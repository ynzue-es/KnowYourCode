"""Exécution de l'évaluation hors du fil principal.

L'évaluation deviendra un appel réseau : la faire sur le fil de l'interface
gèlerait la fenêtre, or l'état d'évaluation doit rester utilisable (déplacer la
fenêtre, relire le code, appuyer sur Esc).
"""

from __future__ import annotations

from PyQt6.QtCore import QObject, QRunnable, pyqtSignal

from .evaluateur import Evaluateur
from .modeles import Evaluation, Extrait


class _SignauxEvaluation(QObject):
    """Porte-signaux : un `QRunnable` n'est pas un `QObject`."""

    terminee = pyqtSignal(object)


class TacheEvaluation(QRunnable):
    """Fait tourner un évaluateur dans le pool de fils de Qt.

    Une exception de l'évaluateur est convertie en `Evaluation` plutôt que
    propagée : un fil qui meurt en silence laisserait l'interface tourner
    indéfiniment sur son indicateur d'attente.
    """

    def __init__(self, evaluateur: Evaluateur, extrait: Extrait, reponse: str) -> None:
        super().__init__()
        self._evaluateur = evaluateur
        self._extrait = extrait
        self._reponse = reponse
        self.signaux = _SignauxEvaluation()

    def run(self) -> None:
        try:
            evaluation = self._evaluateur.evaluer(self._extrait, self._reponse)
        except Exception as erreur:  # noqa: BLE001 - on veut vraiment tout attraper
            evaluation = Evaluation(
                verdict=f"L'évaluation a échoué : {erreur}",
                score=0,
                points_oublies=[],
            )
        self.signaux.terminee.emit(evaluation)
