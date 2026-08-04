"""L'icône dans la barre de menus, seule présence permanente à l'écran.

C'est le point d'entrée de l'application : un clic ouvre le panneau, et les
notifications système partent d'ici. Il n'y a pas de menu déroulant, tout est
dans le panneau, comme dans les utilitaires de barre de menus de macOS.
"""

from __future__ import annotations

from PyQt6.QtCore import QRect, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QSystemTrayIcon

from .logo import ajuster, marque

# Un élément de barre de menus n'a pas à être carré, et la marque est plus
# large que haute : lui imposer un carré la rétrécirait pour rien.
LARGEUR_ICONE = 30
HAUTEUR_ICONE = 19

_DIAMETRE_PASTILLE = 5.0

DUREE_NOTIFICATION_MS = 8000


def icone_barre_menu(actif: bool = True, en_attente: bool = False) -> QIcon:
    """Dessine l'icône plutôt que d'embarquer un fichier image.

    Les états se distinguent par la forme et non par la teinte ou la
    transparence : macOS recolore les icônes de barre de menus selon son
    thème, et une icône simplement pâlie se laisse oublier. Écran avec du code
    veut dire « à l'écoute », écran vide veut dire « en pause ».

    La pastille dit qu'une question attend. Elle existe parce qu'une
    notification système peut très bien ne jamais s'afficher, l'utilisateur
    n'ayant pas donné l'autorisation ou étant en mode concentration : l'icône,
    elle, est toujours là.

    L'icône est déclarée comme masque, ce qui demande justement à macOS cette
    recoloration, comme pour ses propres icônes.
    """
    pixmap = QPixmap(LARGEUR_ICONE * 2, HAUTEUR_ICONE * 2)
    pixmap.setDevicePixelRatio(2.0)
    pixmap.fill(Qt.GlobalColor.transparent)

    peintre = QPainter(pixmap)
    peintre.setRenderHint(QPainter.RenderHint.Antialiasing)

    noir = QColor(0, 0, 0)
    largeur_marque = LARGEUR_ICONE - (_DIAMETRE_PASTILLE + 2.0)
    cible = QRectF(0.5, 1.0, largeur_marque - 1.0, HAUTEUR_ICONE - 2.0)
    peintre.fillPath(ajuster(marque(actif), cible), noir)

    if en_attente:
        peintre.setBrush(noir)
        peintre.setPen(Qt.PenStyle.NoPen)
        peintre.drawEllipse(
            QRectF(
                LARGEUR_ICONE - _DIAMETRE_PASTILLE - 0.5,
                2.0,
                _DIAMETRE_PASTILLE,
                _DIAMETRE_PASTILLE,
            )
        )

    peintre.end()

    icone = QIcon(pixmap)
    icone.setIsMask(True)
    return icone


class BarreMenu(QSystemTrayIcon):
    """L'icône, ses deux états, et les notifications."""

    ouverture_demandee = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(icone_barre_menu(True), parent)
        self._actif = True
        self._en_attente = False
        self._rafraichir()

        # Pas de menu contextuel : sur macOS il s'ouvrirait à tous les clics
        # et empêcherait le panneau d'apparaître.
        self.activated.connect(self._sur_clic)
        self.messageClicked.connect(self.ouverture_demandee.emit)

    def _sur_clic(self, raison: QSystemTrayIcon.ActivationReason) -> None:
        if raison in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.Context,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.ouverture_demandee.emit()

    def definir_actif(self, actif: bool) -> None:
        """Reflète l'état de la détection dans l'icône et l'infobulle."""
        self._actif = actif
        self._rafraichir()

    def definir_en_attente(self, en_attente: bool) -> None:
        """Affiche ou retire la pastille qui signale une question en attente."""
        self._en_attente = en_attente
        self._rafraichir()

    def _rafraichir(self) -> None:
        self.setIcon(icone_barre_menu(self._actif, self._en_attente))
        if self._en_attente:
            self.setToolTip("KnowYourCode, une question vous attend")
            return
        self.setToolTip(
            "KnowYourCode, à l'écoute" if self._actif else "KnowYourCode, en pause"
        )

    def notifier(self, titre: str, message: str) -> None:
        """Envoie une notification système.

        Le système peut très bien ne rien afficher, si l'utilisateur a refusé
        les notifications ou activé un mode de concentration. C'est son droit,
        et l'icône reste là pour rattraper le coup.
        """
        self.showMessage(titre, message, self.icon(), DUREE_NOTIFICATION_MS)

    def zone(self) -> QRect:
        """La position de l'icône à l'écran, pour y accrocher le panneau."""
        return self.geometry()
