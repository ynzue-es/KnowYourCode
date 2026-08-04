"""La bulle qui signale qu'une session Claude Code vient de démarrer.

Elle ne pose pas encore de question : elle propose. Interrompre quelqu'un en
plein travail par un formulaire de trois cents pixels est le meilleur moyen de
lui faire fermer l'application au bout de deux jours ; une ligne de texte qui
s'efface toute seule se laisse ignorer sans effort.
"""

from __future__ import annotations

from PyQt6.QtCore import QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QKeyEvent, QMouseEvent
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, CaptionLabel, FluentIcon, TransparentToolButton

from .affichage import afficher_sans_activer, est_a_l_ecran, retirer_de_l_ecran
from .apparence import (
    COULEUR_TEXTE_ATTENUE,
    MARGE_OMBRE,
    configurer_fenetre_flottante,
    poser_ombre,
    style_panneau,
)

LARGEUR = 320
HAUTEUR = 62

# Au-delà, l'invitation n'est plus une invitation mais un reproche.
DUREE_AFFICHAGE_MS = 15000

TEXTE = "Répondez à quelques questions sur votre code !"


class BulleInvitation(QWidget):
    """Un bandeau discret, cliquable, qui disparaît de lui-même."""

    ouverture_demandee = pyqtSignal()
    rejet_demande = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        configurer_fenetre_flottante(self)
        self.setWindowTitle("KnowYourCode")
        self.resize(LARGEUR + 2 * MARGE_OMBRE, HAUTEUR + 2 * MARGE_OMBRE)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._minuteur = QTimer(self)
        self._minuteur.setSingleShot(True)
        self._minuteur.setInterval(DUREE_AFFICHAGE_MS)
        self._minuteur.timeout.connect(self.rejet_demande.emit)

        self._construire()

    def _construire(self) -> None:
        exterieur = QVBoxLayout(self)
        exterieur.setContentsMargins(
            MARGE_OMBRE, MARGE_OMBRE, MARGE_OMBRE, MARGE_OMBRE
        )

        panneau = QFrame(self)
        panneau.setObjectName("panneau")
        panneau.setStyleSheet(style_panneau())
        poser_ombre(panneau)
        exterieur.addWidget(panneau)

        ligne = QHBoxLayout(panneau)
        ligne.setContentsMargins(14, 10, 8, 10)
        ligne.setSpacing(8)

        textes = QVBoxLayout()
        textes.setSpacing(1)
        textes.addWidget(BodyLabel(TEXTE, panneau))

        rappel = CaptionLabel("Cliquez pour commencer", panneau)
        rappel.setStyleSheet(f"color: {COULEUR_TEXTE_ATTENUE};")
        textes.addWidget(rappel)
        ligne.addLayout(textes, stretch=1)

        self._bouton_fermer = TransparentToolButton(FluentIcon.CLOSE, panneau)
        self._bouton_fermer.setFixedSize(24, 24)
        self._bouton_fermer.setIconSize(QSize(9, 9))
        self._bouton_fermer.setToolTip("Ignorer")
        self._bouton_fermer.clicked.connect(self.rejet_demande.emit)
        ligne.addWidget(self._bouton_fermer, alignment=Qt.AlignmentFlag.AlignTop)

    def afficher(self) -> None:
        """Montre la bulle et arme son effacement automatique."""
        afficher_sans_activer(self)
        self._minuteur.start()

    def masquer(self) -> None:
        self._minuteur.stop()
        retirer_de_l_ecran(self)

    def est_visible(self) -> bool:
        return est_a_l_ecran(self)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        # Tout le panneau est cliquable sauf le bouton d'écart, qui consomme
        # son clic avant d'arriver ici.
        if event.button() == Qt.MouseButton.LeftButton:
            self.ouverture_demandee.emit()
            event.accept()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.rejet_demande.emit()
            event.accept()
            return
        super().keyPressEvent(event)
