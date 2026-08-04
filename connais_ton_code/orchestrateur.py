"""Le chef d'orchestre : il tient l'état courant et branche les briques.

Toute la logique du cycle est ici. Les fenêtres signalent des intentions, les
briques rendent des données, et c'est l'orchestrateur qui décide de l'état
suivant. Ce découpage est ce qui permettra de remplacer le détecteur, le
sélecteur ou l'évaluateur sans rouvrir l'interface.
"""

from __future__ import annotations

from PyQt6.QtCore import QObject, QThreadPool, QTimer

from .barre_menu import BarreMenu
from .detecteur import Detecteur
from .etats import Etat, transition_valide
from .evaluateur import Evaluateur
from .fenetre import FenetreFlottante
from .historique import Historique
from .invitation import BulleInvitation
from .modeles import Evaluation, Extrait
from .reglages import Reglages
from .selecteur import Selecteur
from .taches import TacheEvaluation

INTERVALLE_SONDAGE_MS = 1000


class Orchestrateur(QObject):
    """Fait tourner le cycle Masquée → Invitation → Question → Évaluation → Retour."""

    def __init__(
        self,
        fenetre: FenetreFlottante,
        bulle: BulleInvitation,
        detecteur: Detecteur,
        selecteur: Selecteur,
        evaluateur: Evaluateur,
        historique: Historique,
        reglages: Reglages,
        barre: BarreMenu | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._fenetre = fenetre
        self._bulle = bulle
        self._detecteur = detecteur
        self._selecteur = selecteur
        self._evaluateur = evaluateur
        self._historique = historique
        self._reglages = reglages
        self._barre = barre

        self._etat = Etat.MASQUEE
        self._extrait_courant: Extrait | None = None

        # Une évaluation lancée puis abandonnée (Esc) finit quand même par
        # rendre son résultat : le jeton permet de reconnaître un retour
        # devenu sans objet au lieu de rouvrir la fenêtre par surprise.
        self._jeton_evaluation = 0

        self._brancher()

        self._sonde = QTimer(self)
        self._sonde.setInterval(INTERVALLE_SONDAGE_MS)
        self._sonde.timeout.connect(self._sonder)

    # ------------------------------------------------------------------
    # Cycle de vie
    # ------------------------------------------------------------------

    def demarrer(self) -> None:
        """Lance le sondage du détecteur. Rien ne s'affiche encore."""
        self._sonde.start()

    def etat(self) -> Etat:
        return self._etat

    def _brancher(self) -> None:
        self._fenetre.reponse_soumise.connect(self._sur_reponse)
        self._fenetre.passage_demande.connect(self._sur_passage)
        self._fenetre.suite_demandee.connect(self._sur_suite)
        self._fenetre.masquage_demande.connect(self._sur_masquage)
        self._fenetre.deplacee.connect(
            lambda x, y: self._reglages.enregistrer_position("fenetre", x, y)
        )

        self._bulle.ouverture_demandee.connect(self.poser_question)
        self._bulle.rejet_demande.connect(self._sur_rejet_invitation)

        if self._barre is not None:
            self._barre.question_demandee.connect(self.poser_question)
            self._barre.detection_simulee.connect(self._sur_detection_simulee)

    # ------------------------------------------------------------------
    # Transitions
    # ------------------------------------------------------------------

    def _aller_vers(self, etat: Etat) -> None:
        if not transition_valide(self._etat, etat):
            raise RuntimeError(f"Transition interdite : {self._etat} → {etat}")
        self._etat = etat

    def _sonder(self) -> None:
        """Un tour d'horloge : le détecteur a-t-il quelque chose à signaler ?"""
        # Inviter par-dessus une question en cours reviendrait à effacer une
        # réponse en train d'être écrite.
        if self._etat is not Etat.MASQUEE:
            return
        if self._detecteur.session_active():
            self.inviter()

    def inviter(self) -> None:
        """Affiche la bulle d'invitation, sans encore choisir d'extrait.

        Le tirage est repoussé au moment où l'utilisateur accepte : rien ne
        garantit qu'il le fera, et une invitation ignorée ne doit pas brûler
        un extrait.
        """
        if self._etat is not Etat.MASQUEE:
            return
        self._bulle.afficher()
        self._aller_vers(Etat.INVITATION)

    def poser_question(self) -> None:
        """Choisit un extrait et l'affiche. Sans extrait, rien ne se passe."""
        if self._etat not in (Etat.MASQUEE, Etat.INVITATION, Etat.RETOUR):
            return

        extrait = self._selecteur.choisir(self._historique.identifiants_deja_vus())
        if extrait is None:
            self._sur_rejet_invitation()
            return

        self._bulle.masquer()
        self._extrait_courant = extrait
        self._fenetre.afficher_question(extrait)
        self._aller_vers(Etat.QUESTION)

    def _sur_rejet_invitation(self) -> None:
        """L'invitation est écartée, ou s'est effacée toute seule."""
        if self._etat is not Etat.INVITATION:
            return
        self._bulle.masquer()
        self._aller_vers(Etat.MASQUEE)

    def _sur_detection_simulee(self) -> None:
        """Le menu passe par le détecteur, pas par un raccourci interne.

        Cela garde un seul chemin d'entrée dans le cycle, celui qui servira
        aussi à la détection automatique.
        """
        if hasattr(self._detecteur, "demander_question"):
            self._detecteur.demander_question()

    def _sur_reponse(self, reponse: str) -> None:
        if self._etat is not Etat.QUESTION or self._extrait_courant is None:
            return

        self._aller_vers(Etat.EVALUATION)
        self._fenetre.afficher_attente()

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
        self._fenetre.afficher_retour(evaluation)
        self._aller_vers(Etat.RETOUR)

    def _sur_passage(self) -> None:
        if self._etat is not Etat.QUESTION or self._extrait_courant is None:
            return
        self._historique.enregistrer_passage(self._extrait_courant)
        self._terminer()

    def _sur_suite(self) -> None:
        if self._etat is not Etat.RETOUR:
            return
        self._terminer()

    def _sur_masquage(self) -> None:
        """Esc : on masque et on n'enregistre rien, même en pleine évaluation."""
        if self._etat is Etat.MASQUEE:
            return
        self._jeton_evaluation += 1
        self._terminer()

    def _terminer(self) -> None:
        self._extrait_courant = None
        self._bulle.masquer()
        self._fenetre.masquer()
        self._aller_vers(Etat.MASQUEE)
