"""Fabrication des cartes hors du fil principal.

Fabriquer une série, c'est un appel réseau. Le faire sur le fil de l'interface
gèlerait la fenêtre le temps de la réponse de Mistral — jusqu'au délai de
quarante-cinq secondes en cas de panne, avec le curseur qui tourne et rien à
quoi se raccrocher.

La correction, elle, ne passe plus par ici : elle est locale et immédiate.
Seule la fabrication demande à s'écarter, et elle a lieu une fois par série,
avant la première carte — de préférence en avance, pendant que le panneau est
au repos.
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from PyQt6.QtCore import QObject, QRunnable, pyqtSignal

from .cartes import Serie
from .couverture import Couverture, mesurer
from .generateur import Generateur
from .modeles import EntreeHistorique, Extrait


class _SignauxFabrication(QObject):
    """Porte-signaux : un `QRunnable` n'est pas un `QObject`."""

    terminee = pyqtSignal(object)
    """Rend la `Serie` fabriquée, ou `None` s'il n'y avait rien à fabriquer."""


class TacheFabrication(QRunnable):
    """Fait tourner un générateur dans le pool de fils de Qt.

    Une exception du générateur devient un `None` plutôt que de remonter : un
    fil qui meurt en silence laisserait le panneau attendre une série qui
    n'arrive jamais. Le contrat du générateur interdit déjà de lever, mais
    l'interface ne peut pas se permettre d'en dépendre.
    """

    def __init__(self, generateur: Generateur, extrait: Extrait) -> None:
        super().__init__()
        self._generateur = generateur
        self._extrait = extrait
        self.signaux = _SignauxFabrication()

    def run(self) -> None:
        try:
            serie: Serie | None = self._generateur.fabriquer(self._extrait)
        except Exception:  # noqa: BLE001 - on veut vraiment tout attraper
            serie = None
        self.signaux.terminee.emit(serie)


class _SignauxCouverture(QObject):
    terminee = pyqtSignal(object)
    """Rend la `Couverture` mesurée, ou `None` si la mesure a échoué."""


class TacheCouverture(QRunnable):
    """Mesure la couverture du projet hors du fil de l'interface.

    Le parcours du projet entier coûte un quart de seconde sur ce dépôt et
    plus d'une demi-seconde sur un gros : c'est court pour un calcul, mais
    long pour une fenêtre qui vient de s'ouvrir. Le tableau de bord s'affiche
    donc d'abord, et cette mesure vient s'y poser quand elle est prête.
    """

    def __init__(self, entrees: Sequence[EntreeHistorique], dossier: Path | None):
        super().__init__()
        self._entrees = list(entrees)
        self._dossier = dossier
        self.signaux = _SignauxCouverture()

    def run(self) -> None:
        try:
            resultat: Couverture | None = mesurer(self._entrees, self._dossier)
        except Exception:  # noqa: BLE001 - une mesure ratée n'est pas une panne
            resultat = None
        self.signaux.terminee.emit(resultat)
