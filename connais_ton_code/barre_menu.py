"""L'icône dans la barre de menus, seule présence permanente à l'écran.

C'est le point d'entrée de l'application : un clic ouvre le panneau. Il n'y a
pas de menu déroulant, tout est dans le panneau, comme dans les utilitaires de
barre de menus de macOS.
"""

from __future__ import annotations

from PyQt6.QtCore import QRect, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QSystemTrayIcon

from .logo import ajuster, marque

# Un élément de barre de menus n'a pas à être carré, et la marque est plus
# large que haute : lui imposer un carré la rétrécirait pour rien.
LARGEUR_ICONE = 26
HAUTEUR_ICONE = 19


def icone_barre_menu() -> QIcon:
    """Dessine l'icône plutôt que d'embarquer un fichier image.

    Elle est déclarée comme masque, ce qui demande à macOS de la recolorer
    selon le thème de la barre, comme il le fait pour ses propres icônes.
    """
    pixmap = QPixmap(LARGEUR_ICONE * 2, HAUTEUR_ICONE * 2)
    pixmap.setDevicePixelRatio(2.0)
    pixmap.fill(Qt.GlobalColor.transparent)

    peintre = QPainter(pixmap)
    peintre.setRenderHint(QPainter.RenderHint.Antialiasing)
    cible = QRectF(0.5, 1.0, LARGEUR_ICONE - 1.0, HAUTEUR_ICONE - 2.0)
    peintre.fillPath(ajuster(marque(True), cible), QColor(0, 0, 0))
    peintre.end()

    icone = QIcon(pixmap)
    icone.setIsMask(True)
    return icone


class BarreMenu(QSystemTrayIcon):
    """L'icône, ses deux états, et les notifications."""

    ouverture_demandee = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(icone_barre_menu(), parent)
        self.setToolTip("KnowYourCode")

        # Pas de menu contextuel : sur macOS il s'ouvrirait à tous les clics
        # et empêcherait le panneau d'apparaître.
        self.activated.connect(self._sur_clic)

    def _sur_clic(self, raison: QSystemTrayIcon.ActivationReason) -> None:
        if raison in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.Context,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.ouverture_demandee.emit()

    def zone(self) -> QRect:
        """La position de l'icône à l'écran, pour y accrocher le panneau."""
        return self.geometry()
