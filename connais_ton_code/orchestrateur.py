"""Le chef d'orchestre : il tient l'état courant et branche les briques.

Toute la logique du cycle est ici. Le panneau signale des intentions, les
briques rendent des données, et c'est l'orchestrateur qui décide de l'état
suivant. Ce découpage est ce qui permet de remplacer le repérage du
projet, le sélecteur ou le générateur de cartes sans rouvrir l'interface.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, pyqtSignal

from .barre_menu import BarreMenu
from .cartes import Carte, Correction, Serie, corriger
from .etats import Etat, transition_valide
from .historique import Historique
from . import rappel
from .fenetre_principale import FenetrePrincipale
from .modeles import Extrait
from .panneau import Panneau
from .projet import Projet
from .selecteur import Selecteur
from .statistiques import calculer_statistiques

if TYPE_CHECKING:  # pragma: no cover - le générateur n'est qu'un contrat ici
    from .generateur import Generateur

MESSAGE_REPOS = "Rien en attente. Une série quand vous voulez."
MESSAGE_SANS_EXTRAIT = (
    "Aucune fonction à faire lire n'a été trouvée dans le projet."
)
MESSAGE_SANS_SERIE = (
    "Rien à demander sur ce bout de code. Réessayez dans un instant."
)
MESSAGE_ABANDON = "Série laissée de côté. Une autre quand vous voulez."


def _commentaire_de_bilan(justes: int, total: int) -> str:
    """La phrase qui accompagne le compte, sans note ni félicitations creuses."""
    if total and justes == total:
        return "Ce code-là, vous le connaissez."
    if justes * 2 >= total:
        return "Les explications valent d'être relues."
    return "C'est justement le genre de code qui mérite qu'on y revienne."


class Orchestrateur(QObject):
    """Fait tourner le cycle Fermé → Carte → Correction → Bilan."""

    carte_repondue = pyqtSignal(object, object, str, object)
    """Extrait, carte, réponse donnée, correction : de quoi tenir un journal.

    L'orchestrateur confie déjà la réponse à l'historique ; ce signal existe
    pour qui voudrait la suivre sans passer par le disque.
    """

    def __init__(
        self,
        panneau: Panneau,
        fenetre: FenetrePrincipale,
        barre: BarreMenu,
        projet: Projet,
        selecteur: Selecteur,
        generateur: "Generateur",
        historique: Historique,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._panneau = panneau
        self._fenetre = fenetre
        self._barre = barre
        self._projet = projet
        self._selecteur = selecteur
        self._generateur = generateur
        self._historique = historique

        self._etat = Etat.FERME
        self._extrait_courant: Extrait | None = None
        self._serie: Serie | None = None
        self._index = 0
        self._justes = 0

        self._brancher()

    # ------------------------------------------------------------------
    # Cycle de vie
    # ------------------------------------------------------------------

    def etat(self) -> Etat:
        return self._etat

    def _brancher(self) -> None:
        self._panneau.reponse_donnee.connect(self._sur_reponse)
        self._panneau.passage_demande.connect(self._sur_passage)
        self._panneau.suite_demandee.connect(self._sur_suite)
        self._panneau.question_demandee.connect(self.poser_question)
        self._panneau.fenetre_demandee.connect(self.afficher_fenetre)
        self._panneau.fermeture_demandee.connect(self.fermer)
        self._fenetre.rappel_change.connect(self._sur_rappel)
        self._panneau.masque.connect(self._sur_masque)

        self._barre.ouverture_demandee.connect(self.ouvrir)

    # ------------------------------------------------------------------
    # Transitions
    # ------------------------------------------------------------------

    def _aller_vers(self, etat: Etat) -> None:
        if not transition_valide(self._etat, etat):
            raise RuntimeError(f"Transition interdite : {self._etat} → {etat}")
        self._etat = etat

    def _sur_rappel(self, installe: bool) -> None:
        """Pose ou retire le rappel dans les réglages de Claude Code.

        En cas d'échec, l'interrupteur revient à l'état du fichier plutôt que
        de laisser croire à un changement qui n'a pas eu lieu.
        """
        reussi = rappel.installer() if installe else rappel.retirer()
        if not reussi:
            self._fenetre.definir_rappel(rappel.est_installe())

    def ouvrir(self) -> None:
        """Le panneau s'ouvre : sur la série qui attendait, ou au repos."""
        self._panneau.ancrer(self._barre.zone())

        if self._etat is not Etat.FERME:
            # Déjà ouvert : on le ramène devant, en le replaçant au passage.
            # La position de l'icône a pu devenir connue depuis l'ouverture.
            self._panneau.repositionner()
            self._panneau.raise_()
            self._panneau.activateWindow()
            return

        self._afficher_repos(MESSAGE_REPOS)

    def _afficher_repos(self, message: str) -> None:
        self._oublier_serie()
        self._panneau.afficher_repos(message)
        if self._etat is not Etat.REPOS:
            self._aller_vers(Etat.REPOS)

    def poser_question(self) -> None:
        """Choisit un extrait, fait fabriquer sa série, et pose la première carte.

        Toute la série est fabriquée ici, avant la première carte : c'est ce
        qui permet aux corrections suivantes d'être instantanées, et donc à
        l'exercice de ne jamais faire attendre entre deux cartes.
        """
        if self._etat not in (Etat.FERME, Etat.REPOS, Etat.BILAN):
            return

        self._panneau.ancrer(self._barre.zone())
        extrait = self._selecteur.choisir(
            self._historique.identifiants_deja_vus(), self._projet.projet_actif()
        )
        if extrait is None:
            self._afficher_repos(MESSAGE_SANS_EXTRAIT)
            return

        serie = self._generateur.fabriquer(extrait)
        if serie is None or not serie.cartes:
            self._afficher_repos(MESSAGE_SANS_SERIE)
            return

        self._extrait_courant = extrait
        self._serie = serie
        self._index = 0
        self._justes = 0
        self._poser_carte()

    def afficher_fenetre(self) -> None:
        """Ouvre la grande fenêtre, sans toucher au cycle de l'exercice.

        La progression et les réglages ne sont pas un état du panneau : on
        peut les consulter pendant qu'une carte attend une réponse, sans rien
        lui faire perdre.
        """
        self._fenetre.definir_rappel(rappel.est_installe())
        self._fenetre.afficher(calculer_statistiques(self._historique.entrees()))

    # ------------------------------------------------------------------
    # La série
    # ------------------------------------------------------------------

    def _poser_carte(self) -> None:
        if self._serie is None or self._extrait_courant is None:
            return
        self._panneau.afficher_carte(
            self._extrait_courant,
            self._serie.cartes[self._index],
            self._index + 1,
            len(self._serie.cartes),
        )
        if self._etat is not Etat.QUESTION:
            self._aller_vers(Etat.QUESTION)

    def _sur_reponse(self, reponse: str) -> None:
        """Corrige sur place : rien ne part sur le réseau, rien n'attend."""
        if self._etat is not Etat.QUESTION or self._serie is None:
            return

        carte = self._serie.cartes[self._index]
        correction = corriger(carte, reponse)
        if correction.juste:
            self._justes += 1

        self._enregistrer(carte, reponse, correction)
        self._panneau.afficher_correction(
            correction, self._index + 1, len(self._serie.cartes)
        )
        self._aller_vers(Etat.RETOUR)

    def _enregistrer(
        self, carte: Carte, reponse: str, correction: Correction
    ) -> None:
        """Confie la réponse à l'historique, et la fait connaître au-dehors.

        L'historique est réécrit en même temps que cet exercice : tant que sa
        méthode pour les cartes n'est pas en place, la série doit continuer
        plutôt que de tomber au milieu. Le signal, lui, part dans tous les cas.
        """
        if self._extrait_courant is None:
            return
        self.carte_repondue.emit(self._extrait_courant, carte, reponse, correction)

        enregistrer = getattr(self._historique, "enregistrer_carte", None)
        if enregistrer is not None:
            enregistrer(self._extrait_courant, carte, reponse, correction)

    def _sur_suite(self) -> None:
        """La carte suivante, ou le bilan s'il n'en reste plus."""
        if self._etat is not Etat.RETOUR or self._serie is None:
            return

        self._index += 1
        if self._index < len(self._serie.cartes):
            self._poser_carte()
            return

        total = len(self._serie.cartes)
        justes = self._justes
        self._oublier_serie()
        self._panneau.afficher_bilan(
            justes, total, _commentaire_de_bilan(justes, total)
        )
        self._aller_vers(Etat.BILAN)

    def _sur_passage(self) -> None:
        if self._etat is not Etat.QUESTION or self._extrait_courant is None:
            return
        self._historique.enregistrer_passage(self._extrait_courant)
        self._afficher_repos(MESSAGE_ABANDON)

    def _oublier_serie(self) -> None:
        self._extrait_courant = None
        self._serie = None
        self._index = 0
        self._justes = 0

    # ------------------------------------------------------------------
    # Fermeture
    # ------------------------------------------------------------------

    def fermer(self) -> None:
        """Referme le panneau sans rien enregistrer de plus."""
        if self._etat is Etat.FERME:
            return
        self._oublier_serie()
        self._aller_vers(Etat.FERME)
        self._panneau.fermer()

    def _sur_masque(self) -> None:
        """Le panneau a disparu de lui-même, macOS l'ayant mis en retrait."""
        if self._etat is Etat.FERME:
            return
        self._oublier_serie()
        self._aller_vers(Etat.FERME)
