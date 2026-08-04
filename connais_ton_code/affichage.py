"""Afficher et masquer une fenêtre sans jamais activer l'application.

Sur macOS, `QWidget.show()` active l'application quoi qu'on fasse : ni
`WA_ShowWithoutActivating`, ni `WindowDoesNotAcceptFocus`, ni le passage en
application accessoire n'y changent quoi que ce soit (vérifié avec Qt 6.11).
Le focus clavier quitte alors le terminal, ce qui est exactement ce que cette
application doit éviter.

On passe donc sous Qt : la fenêtre native est montrée avec
`orderFrontRegardless`, qui affiche sans activer, et retirée avec `orderOut`.
Qt continue de croire la fenêtre visible en permanence, ce qui lui va très
bien et évite de repasser par le chemin qui active.

Un clic de l'utilisateur active l'application normalement : c'est voulu, c'est
comme ça qu'on peut répondre.

Sur les autres systèmes, `WA_ShowWithoutActivating` suffit et ces fonctions se
réduisent à `show()` et `hide()`.
"""

from __future__ import annotations

import ctypes
import os
import sys

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QWidget

# Délai avant de rendre le focus à l'application précédente : Qt active la
# nôtre pendant le tour de boucle qui suit l'affichage, pas pendant l'appel.
_DELAI_RESTITUTION_MS = 50

# À qui rendre le clavier quand on se retire après avoir été activé par un
# clic. Retenu au moment où la fenêtre s'affiche, c'est-à-dire quand
# l'utilisateur est encore en train de travailler ailleurs.
_application_externe = None


def _sur_cocoa() -> bool:
    """Vrai seulement si Qt dessine vraiment à travers Cocoa.

    Le nom de plateforme compte autant que le système : avec le greffon
    `offscreen`, utilisé pour les tests, `winId()` ne désigne pas une NSView
    et la passer à pyobjc fait tomber le processus.
    """
    return (
        sys.platform == "darwin"
        and QGuiApplication.platformName().lower() == "cocoa"
    )


def _fenetre_native(widget: QWidget):
    """Rend le NSWindow derrière le widget, ou None si Cocoa n'est pas là."""
    if not _sur_cocoa():
        return None
    try:
        import objc
    except ImportError:
        return None
    return objc.objc_object(c_void_p=ctypes.c_void_p(int(widget.winId()))).window()


def _application_au_premier_plan():
    try:
        from AppKit import NSWorkspace
    except ImportError:
        return None
    return NSWorkspace.sharedWorkspace().frontmostApplication()


def _retenir_application_externe() -> None:
    global _application_externe
    application = _application_au_premier_plan()
    if application is not None and application.processIdentifier() != os.getpid():
        _application_externe = application


def _rendre_le_clavier() -> None:
    """Rend le focus si l'utilisateur nous l'avait donné en cliquant.

    Sans ça, masquer la fenêtre après avoir cliqué dedans laisse macOS sur
    notre application, qui n'a plus rien à l'écran : les frappes suivantes
    tombent dans le vide au lieu de retourner au terminal.
    """
    try:
        from AppKit import NSApplication
    except ImportError:
        return
    if not NSApplication.sharedApplication().isActive():
        return
    if _application_externe is not None:
        _application_externe.activateWithOptions_(0)
    else:
        NSApplication.sharedApplication().deactivate()


def amorcer(widget: QWidget, montrer_ensuite: bool = False) -> None:
    """Crée la fenêtre native une bonne fois, sans rien montrer.

    C'est le seul moment où l'application prend le focus : l'unique `show()`
    de sa vie, rendu invisible par une opacité nulle, suivi d'une restitution
    du focus à l'application qui l'avait. Après ça, plus rien ne repasse par
    Qt pour afficher.
    """
    if not _sur_cocoa():
        if montrer_ensuite:
            widget.show()
        return

    _retenir_application_externe()
    precedente = _application_externe
    widget.setWindowOpacity(0.0)
    widget.show()

    def rendre_la_main() -> None:
        native = _fenetre_native(widget)
        if native is not None:
            native.orderOut_(None)
        widget.setWindowOpacity(1.0)
        if precedente is not None:
            precedente.activateWithOptions_(0)
        if montrer_ensuite:
            afficher_sans_activer(widget)

    QTimer.singleShot(_DELAI_RESTITUTION_MS, rendre_la_main)


def afficher_sans_activer(widget: QWidget) -> None:
    """Montre la fenêtre en laissant le clavier là où il est."""
    native = _fenetre_native(widget)
    if native is None:
        widget.show()
        return
    _retenir_application_externe()
    native.orderFrontRegardless()
    # La fenêtre a pu changer de contenu pendant qu'elle était retirée.
    widget.update()


def retirer_de_l_ecran(widget: QWidget) -> None:
    """Retire la fenêtre de l'écran sans passer par `hide()`."""
    native = _fenetre_native(widget)
    if native is None:
        widget.hide()
        return
    native.orderOut_(None)
    _rendre_le_clavier()


def est_a_l_ecran(widget: QWidget) -> bool:
    """Dit si la fenêtre est réellement visible.

    `QWidget.isVisible()` ne répond plus à la question sur macOS : il reste
    vrai en permanence puisque c'est la fenêtre native qu'on retire.
    """
    native = _fenetre_native(widget)
    if native is None:
        return widget.isVisible()
    return bool(native.isVisible())
