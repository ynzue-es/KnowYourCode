"""L'icône dans la barre de menus, seule présence permanente à l'écran.

C'est le point d'entrée manuel de l'application : tant que la détection
automatique n'existe pas, c'est de là que partent les questions. Une icône de
barre de menus a l'avantage de ne rien recouvrir et de ne pas se déplacer.
"""

from __future__ import annotations

from PyQt6.QtCore import QRectF, Qt, pyqtSignal
from PyQt6.QtGui import (
    QAction,
    QColor,
    QFont,
    QFontMetricsF,
    QIcon,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PyQt6.QtWidgets import QMenu, QSystemTrayIcon

COTE_ICONE = 18
_CADRE = QRectF(1.4, 2.4, 15.2, 13.2)


def _tracé_du_point_dinterrogation() -> QPainterPath:
    """Le « ? », centré dans le cadre et converti en tracé.

    En tracé et non en texte dessiné : il faut pouvoir le soustraire du cadre
    pour obtenir la version pleine.
    """
    police = QFont("Menlo")
    police.setPixelSize(12)
    police.setBold(True)
    metriques = QFontMetricsF(police)

    tracé = QPainterPath()
    tracé.addText(
        _CADRE.center().x() - metriques.horizontalAdvance("?") / 2,
        _CADRE.center().y() + metriques.capHeight() / 2,
        police,
        "?",
    )
    return tracé


def icone_barre_menu(actif: bool = True) -> QIcon:
    """Dessine l'icône plutôt que d'embarquer un fichier image.

    Deux états, distingués par le plein et le vide plutôt que par la couleur :
    macOS recolore les icônes de barre de menus selon son thème, une teinte ne
    survivrait pas. Plein veut dire « à l'écoute », vide « en pause ».

    L'icône est déclarée comme masque, ce qui demande justement à macOS cette
    recoloration, comme pour ses propres icônes.
    """
    pixmap = QPixmap(COTE_ICONE * 2, COTE_ICONE * 2)
    pixmap.setDevicePixelRatio(2.0)
    pixmap.fill(Qt.GlobalColor.transparent)

    peintre = QPainter(pixmap)
    peintre.setRenderHint(QPainter.RenderHint.Antialiasing)

    noir = QColor(0, 0, 0)
    cadre = QPainterPath()
    cadre.addRoundedRect(_CADRE, 4.0, 4.0)
    interrogation = _tracé_du_point_dinterrogation()

    if actif:
        peintre.fillPath(cadre.subtracted(interrogation), noir)
    else:
        stylo = QPen(noir)
        stylo.setWidthF(1.6)
        peintre.setPen(stylo)
        peintre.drawPath(cadre)
        peintre.fillPath(interrogation, noir)

    peintre.end()

    icone = QIcon(pixmap)
    icone.setIsMask(True)
    return icone


class BarreMenu(QSystemTrayIcon):
    """L'icône et son menu déroulant."""

    question_demandee = pyqtSignal()
    detection_simulee = pyqtSignal()
    activation_changee = pyqtSignal(bool)
    fermeture_demandee = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(icone_barre_menu(True), parent)

        # Le menu doit rester référencé côté Python, sinon il est ramassé et
        # l'icône devient un bouton sans effet.
        self._menu = QMenu()

        self._action_activation = QAction("Détection active", self._menu)
        self._action_activation.setCheckable(True)
        self._action_activation.setChecked(True)
        self._action_activation.toggled.connect(self.activation_changee.emit)
        self._menu.addAction(self._action_activation)

        self._menu.addSeparator()

        self._action_question = QAction("Poser une question", self._menu)
        self._action_question.triggered.connect(self.question_demandee.emit)
        self._menu.addAction(self._action_question)

        self._action_detection = QAction("Simuler une détection", self._menu)
        self._action_detection.setToolTip(
            "Affiche l'invitation, comme le fait le démarrage d'une session"
        )
        self._action_detection.triggered.connect(self.detection_simulee.emit)
        self._menu.addAction(self._action_detection)

        self._menu.addSeparator()

        self._action_quitter = QAction("Quitter KnowYourCode", self._menu)
        self._action_quitter.triggered.connect(self.fermeture_demandee.emit)
        self._menu.addAction(self._action_quitter)

        self.setContextMenu(self._menu)
        self.definir_actif(True)

    def definir_actif(self, actif: bool) -> None:
        """Reflète l'état dans l'icône, l'infobulle et la coche du menu.

        Le signal est bloqué le temps de cocher : sans ça, mettre le menu à
        jour depuis l'orchestrateur relancerait l'orchestrateur.
        """
        self.setIcon(icone_barre_menu(actif))
        self.setToolTip(
            "KnowYourCode — à l'écoute" if actif else "KnowYourCode — en pause"
        )

        self._action_activation.blockSignals(True)
        self._action_activation.setChecked(actif)
        self._action_activation.blockSignals(False)

        # Simuler une détection alors que la détection est en pause ne
        # produirait rien : mieux vaut le dire en grisant l'entrée.
        self._action_detection.setEnabled(actif)
