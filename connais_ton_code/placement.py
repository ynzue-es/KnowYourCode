"""Placement des fenêtres à l'écran, et restauration de leur position.

Une position mémorisée peut devenir absurde : écran externe débranché,
résolution changée. On préfère replacer la fenêtre au coin par défaut plutôt
que la laisser hors champ, où l'utilisateur ne pourrait plus la récupérer.
"""

from __future__ import annotations

from PyQt6.QtCore import QPoint, QRect
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QWidget

from .apparence import MARGE_OMBRE
from .reglages import Reglages

MARGE_ECRAN = 24


def _zone_utile() -> QRect:
    ecran = QGuiApplication.primaryScreen()
    return ecran.availableGeometry() if ecran else QRect(0, 0, 1280, 800)


def coin_bas_droite(fenetre: QWidget, decalage_vertical: int = 0) -> QPoint:
    """Position du coin bas droit, la marge d'ombre étant hors panneau."""
    zone = _zone_utile()
    x = zone.right() - MARGE_ECRAN - fenetre.width() + MARGE_OMBRE
    y = (
        zone.bottom()
        - MARGE_ECRAN
        - fenetre.height()
        + MARGE_OMBRE
        - decalage_vertical
    )
    return QPoint(x, y)


def coin_haut_droite(fenetre: QWidget) -> QPoint:
    """Position du coin haut droit, juste sous la barre de menus.

    `availableGeometry` exclut déjà la barre de menus : inutile de deviner sa
    hauteur, qui change avec l'encoche des écrans récents.
    """
    zone = _zone_utile()
    return QPoint(
        zone.right() - MARGE_ECRAN - fenetre.width() + MARGE_OMBRE,
        zone.top() + MARGE_ECRAN - MARGE_OMBRE,
    )


def _reste_visible(fenetre: QWidget, position: QPoint) -> bool:
    cadre = QRect(position, fenetre.size())
    return any(
        ecran.availableGeometry().intersects(cadre)
        for ecran in QGuiApplication.screens()
    )


def restaurer_ou_placer(
    fenetre: QWidget,
    reglages: Reglages,
    nom: str,
    decalage_vertical: int = 0,
) -> None:
    """Remet la fenêtre où elle était, sinon la pose en bas à droite."""
    memorisee = reglages.position(nom)
    if memorisee is not None:
        position = QPoint(*memorisee)
        if _reste_visible(fenetre, position):
            fenetre.move(position)
            return
    fenetre.move(coin_bas_droite(fenetre, decalage_vertical))
