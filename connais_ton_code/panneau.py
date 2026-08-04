"""Le panneau accroché sous l'icône de la barre de menus.

Il ne connaît ni le détecteur, ni le sélecteur, ni l'évaluateur : il affiche
ce qu'on lui donne et signale ce que l'utilisateur demande. Toutes les
décisions appartiennent à l'orchestrateur.
"""

from __future__ import annotations

import sys

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
    SegmentedWidget,
    SmoothScrollArea,
    StrongBodyLabel,
    SwitchButton,
    TextEdit,
    TransparentToolButton,
)

from .apparence import (
    COULEUR_TEXTE_ATTENUE,
    configurer_panneau,
    style_panneau,
)
from .coloration import COULEUR_FOND_CODE, colorer
from .modeles import Evaluation, Extrait
from .statistiques import Statistiques
from .tableau_de_bord import TableauDeBord

LARGEUR = 620
HAUTEUR_QUESTION = 500
HAUTEUR_REPOS = 170
HAUTEUR_TABLEAU = 560

# Hauteur figée du bas du panneau, sinon la zone de code se redimensionne au
# moindre mot tapé et le regard perd sa place. Repos et Retour s'en écartent
# dans un sens ou dans l'autre : Repos n'a qu'un message et un bouton à poser,
# Retour est le seul à demander davantage, puisque c'est là que le texte à
# lire se trouve.
HAUTEUR_ZONE_REPOS = 70
HAUTEUR_ZONE_BASSE = 124
HAUTEUR_ZONE_RETOUR = 186

MARGE_ECRAN = 8

# Le panneau se décolle de la barre de menus comme le font les menus du
# système, sans plus.
ECART_SOUS_LA_BARRE = 6

_INDEX_REPOS = 0
_INDEX_SAISIE = 1
_INDEX_ATTENTE = 2
_INDEX_RETOUR = 3

# Identifiants des deux sections de la navigation d'entête.
_SECTION_QUESTION = "question"
_SECTION_TABLEAU = "tableau"


def _activer_application() -> None:
    """Passe l'application au premier plan avant de montrer le panneau.

    macOS efface les panneaux utilitaires des applications inactives : sans
    cette activation, le panneau s'ouvre et disparaît dans la même seconde.
    C'est aussi le comportement attendu, puisqu'on n'ouvre le panneau qu'à la
    suite d'un clic de l'utilisateur.
    """
    if sys.platform != "darwin":
        return
    try:
        from AppKit import NSApplication
    except ImportError:
        return
    NSApplication.sharedApplication().activateIgnoringOtherApps_(True)


class Panneau(QWidget):
    """Le panneau qui pose la question et recueille la réponse."""

    reponse_soumise = pyqtSignal(str)
    passage_demande = pyqtSignal()
    suite_demandee = pyqtSignal()
    question_demandee = pyqtSignal()
    tableau_demande = pyqtSignal()
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
        # Le cadre occupe toute la fenêtre : pas de marge autour, sinon elle
        # se voit comme une bande sombre au lieu de disparaître.
        exterieur.setContentsMargins(0, 0, 0, 0)

        self._cadre = QFrame(self)
        self._cadre.setObjectName("panneau")
        self._cadre.setStyleSheet(style_panneau())
        exterieur.addWidget(self._cadre)

        interieur = QVBoxLayout(self._cadre)
        # Marges resserrées : la largeur gagnée doit profiter à la zone de
        # code, pas à du vide sur les bords.
        interieur.setContentsMargins(10, 10, 10, 10)
        interieur.setSpacing(8)

        interieur.addLayout(self._construire_entete())
        self._localisation = self._construire_localisation()
        interieur.addWidget(self._localisation)
        interieur.addWidget(self._construire_zone_code(), stretch=1)
        interieur.addWidget(self._construire_zone_basse())
        self._defilement_tableau = self._construire_tableau()
        interieur.addWidget(self._defilement_tableau, stretch=1)
        interieur.addWidget(self._construire_pied())

        self._definir_section_active(_SECTION_QUESTION)

    def _construire_entete(self) -> QHBoxLayout:
        ligne = QHBoxLayout()
        ligne.setSpacing(8)
        ligne.addWidget(StrongBodyLabel("KnowYourCode", self._cadre))

        self._navigation = SegmentedWidget(self._cadre)
        self._navigation.addItem(_SECTION_QUESTION, "Question")
        self._navigation.addItem(_SECTION_TABLEAU, "Progression")
        self._navigation.currentItemChanged.connect(self._sur_changement_section)
        ligne.addWidget(self._navigation)

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

    def _construire_tableau(self) -> QWidget:
        # `TableauDeBord` a sa propre taille figée : la mettre dans une zone
        # de défilement évite qu'elle impose sa hauteur au panneau, exactement
        # comme `_defilement_retour` le fait déjà pour le verdict.
        self._tableau = TableauDeBord()
        defilement = SmoothScrollArea(self._cadre)
        defilement.setWidget(self._tableau)
        defilement.setWidgetResizable(False)
        defilement.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        defilement.setFrameShape(QFrame.Shape.NoFrame)
        defilement.setStyleSheet("QScrollArea, QWidget { background: transparent; }")
        defilement.viewport().setStyleSheet("background: transparent;")
        defilement.setVisible(False)
        return defilement

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
        """Retient la position de l'icône, sous laquelle s'ouvrir.

        Une icône qui vient d'être créée annonce une position aberrante,
        du genre `QRect(0, 1440, 38, 0)`, le temps que le système la place
        vraiment. Elle n'est pas nulle pour autant : c'est sa hauteur qu'il
        faut regarder, sinon le panneau s'ouvre hors de l'écran.
        """
        if not zone_icone.isEmpty():
            self._zone_ancrage = zone_icone

    def repositionner(self) -> None:
        """Replace le panneau, l'ancrage ayant pu changer depuis l'ouverture."""
        if self.isVisible():
            self._positionner()

    def afficher_repos(self, message: str) -> None:
        """Ouvre le panneau sans question en cours."""
        self._etiquette_etat.setText("")
        self._message_repos.setText(message)
        self._localisation.setVisible(False)
        self._zone_code.setVisible(False)
        self._pile.setVisible(True)
        self._pile.setFixedHeight(HAUTEUR_ZONE_REPOS)
        self._pile.setCurrentIndex(_INDEX_REPOS)
        self._defilement_tableau.setVisible(False)
        self._definir_section_active(_SECTION_QUESTION)
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
        self._pile.setVisible(True)
        self._defilement_tableau.setVisible(False)
        self._definir_section_active(_SECTION_QUESTION)

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

    def afficher_tableau_de_bord(self, statistiques: Statistiques) -> None:
        """Bascule sur la section Progression et l'ouvre à la bonne taille.

        La zone de code, la localisation et le bas de panneau propres à une
        question n'ont rien à faire ici : ils sont masqués, comme le fait déjà
        `afficher_repos` pour ses propres besoins.
        """
        self._etiquette_etat.setText("progression")
        self._tableau.afficher(statistiques)

        self._localisation.setVisible(False)
        self._zone_code.setVisible(False)
        self._pile.setVisible(False)
        self._defilement_tableau.setVisible(True)
        self._definir_section_active(_SECTION_TABLEAU)

        self._afficher(LARGEUR, HAUTEUR_TABLEAU)

    def definir_actif(self, actif: bool) -> None:
        """Met l'interrupteur à jour sans relancer le signal."""
        self._interrupteur.blockSignals(True)
        self._interrupteur.setChecked(actif)
        self._interrupteur.blockSignals(False)

    def _definir_section_active(self, section: str) -> None:
        """Aligne la navigation sur la section affichée, sans relancer le signal.

        Même précaution que `definir_actif` : cette méthode est aussi
        appelée depuis les méthodes `afficher_*`, quand c'est l'orchestrateur
        qui change d'état, et ne doit pas redemander ce qu'il vient de décider.
        """
        self._navigation.blockSignals(True)
        self._navigation.setCurrentItem(section)
        self._navigation.blockSignals(False)

    def _sur_changement_section(self, section: str) -> None:
        """Traduit le clic sur la navigation en simple demande, sans rien trancher."""
        if section == _SECTION_TABLEAU:
            self.tableau_demande.emit()
        else:
            self.question_demandee.emit()

    def fermer(self) -> None:
        """Referme le panneau, sans rien conserver de la saisie."""
        self._zone_reponse.clear()
        self.hide()

    # ------------------------------------------------------------------
    # Placement
    # ------------------------------------------------------------------

    def _afficher(self, largeur: int, hauteur: int) -> None:
        self.resize(largeur, hauteur)
        self._positionner()
        _activer_application()
        self.show()
        self.raise_()
        self.activateWindow()

    def _positionner(self) -> None:
        """Centre le panneau sous l'icône, sans déborder de l'écran."""
        ecran = QGuiApplication.primaryScreen()
        zone = ecran.availableGeometry() if ecran else QRect(0, 0, 1280, 800)

        if self._zone_ancrage.isEmpty():
            # Position de repli : le coin où vit l'icône, faute de savoir où
            # elle est exactement.
            self.move(
                zone.right() - self.width() - MARGE_ECRAN,
                zone.top() + ECART_SOUS_LA_BARRE,
            )
            return

        x = self._zone_ancrage.center().x() - self.width() // 2
        x = max(
            zone.left() + MARGE_ECRAN,
            min(x, zone.right() - self.width() - MARGE_ECRAN),
        )
        # `availableGeometry` commence déjà sous la barre de menus.
        self.move(x, zone.top() + ECART_SOUS_LA_BARRE)

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
