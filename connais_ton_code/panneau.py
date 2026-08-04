"""Le panneau accroché sous l'icône de la barre de menus.

Il ne connaît ni le détecteur, ni le sélecteur, ni l'évaluateur : il affiche
ce qu'on lui donne et signale ce que l'utilisateur demande. Toutes les
décisions appartiennent à l'orchestrateur.
"""

from __future__ import annotations

from PyQt6.QtCore import QRect, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QGuiApplication, QHideEvent, QKeyEvent, QKeySequence, QShortcut
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
    SwitchButton,
    TextEdit,
    TransparentToolButton,
)

from .apparence import (
    COULEUR_TEXTE_ATTENUE,
    MARGE_OMBRE,
    configurer_panneau,
    poser_ombre,
    style_panneau,
)
from .coloration import COULEUR_FOND_CODE, colorer
from .modeles import Evaluation, Extrait

LARGEUR = 520
HAUTEUR_QUESTION = 430
HAUTEUR_REPOS = 150

# Hauteur figée du bas du panneau, sinon la zone de code se redimensionne au
# moindre mot tapé et le regard perd sa place. L'état Retour est le seul à en
# demander davantage : c'est là que le texte à lire se trouve.
HAUTEUR_ZONE_BASSE = 124
HAUTEUR_ZONE_RETOUR = 186

MARGE_ECRAN = 8

_INDEX_REPOS = 0
_INDEX_SAISIE = 1
_INDEX_ATTENTE = 2
_INDEX_RETOUR = 3


class Panneau(QWidget):
    """Le panneau qui pose la question et recueille la réponse."""

    reponse_soumise = pyqtSignal(str)
    passage_demande = pyqtSignal()
    suite_demandee = pyqtSignal()
    question_demandee = pyqtSignal()
    fermeture_demandee = pyqtSignal()
    activation_changee = pyqtSignal(bool)
    sortie_demandee = pyqtSignal()
    masque = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        configurer_panneau(self)
        self.setWindowTitle("KnowYourCode")

        self._zone_ancrage = QRect()
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

        self._cadre = QFrame(self)
        self._cadre.setObjectName("panneau")
        self._cadre.setStyleSheet(style_panneau())
        poser_ombre(self._cadre)
        exterieur.addWidget(self._cadre)

        interieur = QVBoxLayout(self._cadre)
        interieur.setContentsMargins(16, 10, 16, 10)
        interieur.setSpacing(8)

        interieur.addLayout(self._construire_entete())
        self._localisation = self._construire_localisation()
        interieur.addWidget(self._localisation)
        interieur.addWidget(self._construire_zone_code(), stretch=1)
        interieur.addWidget(self._construire_zone_basse())
        interieur.addWidget(self._construire_pied())

    def _construire_entete(self) -> QHBoxLayout:
        ligne = QHBoxLayout()
        ligne.setSpacing(8)
        ligne.addWidget(StrongBodyLabel("KnowYourCode", self._cadre))

        self._etiquette_etat = CaptionLabel("", self._cadre)
        self._etiquette_etat.setStyleSheet(f"color: {COULEUR_TEXTE_ATTENUE};")
        ligne.addWidget(self._etiquette_etat)
        ligne.addStretch(1)

        fermer = TransparentToolButton(FluentIcon.CLOSE, self._cadre)
        fermer.setFixedSize(26, 26)
        fermer.setIconSize(QSize(9, 9))
        fermer.setToolTip("Fermer (Esc)")
        fermer.clicked.connect(self.fermeture_demandee.emit)
        ligne.addWidget(fermer)
        return ligne

    def _construire_localisation(self) -> QWidget:
        bloc = QWidget(self._cadre)
        colonne = QVBoxLayout(bloc)
        colonne.setContentsMargins(0, 0, 0, 0)
        colonne.setSpacing(1)

        self._etiquette_fichier = CaptionLabel("", bloc)
        self._etiquette_fichier.setStyleSheet(f"color: {COULEUR_TEXTE_ATTENUE};")
        colonne.addWidget(self._etiquette_fichier)

        self._etiquette_fonction = BodyLabel("", bloc)
        colonne.addWidget(self._etiquette_fonction)
        return bloc

    def _construire_zone_code(self) -> QWidget:
        self._zone_code = TextEdit(self._cadre)
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
        self._pile = QStackedWidget(self._cadre)
        self._pile.setFixedHeight(HAUTEUR_ZONE_BASSE)
        self._pile.addWidget(self._construire_page_repos())
        self._pile.addWidget(self._construire_page_saisie())
        self._pile.addWidget(self._construire_page_attente())
        self._pile.addWidget(self._construire_page_retour())
        return self._pile

    def _construire_page_repos(self) -> QWidget:
        page = QWidget(self._pile)
        colonne = QVBoxLayout(page)
        colonne.setContentsMargins(0, 0, 0, 0)
        colonne.setSpacing(8)
        colonne.addStretch(1)

        self._message_repos = BodyLabel("", page)
        self._message_repos.setWordWrap(True)
        colonne.addWidget(self._message_repos)

        bouton = PrimaryPushButton("Poser une question", page)
        bouton.clicked.connect(self.question_demandee.emit)
        colonne.addWidget(bouton)
        colonne.addStretch(1)
        return page

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
        self._defilement_retour.setStyleSheet(
            "QScrollArea, QWidget { background: transparent; }"
        )
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

    def _construire_pied(self) -> QWidget:
        pied = QWidget(self._cadre)
        pied.setStyleSheet("border-top: 1px solid rgba(255, 255, 255, 0.07);")

        ligne = QHBoxLayout(pied)
        ligne.setContentsMargins(0, 6, 0, 0)
        ligne.setSpacing(8)

        self._interrupteur = SwitchButton(pied)
        self._interrupteur.setOnText("Détection active")
        self._interrupteur.setOffText("Détection en pause")
        self._interrupteur.checkedChanged.connect(self.activation_changee.emit)
        ligne.addWidget(self._interrupteur)
        ligne.addStretch(1)

        quitter = TransparentToolButton(FluentIcon.POWER_BUTTON, pied)
        quitter.setFixedSize(26, 26)
        quitter.setIconSize(QSize(12, 12))
        quitter.setToolTip("Quitter KnowYourCode")
        quitter.clicked.connect(self.sortie_demandee.emit)
        ligne.addWidget(quitter)
        return pied

    def _brancher_raccourcis(self) -> None:
        # Sur macOS, Qt fait déjà correspondre Ctrl à la touche Cmd.
        for sequence in ("Ctrl+Return", "Ctrl+Enter"):
            raccourci = QShortcut(QKeySequence(sequence), self)
            raccourci.setContext(Qt.ShortcutContext.WindowShortcut)
            raccourci.activated.connect(self._soumettre)

    # ------------------------------------------------------------------
    # Affichage par état
    # ------------------------------------------------------------------

    def ancrer(self, zone_icone: QRect) -> None:
        """Retient la position de l'icône, sous laquelle s'ouvrir."""
        if not zone_icone.isNull():
            self._zone_ancrage = zone_icone

    def afficher_repos(self, message: str) -> None:
        """Ouvre le panneau sans question en cours."""
        self._etiquette_etat.setText("")
        self._message_repos.setText(message)
        self._localisation.setVisible(False)
        self._zone_code.setVisible(False)
        self._pile.setFixedHeight(HAUTEUR_ZONE_BASSE)
        self._pile.setCurrentIndex(_INDEX_REPOS)
        self._afficher(LARGEUR, HAUTEUR_REPOS)

    def afficher_question(self, extrait: Extrait) -> None:
        """Ouvre le panneau sur un nouvel extrait."""
        self._etiquette_etat.setText("question")
        self._etiquette_fichier.setText(extrait.chemin_fichier)
        self._etiquette_fonction.setText(extrait.nom_fonction)
        self._zone_code.setHtml(colorer(extrait.code, extrait.langage))
        self._zone_code.verticalScrollBar().setValue(0)

        self._localisation.setVisible(True)
        self._zone_code.setVisible(True)

        self._zone_reponse.clear()
        self._zone_reponse.setReadOnly(False)
        self._bouton_repondre.setEnabled(True)
        self._bouton_passer.setEnabled(True)
        self._pile.setFixedHeight(HAUTEUR_ZONE_BASSE)
        self._pile.setCurrentIndex(_INDEX_SAISIE)

        self._afficher(LARGEUR, HAUTEUR_QUESTION)
        self._zone_reponse.setFocus()

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

    def definir_actif(self, actif: bool) -> None:
        """Met l'interrupteur à jour sans relancer le signal."""
        self._interrupteur.blockSignals(True)
        self._interrupteur.setChecked(actif)
        self._interrupteur.blockSignals(False)

    def fermer(self) -> None:
        """Referme le panneau, sans rien conserver de la saisie."""
        self._zone_reponse.clear()
        self.hide()

    # ------------------------------------------------------------------
    # Placement
    # ------------------------------------------------------------------

    def _afficher(self, largeur: int, hauteur: int) -> None:
        self.resize(largeur + 2 * MARGE_OMBRE, hauteur + 2 * MARGE_OMBRE)
        self._positionner()
        self.show()
        self.raise_()
        self.activateWindow()

    def _positionner(self) -> None:
        """Centre le panneau sous l'icône, sans déborder de l'écran."""
        ecran = QGuiApplication.primaryScreen()
        zone = ecran.availableGeometry() if ecran else QRect(0, 0, 1280, 800)

        if self._zone_ancrage.isNull():
            self.move(zone.right() - self.width(), zone.top())
            return

        x = self._zone_ancrage.center().x() - self.width() // 2
        x = max(
            zone.left() + MARGE_ECRAN - MARGE_OMBRE,
            min(x, zone.right() - self.width() - MARGE_ECRAN + MARGE_OMBRE),
        )
        # `availableGeometry` commence déjà sous la barre de menus : la marge
        # d'ombre suffit à décoller le panneau du bord.
        self.move(x, zone.top() - MARGE_OMBRE + 2)

    # ------------------------------------------------------------------
    # Interactions
    # ------------------------------------------------------------------

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

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.fermeture_demandee.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    def hideEvent(self, event: QHideEvent) -> None:
        # macOS efface les panneaux utilitaires quand l'application passe en
        # arrière-plan. L'orchestrateur doit l'apprendre, sinon il croirait le
        # panneau encore ouvert.
        super().hideEvent(event)
        self.masque.emit()
