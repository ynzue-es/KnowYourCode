"""Réglages visuels du panneau.

Le parti pris est macOS : un panneau sombre sans cadre, coins arrondis, une
ombre douce, accroché sous l'icône de la barre de menus. Les composants
viennent de la version gratuite de PyQt6-Fluent-Widgets, mais l'habillage est
fait à la main pour éviter le rendu très « Windows 11 » des fenêtres Fluent
complètes.
"""

from __future__ import annotations

import sys

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QGraphicsDropShadowEffect, QWidget
from qfluentwidgets import Theme, setFontFamilies, setTheme, setThemeColor

COULEUR_FOND_PANNEAU = "#1f2023"
COULEUR_BORDURE = "rgba(255, 255, 255, 0.10)"
COULEUR_TEXTE_ATTENUE = "#8a8f98"
COULEUR_ACCENT = "#4c8dff"

# Le panneau est sans cadre : l'ombre est dessinée par nous, donc il faut
# réserver de la marge autour pour qu'elle ait la place d'exister.
MARGE_OMBRE = 14


def appliquer_theme_sombre() -> None:
    """Force le thème sombre, quel que soit le réglage système."""
    setTheme(Theme.DARK)
    setThemeColor(QColor(COULEUR_ACCENT))
    _corriger_police_sur_macos()


def _corriger_police_sur_macos() -> None:
    """Remplace la pile de polices de Fluent par celle du système.

    Fluent demande « Segoe UI », qui n'existe pas sur macOS ; Qt descend alors
    sa liste de repli et atterrit sur PingFang SC, dont les glyphes latins
    donnent immédiatement l'impression d'une application étrangère.
    `.AppleSystemUIFont` est la police d'interface du système, celle du Finder.
    """
    if sys.platform != "darwin":
        return
    setFontFamilies([".AppleSystemUIFont", "Helvetica Neue"])


def configurer_panneau(panneau: QWidget) -> None:
    """Applique les propriétés du panneau flottant.

    `Tool` en fait un panneau utilitaire, qui flotte au-dessus des fenêtres de
    l'application et s'efface quand on passe à autre chose. C'est le
    comportement natif d'un panneau de barre de menus, et il n'est pas
    contrarié : le panneau prend le focus quand on l'ouvre, et disparaît quand
    on retourne travailler ailleurs.
    """
    panneau.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
    panneau.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)


def style_panneau(rayon: int = 10) -> str:
    """Feuille de style du cadre qui sert de fond au panneau."""
    return (
        f"#panneau {{ background-color: {COULEUR_FOND_PANNEAU};"
        f" border: 1px solid {COULEUR_BORDURE}; border-radius: {rayon}px; }}"
    )


def poser_ombre(cible: QWidget) -> None:
    """Ajoute l'ombre portée sous le panneau."""
    ombre = QGraphicsDropShadowEffect(cible)
    ombre.setBlurRadius(24)
    ombre.setOffset(0, 4)
    ombre.setColor(QColor(0, 0, 0, 160))
    cible.setGraphicsEffect(ombre)
