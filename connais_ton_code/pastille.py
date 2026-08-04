"""La pastille de test, qui remplace la détection automatique.

BOUCHON : cette petite fenêtre n'existe que tant que le détecteur est factice.
Quand la surveillance des transcripts JSONL sera en place, elle disparaîtra et
les questions arriveront toutes seules.
"""

from __future__ import annotations

from PyQt6.QtCore import QPoint, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import FluentIcon, PushButton, TransparentToolButton

from .affichage import afficher_sans_activer
from .apparence import (
    MARGE_OMBRE,
    configurer_fenetre_flottante,
    poser_ombre,
    style_panneau,
)

LARGEUR = 210
HAUTEUR = 44


class PastilleTest(QWidget):
    """Deux boutons qui flottent : déclencher une question, ou quitter."""

    question_demandee = pyqtSignal()
    fermeture_demandee = pyqtSignal()
    deplacee = pyqtSignal(int, int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        configurer_fenetre_flottante(self)
        self.setWindowTitle("KnowYourCode — test")
        self.resize(LARGEUR + 2 * MARGE_OMBRE, HAUTEUR + 2 * MARGE_OMBRE)

        self._origine_glissement: QPoint | None = None
        self._construire()

    def _construire(self) -> None:
        exterieur = QVBoxLayout(self)
        exterieur.setContentsMargins(
            MARGE_OMBRE, MARGE_OMBRE, MARGE_OMBRE, MARGE_OMBRE
        )

        panneau = QFrame(self)
        panneau.setObjectName("panneau")
        panneau.setStyleSheet(style_panneau(rayon=HAUTEUR // 2))
        poser_ombre(panneau)
        exterieur.addWidget(panneau)

        ligne = QHBoxLayout(panneau)
        ligne.setContentsMargins(8, 6, 8, 6)
        ligne.setSpacing(6)

        bouton = PushButton("Poser une question", panneau)
        bouton.clicked.connect(self.question_demandee.emit)
        ligne.addWidget(bouton, stretch=1)

        quitter = TransparentToolButton(FluentIcon.POWER_BUTTON, panneau)
        quitter.setFixedSize(28, 28)
        quitter.setIconSize(QSize(12, 12))
        quitter.setToolTip("Quitter KnowYourCode")
        quitter.clicked.connect(self.fermeture_demandee.emit)
        ligne.addWidget(quitter)

    def afficher_sans_voler_le_focus(self) -> None:
        afficher_sans_activer(self)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._origine_glissement = (
                event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._origine_glissement is not None:
            self.move(event.globalPosition().toPoint() - self._origine_glissement)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._origine_glissement is not None:
            self._origine_glissement = None
            self.deplacee.emit(self.pos().x(), self.pos().y())
            event.accept()
