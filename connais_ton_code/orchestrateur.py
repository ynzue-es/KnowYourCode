"""Le chef d'orchestre : il tient l'état courant et branche les briques.

Toute la logique du cycle est ici. Le panneau signale des intentions, les
briques rendent des données, et c'est l'orchestrateur qui décide de l'état
suivant. Ce découpage est ce qui permet de remplacer le repérage du
projet, le sélecteur ou le générateur de cartes sans rouvrir l'interface.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pathlib import Path

from PyQt6.QtCore import QObject, QThreadPool, QTimer, pyqtSignal

from .barre_menu import BarreMenu
from .cartes import Carte, Correction, Serie, corriger
from .etats import Etat, transition_valide
from .historique import Historique
from . import rappel, reveil
from .fenetre_principale import FenetrePrincipale
from .modeles import Extrait
from .panneau import Panneau
from .projet import Projet
from .selecteur import Selecteur
from .statistiques import calculer_statistiques
from .taches import TacheFabrication

if TYPE_CHECKING:  # pragma: no cover - le générateur n'est qu'un contrat ici
    from .generateur import Generateur

MESSAGE_REPOS = "Rien en attente. Une série quand vous voulez."
MESSAGE_SANS_EXTRAIT = (
    "Aucune fonction à faire lire n'a été trouvée dans le projet."
)
MESSAGE_SANS_SERIE = (
    "Rien à demander sur ce bout de code. Réessayez dans un instant."
)
MESSAGE_PREPARATION = "Je prépare les questions…"

# Au-delà, le préchargement se tait. Un clic de l'utilisateur, lui, retente
# toujours : c'est une demande explicite, elle mérite un essai même si les
# précédents ont échoué.
ECHECS_AVANT_DE_SE_TAIRE = 3
MESSAGE_ABANDON = "Série laissée de côté. Une autre quand vous voulez."


def _date_de_fichier(chemin: Path) -> float:
    """La date de dernière écriture, ou zéro si le fichier n'est pas là."""
    try:
        return chemin.stat().st_mtime
    except OSError:
        return 0.0


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

        # L'avance prise pendant le repos : une série déjà fabriquée, qui
        # attend qu'on la demande. C'est elle qui rend l'ouverture instantanée.
        self._serie_prete: Serie | None = None
        self._fabrication_en_cours = False
        # Une fabrication lancée puis abandonnée finit quand même par rendre
        # son résultat. Le jeton permet de reconnaître un retour devenu sans
        # objet au lieu de rouvrir une question par surprise.
        self._jeton_fabrication = 0
        self._echecs_de_suite = 0

        self._brancher()
        self._guetter_le_reveil()

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
        self._fenetre.reveil_change.connect(self._sur_reveil)
        self._panneau.masque.connect(self._sur_masque)

        self._barre.ouverture_demandee.connect(self.ouvrir)

    # ------------------------------------------------------------------
    # Transitions
    # ------------------------------------------------------------------

    def _aller_vers(self, etat: Etat) -> None:
        if not transition_valide(self._etat, etat):
            raise RuntimeError(f"Transition interdite : {self._etat} → {etat}")
        self._etat = etat

    # ------------------------------------------------------------------
    # Le réveil
    # ------------------------------------------------------------------

    def _guetter_le_reveil(self) -> None:
        """Surveille le fichier que le hook de Claude Code vient toucher.

        Un `stat` toutes les deux secondes plutôt qu'une surveillance du
        système de fichiers : le fichier est créé, remplacé, parfois effacé
        avec le dossier de données, et un observateur posé sur un chemin qui
        n'existe pas encore ne se réarme pas tout seul.

        La date de départ est celle du fichier au lancement : sans elle, un
        réveil vieux de trois jours ouvrirait une série au démarrage.
        """
        self._date_du_reveil = _date_de_fichier(reveil.chemin_reveil())
        self._guetteur = QTimer(self)
        self._guetteur.setInterval(2000)
        self._guetteur.timeout.connect(self._sur_guet)
        self._guetteur.start()

    def _sur_guet(self) -> None:
        date = _date_de_fichier(reveil.chemin_reveil())
        if date <= self._date_du_reveil:
            return
        self._date_du_reveil = date

        # Le réglage peut être éteint : dans ce cas plus personne ne touche le
        # fichier, et ce chemin n'est jamais emprunté. On ne relit donc pas
        # les réglages ici, ce serait payer une lecture toutes les deux
        # secondes pour une information qui ne sert qu'une fois.
        if self._etat is not Etat.FERME:
            return
        if calculer_statistiques(self._historique.entrees()).faite_aujourdhui:
            # La série du jour est faite : on a assez demandé. Le compteur de
            # jours est tenu, le reste serait du harcèlement.
            return

        self.ouvrir()
        self.poser_question()

    def _sur_reveil(self, installe: bool) -> None:
        """Pose ou retire le hook dans les réglages de Claude Code."""
        reussi = reveil.installer() if installe else reveil.retirer()
        if not reussi:
            self._fenetre.definir_reveil(reveil.est_installe())

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
        self._precharger()

    def poser_question(self) -> None:
        """Pose la première carte de la série, en la faisant fabriquer au besoin.

        Toute la série est fabriquée d'un coup, avant la première carte :
        c'est ce qui permet aux corrections suivantes d'être instantanées, et
        donc à l'exercice de ne jamais faire attendre entre deux cartes.

        Si le préchargement a eu le temps d'aboutir — c'est le cas ordinaire,
        il démarre dès que le panneau se pose au repos — il n'y a rien à
        attendre du tout.
        """
        if self._etat not in (Etat.FERME, Etat.REPOS, Etat.BILAN):
            return

        self._panneau.ancrer(self._barre.zone())
        self._echecs_de_suite = 0

        prete = self._serie_prete
        if prete is not None:
            self._serie_prete = None
            self._commencer(prete)
            return

        self._aller_vers(Etat.PREPARATION)
        self._panneau.afficher_repos(MESSAGE_PREPARATION)
        # Une fabrication est peut-être déjà en vol, lancée par le
        # préchargement : la doubler ferait deux appels réseau pour une seule
        # série. On se contente d'attendre celle-là.
        if not self._fabrication_en_cours:
            self._lancer_fabrication()

    def _lancer_fabrication(self) -> None:
        """Choisit un extrait et met sa série en fabrication, hors fil principal.

        Fabriquer, c'est appeler Mistral. Sur le fil de l'interface, le
        panneau se figerait jusqu'à la réponse — jusqu'au délai de
        quarante-cinq secondes en cas de panne.
        """
        extrait = self._selecteur.choisir(
            self._historique.identifiants_deja_vus(), self._projet.projet_actif()
        )
        if extrait is None:
            if self._etat is Etat.PREPARATION:
                self._afficher_repos(MESSAGE_SANS_EXTRAIT)
            return

        self._jeton_fabrication += 1
        jeton = self._jeton_fabrication
        self._fabrication_en_cours = True

        tache = TacheFabrication(self._generateur, extrait)
        tache.signaux.terminee.connect(
            lambda serie: self._sur_fabrication(jeton, extrait, serie)
        )
        QThreadPool.globalInstance().start(tache)

    def _sur_fabrication(
        self, jeton: int, extrait: Extrait, serie: Serie | None
    ) -> None:
        """Recueille une série fabriquée, si elle a encore un objet.

        Une fabrication abandonnée — panneau refermé, série laissée de côté —
        finit quand même par rendre son résultat. Le jeton permet de
        reconnaître un retour devenu sans objet au lieu de rouvrir une
        question par surprise.
        """
        if jeton != self._jeton_fabrication:
            return
        self._fabrication_en_cours = False

        if serie is None or not serie.cartes:
            # Cet extrait-là n'a rien donné. En préchargement on se tait et on
            # retentera au prochain repos ; si quelqu'un attend devant, il
            # faut le lui dire.
            self._echecs_de_suite += 1
            if self._etat is Etat.PREPARATION:
                self._afficher_repos(MESSAGE_SANS_SERIE)
            return

        self._echecs_de_suite = 0
        if self._etat is Etat.PREPARATION:
            self._commencer(serie)
        else:
            self._serie_prete = serie

    def _precharger(self) -> None:
        """Prépare la prochaine série pendant que le panneau est au repos.

        C'est ce qui rend l'ouverture instantanée : le temps qu'on lise le
        message d'accueil et qu'on clique, les cartes sont déjà écrites. Rien
        ne s'affiche et rien ne s'ouvre — on ne fait que remplir l'avance.

        Un échec ramène au repos, et le repos précharge : sans compteur, un
        projet dont aucun extrait ne donne de série ferait tourner le réseau
        en boucle sans que personne ne s'en aperçoive. Après quelques essais
        infructueux on se tait, jusqu'à ce que l'utilisateur redemande.
        """
        if self._serie_prete is not None or self._fabrication_en_cours:
            return
        if self._echecs_de_suite >= ECHECS_AVANT_DE_SE_TAIRE:
            return
        self._lancer_fabrication()

    def _commencer(self, serie: Serie) -> None:
        self._extrait_courant = serie.extrait
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
        self._fenetre.definir_reveil(reveil.est_installe())
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

        Carte par carte, jamais série par série : quelqu'un qui referme au
        bout de deux cartes doit garder sa journée. C'est la série de jours
        qui tient l'habitude, et elle ne se perd pas sur une interruption.

        Ce que l'utilisateur a répondu voyage dans la `Correction`, qui le
        porte déjà — inutile de le passer une seconde fois à côté.
        """
        if self._extrait_courant is None:
            return
        self.carte_repondue.emit(self._extrait_courant, carte, reponse, correction)
        self._historique.enregistrer_carte(self._extrait_courant, carte, correction)

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
