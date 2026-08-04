"""Le chef d'orchestre : il tient l'état courant et branche les briques.

Toute la logique du cycle est ici. Le panneau signale des intentions, les
briques rendent des données, et c'est l'orchestrateur qui décide de l'état
suivant. Ce découpage est ce qui permet de remplacer le détecteur, le
sélecteur ou l'évaluateur sans rouvrir l'interface.
"""

from __future__ import annotations

from PyQt6.QtCore import QObject, QThreadPool, QTimer

from .barre_menu import BarreMenu
from .detecteur import Detecteur
from .etats import Etat, transition_valide
from .evaluateur import Evaluateur
from .historique import Historique
from .modeles import Evaluation, Extrait
from .panneau import Panneau
from .reglages import Reglages
from .selecteur import Selecteur
from .taches import TacheEvaluation

INTERVALLE_SONDAGE_MS = 1000

TITRE_NOTIFICATION = "KnowYourCode"
TEXTE_NOTIFICATION = "Répondez à quelques questions sur votre code !"

MESSAGE_REPOS = "Rien en attente. Une question quand vous voulez."
MESSAGE_EN_PAUSE = "Détection en pause. Rien ne s'ouvrira tout seul."
MESSAGE_SANS_EXTRAIT = (
    "Aucune fonction à faire expliquer n'a été trouvée dans le projet."
)


class Orchestrateur(QObject):
    """Fait tourner le cycle Fermé → Question → Évaluation → Retour."""

    def __init__(
        self,
        panneau: Panneau,
        barre: BarreMenu,
        detecteur: Detecteur,
        selecteur: Selecteur,
        evaluateur: Evaluateur,
        historique: Historique,
        reglages: Reglages,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._panneau = panneau
        self._barre = barre
        self._detecteur = detecteur
        self._selecteur = selecteur
        self._evaluateur = evaluateur
        self._historique = historique
        self._reglages = reglages

        self._etat = Etat.FERME
        self._extrait_courant: Extrait | None = None
        self._actif = True

        # Une détection ne pose pas la question tout de suite : elle prévient,
        # et la question attend qu'on vienne la chercher.
        self._question_en_attente = False

        # Une évaluation lancée puis abandonnée finit quand même par rendre
        # son résultat : le jeton permet de reconnaître un retour devenu sans
        # objet au lieu de rouvrir le panneau par surprise.
        self._jeton_evaluation = 0

        self._brancher()

        self._sonde = QTimer(self)
        self._sonde.setInterval(INTERVALLE_SONDAGE_MS)
        self._sonde.timeout.connect(self._sonder)

    # ------------------------------------------------------------------
    # Cycle de vie
    # ------------------------------------------------------------------

    def demarrer(self) -> None:
        """Applique l'état enregistré et lance le sondage."""
        self.definir_actif(self._reglages.detection_active())

    def etat(self) -> Etat:
        return self._etat

    def est_actif(self) -> bool:
        return self._actif

    def question_en_attente(self) -> bool:
        return self._question_en_attente

    def _brancher(self) -> None:
        self._panneau.reponse_soumise.connect(self._sur_reponse)
        self._panneau.passage_demande.connect(self._sur_passage)
        self._panneau.suite_demandee.connect(self._sur_suite)
        self._panneau.question_demandee.connect(self.poser_question)
        self._panneau.fermeture_demandee.connect(self.fermer)
        self._panneau.activation_changee.connect(self.definir_actif)
        self._panneau.masque.connect(self._sur_masque)

        self._barre.ouverture_demandee.connect(self.ouvrir)

    # ------------------------------------------------------------------
    # Détection
    # ------------------------------------------------------------------

    def definir_actif(self, actif: bool) -> None:
        """Met la détection à l'écoute ou en pause.

        La pause n'arrête que la détection automatique : demander une question
        reste possible, puisque c'est un geste explicite.
        """
        self._actif = actif
        self._reglages.enregistrer_detection_active(actif)
        self._barre.definir_actif(actif)
        self._panneau.definir_actif(actif)

        if actif:
            self._sonde.start()
            return

        self._sonde.stop()
        # Une question qui attendait n'a plus lieu d'être : mettre en pause
        # veut dire « laisse-moi tranquille », y compris pour ce qui traînait.
        self._definir_attente(False)

    def _sonder(self) -> None:
        """Un tour d'horloge : le détecteur a-t-il quelque chose à signaler ?"""
        if not self._actif or self._question_en_attente:
            return
        if self._detecteur.session_active():
            self.signaler()

    def signaler(self) -> None:
        """Prévient qu'une question attend, sans rien ouvrir.

        Une notification et rien d'autre : ouvrir un panneau par-dessus le
        travail de quelqu'un est le meilleur moyen de le faire désinstaller.
        """
        self._definir_attente(True)
        self._barre.notifier(TITRE_NOTIFICATION, TEXTE_NOTIFICATION)

    def _definir_attente(self, en_attente: bool) -> None:
        """Retient qu'une question attend, et le fait dire par l'icône.

        La pastille double la notification : le système peut refuser de
        l'afficher, l'icône non.
        """
        self._question_en_attente = en_attente
        self._barre.definir_en_attente(en_attente)

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
            # Déjà ouvert : on le ramène simplement devant.
            self._panneau.raise_()
            self._panneau.activateWindow()
            return

        if self._question_en_attente:
            self.poser_question()
            return

        self._afficher_repos()

    def _afficher_repos(self) -> None:
        message = MESSAGE_REPOS if self._actif else MESSAGE_EN_PAUSE
        self._panneau.afficher_repos(message)
        if self._etat is not Etat.REPOS:
            self._aller_vers(Etat.REPOS)

    def poser_question(self) -> None:
        """Choisit un extrait et l'affiche."""
        if self._etat not in (Etat.FERME, Etat.REPOS, Etat.RETOUR):
            return

        self._panneau.ancrer(self._barre.zone())
        extrait = self._selecteur.choisir(
            self._historique.identifiants_deja_vus(), self._detecteur.projet_actif()
        )
        self._definir_attente(False)

        if extrait is None:
            self._panneau.afficher_repos(MESSAGE_SANS_EXTRAIT)
            if self._etat is not Etat.REPOS:
                self._aller_vers(Etat.REPOS)
            return

        self._extrait_courant = extrait
        self._panneau.afficher_question(extrait)
        self._aller_vers(Etat.QUESTION)

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
