"""La grande fenêtre, au centre de l'écran, pour prendre du recul.

Le panneau de la barre de menus sert à l'exercice, rien d'autre : on y répond
en trente secondes et on retourne travailler. Regarder sa progression ou
changer un réglage n'a rien à y faire, ce sont des gestes qu'on pose en
s'arrêtant. D'où cette fenêtre ordinaire, avec sa barre de titre et sa barre
latérale, qu'on ouvre quand on a le temps.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    StrongBodyLabel,
    SubtitleLabel,
    SwitchButton,
    TransparentPushButton,
)

from .apparence import COULEUR_ACCENT, COULEUR_TEXTE_ATTENUE
from .logo import pixmap_marque
from .rappel import chemin_phrases
from .statistiques import Statistiques
from .tableau_de_bord import TableauDeBord

LARGEUR = 900
HAUTEUR = 660

LARGEUR_BARRE_LATERALE = 190

_INDEX_PROGRESSION = 0
_INDEX_REGLAGES = 1

_COULEUR_FOND = "#141519"
_COULEUR_BARRE = "#1b1c20"


class FenetrePrincipale(QWidget):
    """Progression et réglages, dans une fenêtre classique."""

    rappel_change = pyqtSignal(bool)
    reveil_change = pyqtSignal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("KnowYourCode")
        self.resize(LARGEUR, HAUTEUR)
        self.setMinimumSize(720, 520)
        self.setStyleSheet(f"background-color: {_COULEUR_FOND};")

        self._construire()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _construire(self) -> None:
        ligne = QHBoxLayout(self)
        ligne.setContentsMargins(0, 0, 0, 0)
        ligne.setSpacing(0)

        ligne.addWidget(self._construire_barre_laterale())

        self._pages = QStackedWidget(self)
        self._pages.addWidget(self._construire_progression())
        self._pages.addWidget(self._construire_reglages())
        ligne.addWidget(self._pages, stretch=1)

        self._choisir_page(_INDEX_PROGRESSION)

    def _construire_barre_laterale(self) -> QWidget:
        barre = QFrame(self)
        barre.setObjectName("barreLaterale")
        barre.setFixedWidth(LARGEUR_BARRE_LATERALE)
        barre.setStyleSheet(
            f"#barreLaterale {{ background-color: {_COULEUR_BARRE};"
            f" border-right: 1px solid rgba(255, 255, 255, 0.06); }}"
        )

        colonne = QVBoxLayout(barre)
        colonne.setContentsMargins(16, 22, 16, 16)
        colonne.setSpacing(4)

        entete = QHBoxLayout()
        entete.setSpacing(8)
        logo = QLabel(barre)
        logo.setPixmap(pixmap_marque(18))
        entete.addWidget(logo)
        entete.addWidget(StrongBodyLabel("KnowYourCode", barre))
        entete.addStretch(1)
        colonne.addLayout(entete)
        colonne.addSpacing(18)

        self._boutons: list[TransparentPushButton] = []
        for index, libelle in (
            (_INDEX_PROGRESSION, "Progression"),
            (_INDEX_REGLAGES, "Réglages"),
        ):
            bouton = TransparentPushButton(libelle, barre)
            bouton.setFixedHeight(34)
            bouton.clicked.connect(lambda _, i=index: self._choisir_page(i))
            colonne.addWidget(bouton)
            self._boutons.append(bouton)

        colonne.addStretch(1)
        return barre

    def _construire_progression(self) -> QWidget:
        page = QWidget(self)
        colonne = QVBoxLayout(page)
        colonne.setContentsMargins(24, 22, 24, 22)
        colonne.setSpacing(14)

        colonne.addWidget(SubtitleLabel("Progression", page))
        self._tableau = TableauDeBord(page)
        colonne.addWidget(self._tableau, stretch=1)
        return page

    def _construire_reglages(self) -> QWidget:
        page = QWidget(self)
        colonne = QVBoxLayout(page)
        colonne.setContentsMargins(24, 22, 24, 22)
        colonne.setSpacing(10)

        colonne.addWidget(SubtitleLabel("Réglages", page))
        colonne.addSpacing(6)

        colonne.addWidget(StrongBodyLabel("Rappel dans Claude Code", page))

        explication = BodyLabel(
            "Remplace les mots du compteur d'attente de Claude Code par des "
            "rappels KnowYourCode. Éteint, Claude Code retrouve les siens.",
            page,
        )
        explication.setWordWrap(True)
        colonne.addWidget(explication)

        self._interrupteur = SwitchButton(page)
        self._interrupteur.setOnText("Rappels KnowYourCode")
        self._interrupteur.setOffText("Compteur d'origine")
        self._interrupteur.checkedChanged.connect(self.rappel_change.emit)
        colonne.addWidget(self._interrupteur)

        for texte in (
            "Redémarrez Claude Code pour voir le changement.",
            f"Vos propres phrases : {chemin_phrases()}",
        ):
            note = CaptionLabel(texte, page)
            note.setStyleSheet(f"color: {COULEUR_TEXTE_ATTENUE};")
            note.setWordWrap(True)
            colonne.addWidget(note)

        colonne.addSpacing(18)
        colonne.addWidget(StrongBodyLabel("Ouverture automatique", page))

        explication_reveil = BodyLabel(
            "Ouvre le panneau quand vous envoyez un prompt à Claude Code, "
            "c'est-à-dire au moment où vous alliez attendre. Rien ne s'ouvre "
            "si la série du jour est déjà faite.",
            page,
        )
        explication_reveil.setWordWrap(True)
        colonne.addWidget(explication_reveil)

        self._interrupteur_reveil = SwitchButton(page)
        self._interrupteur_reveil.setOnText("S'ouvre avec Claude Code")
        self._interrupteur_reveil.setOffText("S'ouvre sur demande")
        self._interrupteur_reveil.checkedChanged.connect(self.reveil_change.emit)
        colonne.addWidget(self._interrupteur_reveil)

        note_reveil = CaptionLabel(
            "Lit le journal de session que Claude Code tient dans "
            "~/.claude/projects. Rien n'est installé, rien à redémarrer.",
            page,
        )
        note_reveil.setStyleSheet(f"color: {COULEUR_TEXTE_ATTENUE};")
        note_reveil.setWordWrap(True)
        colonne.addWidget(note_reveil)

        colonne.addStretch(1)
        return page

    # ------------------------------------------------------------------
    # Affichage
    # ------------------------------------------------------------------

    def _choisir_page(self, index: int) -> None:
        self._pages.setCurrentIndex(index)
        for numero, bouton in enumerate(self._boutons):
            actif = numero == index
            # Le composant transparent ne marque pas l'entrée courante : sans
            # ce fond, on ne sait pas sur quelle page on se trouve.
            fond = "rgba(255, 255, 255, 0.08)" if actif else "transparent"
            couleur = COULEUR_ACCENT if actif else "#d7d9dd"
            bouton.setStyleSheet(
                "TransparentPushButton {"
                f" background-color: {fond}; color: {couleur};"
                " border: none; border-radius: 6px;"
                " padding-left: 10px; text-align: left; }"
                "TransparentPushButton:hover {"
                " background-color: rgba(255, 255, 255, 0.12); }"
            )

    def afficher(self, statistiques: Statistiques) -> None:
        """Remplit la progression et montre la fenêtre, centrée."""
        self._tableau.afficher(statistiques)
        self._centrer()
        self.show()
        self.raise_()
        self.activateWindow()

    def definir_couverture(self, couverture) -> None:
        """Pose la mesure du projet, qui arrive après l'affichage."""
        self._tableau.definir_couverture(couverture)

    def definir_rappel(self, installe: bool) -> None:
        """Aligne l'interrupteur sur l'état réel, sans relancer le signal.

        Les réglages de Claude Code ont pu changer pendant que la fenêtre
        était fermée : c'est le fichier qui fait foi.
        """
        self._interrupteur.blockSignals(True)
        self._interrupteur.setChecked(installe)
        self._interrupteur.blockSignals(False)

    def definir_reveil(self, installe: bool) -> None:
        """Aligne l'interrupteur d'ouverture automatique sur le fichier de hooks."""
        self._interrupteur_reveil.blockSignals(True)
        self._interrupteur_reveil.setChecked(installe)
        self._interrupteur_reveil.blockSignals(False)

    def _centrer(self) -> None:
        ecran = QGuiApplication.primaryScreen()
        if ecran is None:
            return
        zone = ecran.availableGeometry()
        self.move(
            zone.center().x() - self.width() // 2,
            zone.center().y() - self.height() // 2,
        )

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.close()
            event.accept()
            return
        super().keyPressEvent(event)
