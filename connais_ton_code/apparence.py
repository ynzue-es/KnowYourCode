"""Réglages visuels communs aux fenêtres flottantes.

Le parti pris est macOS : un panneau sombre sans cadre, coins arrondis, une
ombre douce, et rien qui clignote. Les composants viennent de la version
gratuite de PyQt6-Fluent-Widgets, mais l'habillage du panneau est fait à la
main pour éviter le rendu très « Windows 11 » des fenêtres Fluent complètes.
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

# La fenêtre est sans cadre : l'ombre est dessinée par nous, donc il faut
# réserver de la marge autour du panneau pour qu'elle ait la place d'exister.
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


def configurer_fenetre_flottante(fenetre: QWidget) -> None:
    """Applique les propriétés de fenêtre flottante qui ne vole pas le focus.

    Trois réglages font tout le travail sur macOS :
    - `Tool` crée un NSPanel, qui flotte au-dessus sans activer l'application ;
    - `WA_ShowWithoutActivating` empêche l'affichage de rendre la fenêtre
      active, donc le clavier reste au terminal ;
    - `WA_MacAlwaysShowToolWindow` annule le comportement par défaut des
      panneaux macOS, qui disparaissent dès que l'application perd le focus,
      ce qui masquerait la question au moment précis où elle doit rester là.
    """
    fenetre.setWindowFlags(
        Qt.WindowType.Tool
        | Qt.WindowType.FramelessWindowHint
        | Qt.WindowType.WindowStaysOnTopHint
    )
    fenetre.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
    fenetre.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow, True)
    fenetre.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)


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
