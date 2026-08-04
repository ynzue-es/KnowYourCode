"""Le chef d'orchestre : il tient l'état courant et branche les briques.

Toute la logique du cycle est ici. Le panneau signale des intentions, les
briques rendent des données, et c'est l'orchestrateur qui décide de l'état
suivant. Ce découpage est ce qui permet de remplacer le repérage du
projet, le sélecteur ou l'évaluateur sans rouvrir l'interface.
"""

from __future__ import annotations

from PyQt6.QtCore import QObject, QThreadPool

from .barre_menu import BarreMenu
from .etats import Etat, transition_valide
from .evaluateur import Evaluateur
from .historique import Historique
from .modeles import Evaluation, Extrait
from .panneau import Panneau
from .projet import Projet
from .selecteur import Selecteur
from .statistiques import calculer_statistiques
from .taches import TacheEvaluation

MESSAGE_REPOS = "Rien en attente. Une question quand vous voulez."
MESSAGE_SANS_EXTRAIT = (
    "Aucune fonction à faire expliquer n'a été trouvée dans le projet."
)


class Orchestrateur(QObject):
    """Fait tourner le cycle Fermé → Question → Évaluation → Retour."""

    def __init__(
        self,
        panneau: Panneau,
        barre: BarreMenu,
        projet: Projet,
        selecteur: Selecteur,
        evaluateur: Evaluateur,
        historique: Historique,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._panneau = panneau
        self._barre = barre
        self._projet = projet
        self._selecteur = selecteur
        self._evaluateur = evaluateur
        self._historique = historique

        self._etat = Etat.FERME
        self._extrait_courant: Extrait | None = None

        # Une évaluation lancée puis abandonnée finit quand même par rendre
        # son résultat : le jeton permet de reconnaître un retour devenu sans
        # objet au lieu de rouvrir le panneau par surprise.
        self._jeton_evaluation = 0

        self._brancher()

    # ------------------------------------------------------------------
    # Cycle de vie
    # ------------------------------------------------------------------

    def etat(self) -> Etat:
        return self._etat

    def _brancher(self) -> None:
        self._panneau.reponse_soumise.connect(self._sur_reponse)
        self._panneau.passage_demande.connect(self._sur_passage)
        self._panneau.suite_demandee.connect(self._sur_suite)
        self._panneau.question_demandee.connect(self.poser_question)
        self._panneau.tableau_demande.connect(self.afficher_tableau)
        self._panneau.fermeture_demandee.connect(self.fermer)
        self._panneau.masque.connect(self._sur_masque)

        self._barre.ouverture_demandee.connect(self.ouvrir)

    # ------------------------------------------------------------------
    # Transitions
    # ------------------------------------------------------------------

    def _aller_vers(self, etat: Etat) -> None:
        if not transition_valide(self._etat, etat):
            raise RuntimeError(f"Transition interdite : {self._etat} → {etat}")
        self._etat = etat

    def ouvrir(self) -> None:
        """Le panneau s'ouvre : sur la question qui attendait, ou au repos."""
        self._panneau.ancrer(self._barre.zone())

        if self._etat is not Etat.FERME:
            # Déjà ouvert : on le ramène devant, en le replaçant au passage.
            # La position de l'icône a pu devenir connue depuis l'ouverture.
            self._panneau.repositionner()
            self._panneau.raise_()
            self._panneau.activateWindow()
            return

        self._afficher_repos()

    def _afficher_repos(self) -> None:
        self._panneau.afficher_repos(MESSAGE_REPOS)
        if self._etat is not Etat.REPOS:
            self._aller_vers(Etat.REPOS)

    def poser_question(self) -> None:
        """Choisit un extrait et l'affiche."""
        if self._etat not in (Etat.FERME, Etat.REPOS, Etat.RETOUR, Etat.TABLEAU):
            return

        self._panneau.ancrer(self._barre.zone())
        extrait = self._selecteur.choisir(
            self._historique.identifiants_deja_vus(), self._projet.projet_actif()
        )
        if extrait is None:
            self._panneau.afficher_repos(MESSAGE_SANS_EXTRAIT)
            if self._etat is not Etat.REPOS:
                self._aller_vers(Etat.REPOS)
            return

        self._extrait_courant = extrait
        self._panneau.afficher_question(extrait)
        self._aller_vers(Etat.QUESTION)

    def afficher_tableau(self) -> None:
        """Calcule les statistiques et bascule le panneau sur le tableau de bord.

        Recalculées à chaque ouverture plutôt que gardées en mémoire : la
        dernière réponse enregistrée doit toujours apparaître, et relire tout
        l'historique ne coûte rien face à la taille du fichier.
        """
        if self._etat not in (Etat.FERME, Etat.REPOS, Etat.RETOUR):
            return

        self._panneau.ancrer(self._barre.zone())
        statistiques = calculer_statistiques(self._historique.entrees())
        self._panneau.afficher_tableau_de_bord(statistiques)
        self._aller_vers(Etat.TABLEAU)

    def _sur_reponse(self, reponse: str) -> None:
        if self._etat is not Etat.QUESTION or self._extrait_courant is None:
            return

        self._aller_vers(Etat.EVALUATION)
        self._panneau.afficher_attente()

        self._jeton_evaluation += 1
        jeton = self._jeton_evaluation

        tache = TacheEvaluation(self._evaluateur, self._extrait_courant, reponse)
        tache.signaux.terminee.connect(
            lambda evaluation: self._sur_evaluation(jeton, reponse, evaluation)
        )
        QThreadPool.globalInstance().start(tache)

    def _sur_evaluation(
        self, jeton: int, reponse: str, evaluation: Evaluation
    ) -> None:
        if jeton != self._jeton_evaluation or self._etat is not Etat.EVALUATION:
            return
        if self._extrait_courant is None:
            return

        self._historique.enregistrer_reponse(
            self._extrait_courant, reponse, evaluation
        )
        self._panneau.afficher_retour(evaluation)
        self._aller_vers(Etat.RETOUR)

    def _sur_passage(self) -> None:
        if self._etat is not Etat.QUESTION or self._extrait_courant is None:
            return
        self._historique.enregistrer_passage(self._extrait_courant)
        self._extrait_courant = None
        self._afficher_repos()

    def _sur_suite(self) -> None:
        if self._etat is not Etat.RETOUR:
            return
        self._extrait_courant = None
        self._afficher_repos()

    def fermer(self) -> None:
        """Referme le panneau sans rien enregistrer."""
        if self._etat is Etat.FERME:
            return
        self._jeton_evaluation += 1
        self._extrait_courant = None
        self._aller_vers(Etat.FERME)
        self._panneau.fermer()

    def _sur_masque(self) -> None:
        """Le panneau a disparu de lui-même, macOS l'ayant mis en retrait."""
        if self._etat is Etat.FERME:
            return
        self._jeton_evaluation += 1
        self._extrait_courant = None
        self._aller_vers(Etat.FERME)
