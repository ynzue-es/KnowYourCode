"""La fenêtre flottante et son affichage par état.

La fenêtre ne connaît ni le détecteur, ni le sélecteur, ni l'évaluateur : elle
affiche ce qu'on lui donne et signale ce que l'utilisateur demande. Toutes les
décisions appartiennent à l'orchestrateur.
"""

from __future__ import annotations

from PyQt6.QtCore import QPoint, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QKeyEvent, QKeySequence, QMouseEvent, QShortcut
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    FluentIcon,
    IndeterminateProgressRing,
    PlainTextEdit,
    PrimaryPushButton,
    PushButton,
    SmoothScrollArea,
    StrongBodyLabel,
    TextEdit,
    TransparentToolButton,
)

from .affichage import afficher_sans_activer, est_a_l_ecran, retirer_de_l_ecran
from .apparence import (
    COULEUR_TEXTE_ATTENUE,
    MARGE_OMBRE,
    configurer_fenetre_flottante,
    poser_ombre,
    style_panneau,
)
from .coloration import COULEUR_FOND_CODE, colorer
from .etats import Etat
from .modeles import Evaluation, Extrait

LARGEUR = 520
HAUTEUR = 400

# Hauteur figée du bas de la fenêtre, sinon la zone de code se redimensionne
# au moindre mot tapé et le regard perd sa place. L'état Retour est le seul à
# en demander davantage : c'est là que le texte à lire se trouve.
HAUTEUR_ZONE_BASSE = 124
HAUTEUR_ZONE_RETOUR = 186

_INDEX_SAISIE = 0
_INDEX_ATTENTE = 1
_INDEX_RETOUR = 2


class FenetreFlottante(QWidget):
    """Le panneau qui pose la question et recueille la réponse."""

    reponse_soumise = pyqtSignal(str)
    passage_demande = pyqtSignal()
    suite_demandee = pyqtSignal()
    masquage_demande = pyqtSignal()
    deplacee = pyqtSignal(int, int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        configurer_fenetre_flottante(self)
        self.setWindowTitle("KnowYourCode")
        self.resize(LARGEUR + 2 * MARGE_OMBRE, HAUTEUR + 2 * MARGE_OMBRE)

        self._origine_glissement: QPoint | None = None
        self._extrait_affiche: Extrait | None = None

        self._construire()
        self._brancher_raccourcis()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _construire(self) -> None:
        exterieur = QVBoxLayout(self)
        exterieur.setContentsMargins(
            MARGE_OMBRE, MARGE_OMBRE, MARGE_OMBRE, MARGE_OMBRE
        )

        self._panneau = QFrame(self)
        self._panneau.setObjectName("panneau")
        self._panneau.setStyleSheet(style_panneau())
        poser_ombre(self._panneau)
        exterieur.addWidget(self._panneau)

        interieur = QVBoxLayout(self._panneau)
        interieur.setContentsMargins(16, 10, 16, 12)
        interieur.setSpacing(8)

        interieur.addLayout(self._construire_entete())
        interieur.addLayout(self._construire_localisation())
        interieur.addWidget(self._construire_zone_code(), stretch=1)
        interieur.addWidget(self._construire_zone_basse())

    def _construire_entete(self) -> QHBoxLayout:
        ligne = QHBoxLayout()
        ligne.setSpacing(8)

        titre = StrongBodyLabel("KnowYourCode", self._panneau)
        ligne.addWidget(titre)

        self._etiquette_etat = CaptionLabel("", self._panneau)
        self._etiquette_etat.setStyleSheet(f"color: {COULEUR_TEXTE_ATTENUE};")
        ligne.addWidget(self._etiquette_etat)

        ligne.addStretch(1)

        self._bouton_fermer = TransparentToolButton(FluentIcon.CLOSE, self._panneau)
        self._bouton_fermer.setFixedSize(26, 26)
        self._bouton_fermer.setIconSize(QSize(9, 9))
        self._bouton_fermer.setToolTip("Masquer (Esc)")
        self._bouton_fermer.clicked.connect(self.masquage_demande.emit)
        ligne.addWidget(self._bouton_fermer)

        return ligne

    def _construire_localisation(self) -> QVBoxLayout:
        colonne = QVBoxLayout()
        colonne.setSpacing(1)

        self._etiquette_fichier = CaptionLabel("", self._panneau)
        self._etiquette_fichier.setStyleSheet(f"color: {COULEUR_TEXTE_ATTENUE};")
        colonne.addWidget(self._etiquette_fichier)

        self._etiquette_fonction = BodyLabel("", self._panneau)
        colonne.addWidget(self._etiquette_fonction)

        return colonne

    def _construire_zone_code(self) -> QWidget:
        self._zone_code = TextEdit(self._panneau)
        self._zone_code.setReadOnly(True)
        # Le code ne doit pas être replié : une ligne coupée au milieu change
        # la façon dont on la lit.
        self._zone_code.setLineWrapMode(TextEdit.LineWrapMode.NoWrap)
        self._zone_code.setMinimumHeight(90)
        self._zone_code.setStyleSheet(
            "QTextEdit { background-color: %s;"
            " border: 1px solid rgba(255, 255, 255, 0.08);"
            " border-radius: 6px; padding: 8px; }" % COULEUR_FOND_CODE
        )
        return self._zone_code

    def _construire_zone_basse(self) -> QWidget:
        self._pile = QStackedWidget(self._panneau)
        self._pile.setFixedHeight(HAUTEUR_ZONE_BASSE)
        self._pile.addWidget(self._construire_page_saisie())
        self._pile.addWidget(self._construire_page_attente())
        self._pile.addWidget(self._construire_page_retour())
        return self._pile

    def _construire_page_saisie(self) -> QWidget:
        page = QWidget(self._pile)
        colonne = QVBoxLayout(page)
        colonne.setContentsMargins(0, 0, 0, 0)
        colonne.setSpacing(8)

        self._zone_reponse = PlainTextEdit(page)
        self._zone_reponse.setPlaceholderText(
            "Explique ce que fait cette fonction, et pourquoi elle est écrite comme ça."
        )
        colonne.addWidget(self._zone_reponse, stretch=1)

        actions = QHBoxLayout()
        actions.setSpacing(8)

        rappel = CaptionLabel("Cmd + Entrée", page)
        rappel.setStyleSheet(f"color: {COULEUR_TEXTE_ATTENUE};")
        actions.addWidget(rappel)
        actions.addStretch(1)

        self._bouton_passer = PushButton("Passer", page)
        self._bouton_passer.clicked.connect(self.passage_demande.emit)
        actions.addWidget(self._bouton_passer)

        self._bouton_repondre = PrimaryPushButton("Répondre", page)
        self._bouton_repondre.clicked.connect(self._soumettre)
        actions.addWidget(self._bouton_repondre)

        colonne.addLayout(actions)
        return page

    def _construire_page_attente(self) -> QWidget:
        page = QWidget(self._pile)
        colonne = QVBoxLayout(page)
        colonne.setContentsMargins(0, 0, 0, 0)
        colonne.addStretch(1)

        ligne = QHBoxLayout()
        ligne.setSpacing(10)
        ligne.addStretch(1)

        anneau = IndeterminateProgressRing(page)
        anneau.setFixedSize(22, 22)
        anneau.setStrokeWidth(3)
        ligne.addWidget(anneau)

        ligne.addWidget(BodyLabel("Évaluation en cours", page))
        ligne.addStretch(1)

        colonne.addLayout(ligne)
        colonne.addStretch(1)
        return page

    def _construire_page_retour(self) -> QWidget:
        page = QWidget(self._pile)
        colonne = QVBoxLayout(page)
        colonne.setContentsMargins(0, 0, 0, 0)
        colonne.setSpacing(8)

        self._contenu_retour = QWidget()
        self._colonne_retour = QVBoxLayout(self._contenu_retour)
        self._colonne_retour.setContentsMargins(0, 0, 8, 0)
        self._colonne_retour.setSpacing(6)
        self._colonne_retour.addStretch(1)

        self._defilement_retour = SmoothScrollArea(page)
        self._defilement_retour.setWidget(self._contenu_retour)
        self._defilement_retour.setWidgetResizable(True)
        self._defilement_retour.setFrameShape(QFrame.Shape.NoFrame)
        self._defilement_retour.setStyleSheet("QScrollArea, QWidget { background: transparent; }")
        self._defilement_retour.viewport().setStyleSheet("background: transparent;")
        colonne.addWidget(self._defilement_retour, stretch=1)

        actions = QHBoxLayout()
        self._etiquette_score = CaptionLabel("", page)
        self._etiquette_score.setStyleSheet(f"color: {COULEUR_TEXTE_ATTENUE};")
        actions.addWidget(self._etiquette_score)
        actions.addStretch(1)

        self._bouton_suivant = PrimaryPushButton("Suivant", page)
        self._bouton_suivant.clicked.connect(self.suite_demandee.emit)
        actions.addWidget(self._bouton_suivant)

        colonne.addLayout(actions)
        return page

    def _brancher_raccourcis(self) -> None:
        # Sur macOS, Qt fait déjà correspondre Ctrl à la touche Cmd.
        for sequence in ("Ctrl+Return", "Ctrl+Enter"):
            raccourci = QShortcut(QKeySequence(sequence), self)
            raccourci.setContext(Qt.ShortcutContext.WindowShortcut)
            raccourci.activated.connect(self._soumettre)

    # ------------------------------------------------------------------
    # Affichage par état
    # ------------------------------------------------------------------

    def afficher_question(self, extrait: Extrait) -> None:
        """Passe en état Question avec un nouvel extrait."""
        self._extrait_affiche = extrait
        self._etiquette_etat.setText("question")
        self._etiquette_fichier.setText(extrait.chemin_fichier)
        self._etiquette_fonction.setText(extrait.nom_fonction)
        self._zone_code.setHtml(colorer(extrait.code, extrait.langage))
        self._zone_code.verticalScrollBar().setValue(0)

        self._zone_reponse.clear()
        self._zone_reponse.setReadOnly(False)
        self._bouton_repondre.setEnabled(True)
        self._bouton_passer.setEnabled(True)
        self._pile.setFixedHeight(HAUTEUR_ZONE_BASSE)
        self._pile.setCurrentIndex(_INDEX_SAISIE)

        self.afficher_sans_voler_le_focus()

    def afficher_attente(self) -> None:
        """Passe en état Évaluation, sans rien bloquer d'autre."""
        self._etiquette_etat.setText("évaluation")
        self._pile.setCurrentIndex(_INDEX_ATTENTE)

    def afficher_retour(self, evaluation: Evaluation) -> None:
        """Passe en état Retour et remplit le verdict."""
        self._etiquette_etat.setText("retour")
        self._vider_retour()

        verdict = BodyLabel(evaluation.verdict, self._contenu_retour)
        verdict.setWordWrap(True)
        self._colonne_retour.insertWidget(0, verdict)

        position = 1
        if evaluation.points_oublies:
            titre = CaptionLabel("Ce que tu as oublié", self._contenu_retour)
            titre.setStyleSheet(f"color: {COULEUR_TEXTE_ATTENUE};")
            self._colonne_retour.insertWidget(position, titre)
            position += 1

            for point in evaluation.points_oublies:
                ligne = BodyLabel(f"•  {point}", self._contenu_retour)
                ligne.setWordWrap(True)
                self._colonne_retour.insertWidget(position, ligne)
                position += 1

        self._etiquette_score.setText(f"{evaluation.score} / 100")
        self._pile.setFixedHeight(HAUTEUR_ZONE_RETOUR)
        self._pile.setCurrentIndex(_INDEX_RETOUR)

    def masquer(self) -> None:
        """Retour à l'état Masquée, sans rien conserver de la saisie."""
        self._zone_reponse.clear()
        retirer_de_l_ecran(self)

    def afficher_sans_voler_le_focus(self) -> None:
        """Montre la fenêtre en laissant le clavier là où il est.

        Ni `activateWindow` ni `setFocus` ici : c'est tout l'intérêt de la
        fenêtre.
        """
        afficher_sans_activer(self)

    def etat_affiche(self) -> Etat:
        """Rend l'état déduit de ce qui est actuellement à l'écran."""
        if not est_a_l_ecran(self):
            return Etat.MASQUEE
        index = self._pile.currentIndex()
        if index == _INDEX_ATTENTE:
            return Etat.EVALUATION
        if index == _INDEX_RETOUR:
            return Etat.RETOUR
        return Etat.QUESTION

    def _vider_retour(self) -> None:
        while self._colonne_retour.count() > 1:
            element = self._colonne_retour.takeAt(0)
            widget = element.widget()
            if widget is not None:
                widget.deleteLater()

    def _soumettre(self) -> None:
        if self._pile.currentIndex() != _INDEX_SAISIE:
            return
        self._bouton_repondre.setEnabled(False)
        self._bouton_passer.setEnabled(False)
        self._zone_reponse.setReadOnly(True)
        self.reponse_soumise.emit(self._zone_reponse.toPlainText())

    # ------------------------------------------------------------------
    # Déplacement et clavier
    # ------------------------------------------------------------------

    def position_panneau(self) -> tuple[int, int]:
        """Position à mémoriser : celle de la fenêtre, marge d'ombre comprise."""
        point = self.pos()
        return point.x(), point.y()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        # Les widgets interactifs consomment le clic ; ce qui arrive ici vient
        # du fond du panneau, donc c'est une intention de déplacement.
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
            x, y = self.position_panneau()
            self.deplacee.emit(x, y)
            event.accept()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.masquage_demande.emit()
            event.accept()
            return
        super().keyPressEvent(event)
