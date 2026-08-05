"""Le panneau accroché sous l'icône de la barre de menus.

Il ne connaît ni le repérage, ni le sélecteur, ni le générateur de cartes : il
pose la carte qu'on lui donne, montre la correction qu'on lui donne, et signale
ce que l'utilisateur demande. Toutes les décisions appartiennent à
l'orchestrateur.
"""

from __future__ import annotations

import sys

from PyQt6.QtCore import QRect, QSize, Qt, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QGuiApplication,
    QHideEvent,
    QIcon,
    QKeyEvent,
    QMouseEvent,
    QTextCursor,
    QTextFormat,
)
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    FluentIcon,
    LineEdit,
    PrimaryPushButton,
    PushButton,
    SmoothScrollArea,
    StrongBodyLabel,
    TextEdit,
    TransparentToolButton,
)

from .apparence import (
    COULEUR_TEXTE_ATTENUE,
    configurer_panneau,
    style_panneau,
)
from .cartes import Carte, Correction, Forme
from .coloration import (
    COULEUR_FOND_CODE,
    COULEUR_TEXTE_CODE,
    POLICE_CODE,
    colorer,
)
from .logo import pixmap_marque
from .modeles import Extrait

# Le panneau tenait en 620 × 520 du temps où l'on tapait une explication : le
# code était un décor qu'on survolait. Maintenant qu'il faut le lire ligne à
# ligne pour répondre — et cliquer dedans, sur les cartes « repérer » — il
# devient le sujet, et la place lui revient. 760 laisse passer une ligne de
# quatre-vingts caractères sans défilement horizontal, largeur au-delà de
# laquelle plus personne n'écrit.
LARGEUR = 760
HAUTEUR_MANCHE = 640
HAUTEUR_REPOS = 170
HAUTEUR_BILAN = 210

MARGE_ECRAN = 8

# Le plancher au-delà duquel on cesse de rétrécir pour tenir dans un petit
# écran : en dessous, les blocs à hauteur fixe se recouvrent et la carte
# devient illisible. Mieux vaut alors déborder un peu que ne rien montrer.
HAUTEUR_MINIMALE = 400

# Le panneau se décolle de la barre de menus comme le font les menus du
# système, sans plus.
ECART_SOUS_LA_BARRE = 6

# Hauteur figée du bas du panneau : la carte et sa correction se succèdent sur
# le même extrait, et si la zone de code changeait de taille entre les deux, le
# regard perdrait sa place au moment précis où il doit relire. Seuls Repos et
# Bilan s'en écartent, puisqu'ils n'affichent pas de code du tout.
# Les propositions se répondent à la souris et se lisent d'un regard : serrées,
# on hésite sur celle qu'on vise, et deux libellés qui se touchent se lisent
# comme une seule phrase coupée. Un bouton confortable fait 36 pixels ; deux
# rangées et leur écart en demandent donc 80.
HAUTEUR_BOUTON_OPTION = 36
ECART_OPTIONS = 8
ECART_OPTIONS_HORIZONTAL = 14
HAUTEUR_ZONE_OPTIONS = 2 * HAUTEUR_BOUTON_OPTION + ECART_OPTIONS

HAUTEUR_ZONE_REPOS = 70
HAUTEUR_ZONE_CARTE = 160
HAUTEUR_ZONE_CORRECTION = 214
HAUTEUR_ZONE_BILAN = 104

# D'où la hauteur de la fenêtre en correction : ce que le bas gagne, la
# fenêtre le prend, au lieu de le retirer au code.
HAUTEUR_CORRECTION = HAUTEUR_MANCHE + HAUTEUR_ZONE_CORRECTION - HAUTEUR_ZONE_CARTE

COULEUR_JUSTE = "#4ec9a0"
COULEUR_FAUX = "#ff7b72"
COULEUR_NUMERO_LIGNE = "#575d66"

# La ligne visée se pose en fond derrière le code : un cadre ou une flèche
# vaudrait désignation, et on veut que l'œil y arrive en lisant, pas qu'il y
# soit envoyé.
FOND_LIGNE_VISEE = QColor(76, 141, 255, 46)

_INDEX_REPOS = 0
_INDEX_CARTE = 1
_INDEX_CORRECTION = 2
_INDEX_BILAN = 3

# Deux colonnes : quatre propositions à la file mangeraient la hauteur de la
# zone de code, qui reste ce qu'on est venu lire.
_COLONNES_QCM = 2


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


def _decouper_en_lignes(corps: str) -> list[str]:
    """Coupe le HTML de Pygments en une entrée par ligne source.

    Une chaîne ou un commentaire sur plusieurs lignes tient dans une seule
    balise, qui enjambe donc les retours : couper naïvement sur `\\n` rendrait
    des lignes au balisage déséquilibré, que Qt affiche n'importe comment. On
    referme donc les balises ouvertes en fin de ligne et on les rouvre à la
    suivante. Pygments n'émet que des `<span>`, ce qui rend la refermeture
    triviale.
    """
    lignes: list[str] = []
    ouvertes: list[str] = []
    courante: list[str] = []

    position = 0
    while position < len(corps):
        caractere = corps[position]
        if caractere == "<":
            fin = corps.find(">", position)
            if fin == -1:
                courante.append(corps[position:])
                break
            balise = corps[position : fin + 1]
            if balise.startswith("</"):
                if ouvertes:
                    ouvertes.pop()
            elif not balise.endswith("/>"):
                ouvertes.append(balise)
            courante.append(balise)
            position = fin + 1
        elif caractere == "\n":
            courante.append("</span>" * len(ouvertes))
            lignes.append("".join(courante))
            courante = list(ouvertes)
            position += 1
        else:
            courante.append(caractere)
            position += 1

    courante.append("</span>" * len(ouvertes))
    lignes.append("".join(courante))

    # Pygments termine son rendu par un retour à la ligne : sans ce retrait,
    # chaque extrait gagnerait une ligne vide numérotée.
    if len(lignes) > 1 and not lignes[-1].strip():
        lignes.pop()
    return lignes


def _code_numerote(code: str, langage: str) -> str:
    """Rend le code coloré, une ligne par bloc, précédé de son numéro.

    Les numéros sont indispensables : ce sont eux qui permettent à une carte de
    dire « ligne 7 », et à une réponse d'être un clic. Ils font partie du texte
    plutôt que d'une marge peinte à côté, pour qu'un bloc de document
    corresponde exactement à une ligne source — c'est ce qui rend le clic
    lisible sans calcul de coordonnées.
    """
    entier = colorer(code, langage)
    debut = entier.find(">") + 1
    lignes = _decouper_en_lignes(entier[debut : entier.rfind("</pre>")])

    largeur = len(str(len(lignes)))
    corps = "\n".join(
        f'<span style="color:{COULEUR_NUMERO_LIGNE};">'
        f"{str(numero).rjust(largeur).replace(' ', '&nbsp;')}</span>"
        f"&nbsp;&nbsp;{ligne}"
        for numero, ligne in enumerate(lignes, start=1)
    )
    return (
        # Treize plutôt que douze : un point de plus ne change rien à ce qui
        # tient à l'écran maintenant que le panneau est plus large, et beaucoup
        # à la fatigue de qui relit une ligne pour la troisième fois.
        f'<pre style="font-family:{POLICE_CODE}; font-size:13px;'
        f" line-height:155%; color:{COULEUR_TEXTE_CODE};"
        f' white-space:pre; margin:0;">{corps}</pre>'
    )


class ZoneCode(TextEdit):
    """Le bloc de code : numéroté, et souligné sur la ligne en question."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
        # Le code ne doit pas être replié : une ligne coupée au milieu change
        # la façon dont on la lit, et fausserait la numérotation.
        self.setLineWrapMode(TextEdit.LineWrapMode.NoWrap)
        self.setMinimumHeight(90)
        self.setStyleSheet(
            "QTextEdit { background-color: %s;"
            " border: 1px solid rgba(255, 255, 255, 0.08);"
            " border-radius: 6px; padding: 8px; }" % COULEUR_FOND_CODE
        )

        self._ligne_visee = 0

    def montrer(self, code: str, langage: str, ligne: int) -> None:
        """Affiche l'extrait en soulignant la ligne sur laquelle on interroge."""
        self.setHtml(_code_numerote(code, langage))
        self._ligne_visee = ligne
        self._souligner()
        self._amener_en_vue(ligne)

    def _amener_en_vue(self, ligne: int) -> None:
        """Remonte en haut de l'extrait, et ne descend que s'il le faut.

        Un extrait qui tient tout entier dans la zone ne doit pas bouger d'un
        cran : une première ligne coupée en haut se lit comme du code manquant.
        """
        self.verticalScrollBar().setValue(0)
        self.horizontalScrollBar().setValue(0)
        if ligne <= 0 or self.verticalScrollBar().maximum() == 0:
            return

        bloc = self.document().findBlockByNumber(ligne - 1)
        if not bloc.isValid():
            return
        self.setTextCursor(QTextCursor(bloc))
        self.ensureCursorVisible()
        self.horizontalScrollBar().setValue(0)

    def _souligner(self) -> None:
        bande = self._bande(self._ligne_visee, FOND_LIGNE_VISEE)
        self.setExtraSelections([bande] if bande is not None else [])

    def _bande(self, ligne: int, couleur: QColor) -> QTextEdit.ExtraSelection | None:
        """Peint une ligne entière en fond, bord à bord."""
        if ligne <= 0:
            return None
        bloc = self.document().findBlockByNumber(ligne - 1)
        if not bloc.isValid():
            return None

        selection = QTextEdit.ExtraSelection()
        selection.format.setBackground(couleur)
        # Sans cette propriété, le fond s'arrête au dernier caractère et la
        # bande a la forme dentelée du code.
        selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
        curseur = QTextCursor(bloc)
        curseur.clearSelection()
        selection.cursor = curseur
        return selection


# L'épaisseur de la bande, en haut de l'écran, où peut vivre une icône de barre
# de menus. Large : la barre grossit avec l'encoche des portables récents.
BANDE_BARRE_DE_MENUS = 80


def _ancrage_credible(zone_icone: QRect) -> bool:
    """Dit si cette position peut être celle d'une icône de barre de menus."""
    if zone_icone.isEmpty():
        return False

    ecran = QGuiApplication.screenAt(zone_icone.center())
    if ecran is None:
        return False

    haut = ecran.geometry().top()
    return haut <= zone_icone.top() <= haut + BANDE_BARRE_DE_MENUS


class Panneau(QWidget):
    """Le panneau qui pose les cartes et recueille les gestes de réponse."""

    reponse_donnee = pyqtSignal(str)
    passage_demande = pyqtSignal()
    suite_demandee = pyqtSignal()
    question_demandee = pyqtSignal()
    fenetre_demandee = pyqtSignal()
    fermeture_demandee = pyqtSignal()
    sortie_demandee = pyqtSignal()
    masque = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        configurer_panneau(self)
        self.setWindowTitle("KnowYourCode")

        self._zone_ancrage = QRect()
        self._reponse_ouverte = False
        self._boutons_options: list[PushButton] = []
        self._construire()

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
        interieur.addWidget(self._construire_pied())

    def _construire_entete(self) -> QHBoxLayout:
        ligne = QHBoxLayout()
        ligne.setSpacing(8)

        logo = QLabel(self._cadre)
        logo.setPixmap(pixmap_marque(15))
        ligne.addWidget(logo)
        ligne.addSpacing(-2)

        ligne.addWidget(StrongBodyLabel("KnowYourCode", self._cadre))

        self._etiquette_etat = CaptionLabel("", self._cadre)
        self._etiquette_etat.setStyleSheet(f"color: {COULEUR_TEXTE_ATTENUE};")
        ligne.addWidget(self._etiquette_etat)
        ligne.addStretch(1)

        # L'avancement se tient dans l'entête et non près des boutons : on veut
        # pouvoir savoir combien il reste sans quitter le code des yeux plus
        # d'un instant.
        self._etiquette_avancement = CaptionLabel("", self._cadre)
        self._etiquette_avancement.setStyleSheet(f"color: {COULEUR_TEXTE_ATTENUE};")
        ligne.addWidget(self._etiquette_avancement)

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
        self._zone_code = ZoneCode(self._cadre)
        return self._zone_code

    def _construire_zone_basse(self) -> QWidget:
        self._pile = QStackedWidget(self._cadre)
        self._pile.setFixedHeight(HAUTEUR_ZONE_CARTE)
        self._pile.addWidget(self._construire_page_repos())
        self._pile.addWidget(self._construire_page_carte())
        self._pile.addWidget(self._construire_page_correction())
        self._pile.addWidget(self._construire_page_bilan())
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

        bouton = PrimaryPushButton("Commencer une série", page)
        bouton.clicked.connect(self.question_demandee.emit)
        colonne.addWidget(bouton)
        colonne.addStretch(1)
        return page

    def _construire_page_carte(self) -> QWidget:
        page = QWidget(self._pile)
        colonne = QVBoxLayout(page)
        colonne.setContentsMargins(0, 0, 0, 0)
        colonne.setSpacing(8)

        self._etiquette_question = BodyLabel("", page)
        self._etiquette_question.setWordWrap(True)
        colonne.addWidget(self._etiquette_question)

        colonne.addWidget(self._construire_reponses(page))
        colonne.addStretch(1)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        actions.addStretch(1)

        # Passer abandonne la série entière, pas seulement la carte : une
        # question qu'on saute a déjà appris quelque chose, une série qu'on
        # traîne à moitié n'apprend plus rien.
        self._bouton_passer = PushButton("Passer", page)
        self._bouton_passer.clicked.connect(self.passage_demande.emit)
        actions.addWidget(self._bouton_passer)

        colonne.addLayout(actions)
        return page

    def _construire_reponses(self, parent: QWidget) -> QWidget:
        """La grille de propositions, seul geste de réponse qui subsiste."""
        self._zone_options = QWidget(parent)
        self._zone_options.setFixedHeight(HAUTEUR_ZONE_OPTIONS)
        self._grille_options = QGridLayout(self._zone_options)
        self._grille_options.setContentsMargins(0, 0, 0, 0)
        # L'écart horizontal est le plus large des deux : côte à côte, deux
        # libellés séparés de huit pixels seulement se lisent comme une seule
        # phrase, alors que l'un est la bonne réponse et l'autre un leurre.
        self._grille_options.setHorizontalSpacing(ECART_OPTIONS_HORIZONTAL)
        self._grille_options.setVerticalSpacing(ECART_OPTIONS)
        return self._zone_options

    def _construire_page_correction(self) -> QWidget:
        page = QWidget(self._pile)
        colonne = QVBoxLayout(page)
        colonne.setContentsMargins(0, 0, 0, 0)
        colonne.setSpacing(6)

        self._etiquette_verdict = StrongBodyLabel("", page)
        colonne.addWidget(self._etiquette_verdict)

        self._etiquette_bonne_reponse = BodyLabel("", page)
        self._etiquette_bonne_reponse.setWordWrap(True)
        colonne.addWidget(self._etiquette_bonne_reponse)

        self._etiquette_explication = BodyLabel("", page)
        self._etiquette_explication.setWordWrap(True)
        self._etiquette_explication.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )

        # L'explication est le seul texte long du panneau, et le seul qu'on
        # relit : elle défile plutôt que de rogner la zone de code.
        defilement = SmoothScrollArea(page)
        defilement.setWidget(self._etiquette_explication)
        defilement.setWidgetResizable(True)
        defilement.setFrameShape(QFrame.Shape.NoFrame)
        defilement.setStyleSheet("QScrollArea, QWidget { background: transparent; }")
        defilement.viewport().setStyleSheet("background: transparent;")
        colonne.addWidget(defilement, stretch=1)

        actions = QHBoxLayout()
        actions.addStretch(1)
        self._bouton_suivant = PrimaryPushButton("Carte suivante", page)
        self._bouton_suivant.clicked.connect(self.suite_demandee.emit)
        actions.addWidget(self._bouton_suivant)
        colonne.addLayout(actions)
        return page

    def _construire_page_bilan(self) -> QWidget:
        page = QWidget(self._pile)
        colonne = QVBoxLayout(page)
        colonne.setContentsMargins(0, 0, 0, 0)
        colonne.setSpacing(8)
        colonne.addStretch(1)

        self._etiquette_bilan = StrongBodyLabel("", page)
        colonne.addWidget(self._etiquette_bilan)

        self._commentaire_bilan = BodyLabel("", page)
        self._commentaire_bilan.setWordWrap(True)
        self._commentaire_bilan.setStyleSheet(f"color: {COULEUR_TEXTE_ATTENUE};")
        colonne.addWidget(self._commentaire_bilan)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        actions.addStretch(1)

        refermer = PushButton("Refermer", page)
        refermer.clicked.connect(self.fermeture_demandee.emit)
        actions.addWidget(refermer)

        self._bouton_serie_suivante = PrimaryPushButton("Une autre série", page)
        self._bouton_serie_suivante.clicked.connect(self.question_demandee.emit)
        actions.addWidget(self._bouton_serie_suivante)

        colonne.addLayout(actions)
        colonne.addStretch(1)
        return page

    def _construire_pied(self) -> QWidget:
        pied = QWidget(self._cadre)
        pied.setStyleSheet("border-top: 1px solid rgba(255, 255, 255, 0.07);")

        ligne = QHBoxLayout(pied)
        ligne.setContentsMargins(0, 6, 0, 0)
        ligne.setSpacing(8)

        ouvrir = TransparentToolButton(pied)
        ouvrir.setIcon(QIcon(pixmap_marque(14)))
        ouvrir.setFixedSize(30, 26)
        ouvrir.setToolTip("Progression et réglages")
        ouvrir.clicked.connect(self.fenetre_demandee.emit)
        ligne.addWidget(ouvrir)
        ligne.addStretch(1)

        quitter = TransparentToolButton(FluentIcon.POWER_BUTTON, pied)
        quitter.setFixedSize(26, 26)
        quitter.setIconSize(QSize(12, 12))
        quitter.setToolTip("Quitter KnowYourCode")
        quitter.clicked.connect(self.sortie_demandee.emit)
        ligne.addWidget(quitter)
        return pied

    # ------------------------------------------------------------------
    # Affichage par état
    # ------------------------------------------------------------------

    def ancrer(self, zone_icone: QRect) -> None:
        """Retient la position de l'icône, sous laquelle s'ouvrir.

        Une icône qui vient d'être créée annonce une position aberrante, du
        genre `QRect(0, 1440, 38, 0)`, le temps que le système la place
        vraiment. Elle n'est pas nulle pour autant : c'est sa hauteur qu'il
        faut regarder.

        Et surtout, macOS ne répond pas la même chose selon que l'application
        est au premier plan ou non. Un clic sur l'icône donne toujours une
        position juste ; l'ouverture automatique, elle, arrive pendant qu'on
        est ailleurs, et la position rendue peut alors être celle d'avant,
        voire d'un écran qu'on a débranché. On ne retient donc que ce qui
        ressemble vraiment à une icône de barre de menus : sur un écran connu,
        et collée à son bord haut. Le reste est ignoré, et le dernier ancrage
        valable continue de servir.
        """
        if _ancrage_credible(zone_icone):
            self._zone_ancrage = zone_icone

    def repositionner(self) -> None:
        """Replace le panneau, l'ancrage ayant pu changer depuis l'ouverture."""
        if self.isVisible():
            self._positionner()

    def afficher_repos(self, message: str) -> None:
        """Ouvre le panneau sans série en cours."""
        self._reponse_ouverte = False
        self._etiquette_etat.setText("")
        self._etiquette_avancement.setText("")
        self._message_repos.setText(message)
        self._localisation.setVisible(False)
        self._zone_code.setVisible(False)
        self._pile.setFixedHeight(HAUTEUR_ZONE_REPOS)
        self._pile.setCurrentIndex(_INDEX_REPOS)
        self._afficher(LARGEUR, HAUTEUR_REPOS)

    def afficher_carte(
        self, extrait: Extrait, carte: Carte, numero: int, total: int
    ) -> None:
        """Pose une carte de la série sur son extrait."""
        self._etiquette_etat.setText("carte")
        self._etiquette_avancement.setText(f"{numero} / {total}")
        self._etiquette_fichier.setText(extrait.chemin_fichier)
        self._etiquette_fonction.setText(extrait.nom_fonction)
        self._etiquette_question.setText(carte.question)
        self._preparer_reponse(carte)

        self._localisation.setVisible(True)
        self._zone_code.setVisible(True)
        self._pile.setFixedHeight(HAUTEUR_ZONE_CARTE)
        self._pile.setCurrentIndex(_INDEX_CARTE)

        # Le panneau prend sa taille avant que le code n'arrive : c'est cette
        # taille qui dit si l'extrait tient en entier, donc s'il faut le faire
        # défiler jusqu'à la ligne visée.
        self._afficher(LARGEUR, HAUTEUR_MANCHE)

        self._zone_code.montrer(extrait.code, extrait.langage, carte.ligne)
        self._reponse_ouverte = True

    def afficher_correction(
        self, correction: Correction, numero: int, total: int
    ) -> None:
        """Dit tout de suite si c'était juste, et pourquoi."""
        self._reponse_ouverte = False
        self._etiquette_etat.setText("correction")
        self._etiquette_avancement.setText(f"{numero} / {total}")

        couleur = COULEUR_JUSTE if correction.juste else COULEUR_FAUX
        self._etiquette_verdict.setText("Juste" if correction.juste else "Raté")
        self._etiquette_verdict.setStyleSheet(f"color: {couleur};")

        # La bonne réponse n'est rappelée qu'en cas d'erreur : la répéter après
        # une réussite met le doute là où il n'y en avait pas.
        self._etiquette_bonne_reponse.setText(
            "" if correction.juste else f"C'était : {correction.bonne_reponse}"
        )
        self._etiquette_bonne_reponse.setVisible(not correction.juste)

        self._etiquette_explication.setText(correction.explication)
        self._bouton_suivant.setText(
            "Voir le bilan" if numero >= total else "Carte suivante"
        )

        self._pile.setFixedHeight(HAUTEUR_ZONE_CORRECTION)
        self._pile.setCurrentIndex(_INDEX_CORRECTION)
        # L'explication prend plus de place que la question : c'est la fenêtre
        # qui s'allonge, pas le code qui se serre. Le panneau étant ancré sous
        # la barre de menus, il grandit vers le bas et pas une ligne de code ne
        # bouge — or c'est précisément l'instant où on la relit.
        self.resize(LARGEUR, HAUTEUR_CORRECTION)
        # Mais grandir sans se replacer faisait passer le bas sous le bord de
        # l'écran. Le placement remesure et remonte s'il le faut : le code qui
        # bouge d'un cran vaut mieux qu'un bouton qu'on ne peut plus atteindre.
        self._positionner()
        self._bouton_suivant.setFocus()

    def afficher_bilan(self, justes: int, total: int, commentaire: str) -> None:
        """Referme la série sur son compte."""
        self._reponse_ouverte = False
        self._etiquette_etat.setText("bilan")
        self._etiquette_avancement.setText("")
        self._etiquette_bilan.setText(f"{justes} / {total}")
        self._commentaire_bilan.setText(commentaire)

        self._localisation.setVisible(False)
        self._zone_code.setVisible(False)
        self._pile.setFixedHeight(HAUTEUR_ZONE_BILAN)
        self._pile.setCurrentIndex(_INDEX_BILAN)
        self._afficher(LARGEUR, HAUTEUR_BILAN)
        self._bouton_serie_suivante.setFocus()

    def fermer(self) -> None:
        """Referme le panneau."""
        self._reponse_ouverte = False
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

    def _zone_ecran(self) -> QRect:
        """La place disponible sur l'écran qui porte l'icône.

        Celui de l'icône, et non l'écran principal : avec un moniteur externe,
        la barre de menus n'est pas forcément sur celui que le système appelle
        principal. S'y fier plaçait le panneau d'après un écran et l'ancrait
        sur un autre, c'est-à-dire nulle part.
        """
        ecran = None
        if not self._zone_ancrage.isEmpty():
            ecran = QGuiApplication.screenAt(self._zone_ancrage.center())
        if ecran is None:
            ecran = QGuiApplication.primaryScreen()
        return ecran.availableGeometry() if ecran else QRect(0, 0, 1280, 800)

    def _positionner(self) -> None:
        """Centre le panneau sous l'icône, en le gardant entier à l'écran.

        Le placement borne aussi la taille, et pas seulement la position : une
        fenêtre plus haute que l'écran laisserait dehors le bouton qui fait
        avancer, et la série s'arrêterait là sans qu'on puisse rien y faire.
        Sur un écran assez grand, rien de tout cela ne joue et la fenêtre garde
        la taille qu'on lui a demandée.
        """
        zone = self._zone_ecran()

        # Le plancher ne sert qu'à limiter le rétrécissement, jamais à gonfler :
        # le repos ne demande que 170 pixels, et les lui refuser ouvrait une
        # fenêtre aux trois quarts vide. D'où le `min` avec la hauteur demandée,
        # qui garde la dernière décision à l'appelant.
        place = zone.height() - ECART_SOUS_LA_BARRE - MARGE_ECRAN
        hauteur = min(self.height(), max(place, HAUTEUR_MINIMALE))
        largeur = min(self.width(), zone.width() - 2 * MARGE_ECRAN)
        if (largeur, hauteur) != (self.width(), self.height()):
            self.resize(largeur, hauteur)

        if self._zone_ancrage.isEmpty():
            # Position de repli : le coin où vit l'icône, faute de savoir où
            # elle est exactement.
            x = zone.right() - self.width() - MARGE_ECRAN
        else:
            x = self._zone_ancrage.center().x() - self.width() // 2

        x = max(
            zone.left() + MARGE_ECRAN,
            min(x, zone.right() - self.width() - MARGE_ECRAN),
        )
        # `availableGeometry` commence déjà sous la barre de menus.
        y = max(
            zone.top(),
            min(
                zone.top() + ECART_SOUS_LA_BARRE,
                zone.bottom() - self.height() - MARGE_ECRAN,
            ),
        )
        self.move(x, y)

    # ------------------------------------------------------------------
    # Interactions
    # ------------------------------------------------------------------

    def _preparer_reponse(self, carte: Carte) -> None:
        """Met en place le geste de réponse : deux options, ou quatre."""
        self._poser_options(carte.options)

    def _poser_options(self, options: tuple[str, ...]) -> None:
        """Refait la grille de propositions, celle d'avant n'ayant plus cours."""
        for bouton in self._boutons_options:
            self._grille_options.removeWidget(bouton)
            bouton.deleteLater()
        self._boutons_options = []

        # Deux propositions tiennent côte à côte ; quatre passent en deux
        # rangées, ce qui les garde toutes lisibles d'un seul regard.
        colonnes = min(len(options), _COLONNES_QCM) or 1
        for rang, texte in enumerate(options):
            bouton = PushButton(texte, self._zone_options)
            bouton.setMinimumHeight(HAUTEUR_BOUTON_OPTION)
            bouton.clicked.connect(
                lambda _=False, choix=texte: self._repondre(choix)
            )
            self._grille_options.addWidget(
                bouton, rang // colonnes, rang % colonnes
            )
            self._boutons_options.append(bouton)

    def _repondre(self, reponse: str) -> None:
        """Signale la réponse une fois, et referme le geste derrière elle."""
        if not self._reponse_ouverte or self._pile.currentIndex() != _INDEX_CARTE:
            return
        self._reponse_ouverte = False
        for bouton in self._boutons_options:
            bouton.setEnabled(False)
        self.reponse_donnee.emit(reponse)

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
