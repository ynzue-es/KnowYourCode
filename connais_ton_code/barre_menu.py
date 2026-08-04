"""L'icône dans la barre de menus, seule présence permanente à l'écran.

C'est le point d'entrée manuel de l'application : tant que la détection
automatique n'existe pas, c'est de là que partent les questions. Une icône de
barre de menus a l'avantage de ne rien recouvrir et de ne pas se déplacer.
"""

from __future__ import annotations

from PyQt6.QtCore import QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QIcon, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import QMenu, QSystemTrayIcon

COTE_ICONE = 18


def icone_barre_menu() -> QIcon:
    """Dessine l'icône plutôt que d'embarquer un fichier image.

    Elle est déclarée comme masque : macOS la traite alors en image
    « template », c'est-à-dire recolorée par le système selon le thème de la
    barre et l'état de sélection. Une icône en couleur y ferait tache.
    """
    pixmap = QPixmap(COTE_ICONE * 2, COTE_ICONE * 2)
    pixmap.setDevicePixelRatio(2.0)
    pixmap.fill(Qt.GlobalColor.transparent)

    peintre = QPainter(pixmap)
    peintre.setRenderHint(QPainter.RenderHint.Antialiasing)

    stylo = QPen(QColor(0, 0, 0))
    stylo.setWidthF(1.6)
    peintre.setPen(stylo)
    peintre.drawRoundedRect(QRectF(1.4, 2.4, 15.2, 13.2), 4.0, 4.0)

    police = peintre.font()
    police.setPixelSize(12)
    police.setBold(True)
    peintre.setFont(police)
    peintre.drawText(
        QRectF(1.4, 2.4, 15.2, 13.2), Qt.AlignmentFlag.AlignCenter, "?"
    )
    peintre.end()

    icone = QIcon(pixmap)
    icone.setIsMask(True)
    return icone


class BarreMenu(QSystemTrayIcon):
    """L'icône et son menu déroulant."""

    question_demandee = pyqtSignal()
    detection_simulee = pyqtSignal()
    fermeture_demandee = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(icone_barre_menu(), parent)
        self.setToolTip("KnowYourCode")

        # Le menu doit rester référencé côté Python, sinon il est ramassé et
        # l'icône devient un bouton sans effet.
        self._menu = QMenu()

        self._action_question = QAction("Poser une question", self._menu)
        self._action_question.triggered.connect(self.question_demandee.emit)
        self._menu.addAction(self._action_question)

        self._action_detection = QAction("Simuler une détection", self._menu)
        self._action_detection.setToolTip(
            "Affiche l'invitation, comme le fera le démarrage d'une session"
        )
        self._action_detection.triggered.connect(self.detection_simulee.emit)
        self._menu.addAction(self._action_detection)

        self._menu.addSeparator()

        self._action_quitter = QAction("Quitter KnowYourCode", self._menu)
        self._action_quitter.triggered.connect(self.fermeture_demandee.emit)
        self._menu.addAction(self._action_quitter)

        self.setContextMenu(self._menu)
