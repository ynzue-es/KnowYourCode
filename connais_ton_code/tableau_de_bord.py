"""Le tableau de bord des statistiques de progression.

Il ne calcule rien : `statistiques.py` a déjà transformé l'historique en
valeurs prêtes à afficher, ce widget se contente de les poser à l'écran.
`afficher` est rappelée à chaque ouverture : mieux vaut repartir d'une colonne
vide que d'empiler les widgets d'une ouverture à l'autre.
"""

from __future__ import annotations

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPaintEvent, QPen
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    FlowLayout,
    HorizontalSeparator,
    SimpleCardWidget,
    SmoothScrollArea,
    StrongBodyLabel,
    TitleLabel,
)

from .apparence import COULEUR_ACCENT, COULEUR_FOND_PANNEAU, COULEUR_TEXTE_ATTENUE
from .statistiques import FonctionMalExpliquee, Statistiques

LARGEUR = 600
HAUTEUR = 480

HAUTEUR_COURBE = 90
NOMBRE_OUBLIS_AFFICHES = 10
NOMBRE_FONCTIONS_AFFICHEES = 6


class TableauDeBord(QWidget):
    """La colonne défilante qui affiche la progression de l'utilisateur."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # Taille minimale et non figée : le même widget sert dans le panneau
        # étroit et dans la grande fenêtre, où il doit occuper la place.
        self.setMinimumSize(LARGEUR, HAUTEUR)
        self._construire()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _construire(self) -> None:
        exterieur = QVBoxLayout(self)
        exterieur.setContentsMargins(0, 0, 0, 0)

        cadre = QFrame(self)
        cadre.setObjectName("tableauDeBord")
        cadre.setStyleSheet(
            f"#tableauDeBord {{ background-color: {COULEUR_FOND_PANNEAU};"
            f" border-radius: 10px; }}"
        )
        exterieur.addWidget(cadre)

        interieur = QVBoxLayout(cadre)
        interieur.setContentsMargins(0, 0, 0, 0)

        # Même recette que le panneau : le fond du cadre doit rester visible
        # à travers la zone de défilement, sinon on voit un rectangle gris
        # flotter par-dessus le panneau sombre.
        self._defilement = SmoothScrollArea(cadre)
        self._defilement.setWidgetResizable(True)
        self._defilement.setFrameShape(QFrame.Shape.NoFrame)
        self._defilement.setStyleSheet("QScrollArea, QWidget { background: transparent; }")
        interieur.addWidget(self._defilement)

        self._contenu = QWidget()
        self._contenu.setStyleSheet("background: transparent;")
        self._colonne = QVBoxLayout(self._contenu)
        self._colonne.setContentsMargins(20, 18, 20, 18)
        self._colonne.setSpacing(16)

        self._defilement.setWidget(self._contenu)
        self._defilement.viewport().setStyleSheet("background: transparent;")

    # ------------------------------------------------------------------
    # Remplissage
    # ------------------------------------------------------------------

    def afficher(self, statistiques: Statistiques) -> None:
        """Remplace le contenu affiché par la photographie donnée."""
        self._vider()

        if statistiques.nombre_de_reponses == 0:
            # Premier lancement, ou personne n'a encore répondu à une
            # question : les cartes et la courbe n'ont rien à montrer, alors
            # autant ne rien promettre plutôt que d'afficher des zéros.
            self._colonne.addStretch(1)
            self._colonne.addWidget(self._construire_message_vide())
            self._colonne.addStretch(1)
            return

        self._colonne.addWidget(self._construire_cartes(statistiques))
        self._colonne.addWidget(self._construire_courbe(statistiques))

        if statistiques.oublis_recents:
            self._colonne.addWidget(HorizontalSeparator(self._contenu))
            self._colonne.addWidget(self._construire_oublis(statistiques))

        if statistiques.fonctions_mal_expliquees:
            self._colonne.addWidget(HorizontalSeparator(self._contenu))
            self._colonne.addWidget(self._construire_fonctions(statistiques))

        if statistiques.repartition_par_langage:
            self._colonne.addWidget(HorizontalSeparator(self._contenu))
            self._colonne.addWidget(self._construire_langages(statistiques))

        self._colonne.addStretch(1)

    def _vider(self) -> None:
        while self._colonne.count():
            element = self._colonne.takeAt(0)
            widget = element.widget()
            if widget is not None:
                # `deleteLater` seul ne suffit pas : la suppression réelle
                # attend le prochain passage dans la boucle d'événements, et
                # le widget reste visible entretemps, superposé au nouveau
                # contenu.
                widget.hide()
                widget.deleteLater()

    # ------------------------------------------------------------------
    # Historique vide
    # ------------------------------------------------------------------

    def _construire_message_vide(self) -> QWidget:
        bloc = QWidget(self._contenu)
        colonne = QVBoxLayout(bloc)
        colonne.setContentsMargins(24, 0, 24, 0)

        message = BodyLabel(
            "Réponds à ta première question pour voir tes statistiques apparaître ici.",
            bloc,
        )
        message.setWordWrap(True)
        message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        message.setStyleSheet(f"color: {COULEUR_TEXTE_ATTENUE};")
        colonne.addWidget(message)
        return bloc

    # ------------------------------------------------------------------
    # Chiffres clés
    # ------------------------------------------------------------------

    def _construire_cartes(self, statistiques: Statistiques) -> QWidget:
        ligne = QWidget(self._contenu)
        disposition = QHBoxLayout(ligne)
        disposition.setContentsMargins(0, 0, 0, 0)
        disposition.setSpacing(10)

        disposition.addWidget(
            self._construire_carte(str(statistiques.nombre_de_reponses), "Réponses"),
            stretch=1,
        )
        disposition.addWidget(
            self._construire_carte(_formater_score(statistiques.score_moyen), "Score moyen"),
            stretch=1,
        )
        disposition.addWidget(
            self._construire_carte(
                _formater_score(statistiques.score_moyen_recent), "Score récent"
            ),
            stretch=1,
        )
        return ligne

    def _construire_carte(self, valeur: str, libelle: str) -> QWidget:
        carte = SimpleCardWidget(self._contenu)
        carte.setFixedHeight(86)
        colonne = QVBoxLayout(carte)
        colonne.setContentsMargins(4, 4, 4, 4)
        colonne.setSpacing(2)
        colonne.addStretch(1)

        etiquette_valeur = TitleLabel(valeur, carte)
        etiquette_valeur.setAlignment(Qt.AlignmentFlag.AlignCenter)
        colonne.addWidget(etiquette_valeur)

        etiquette_libelle = CaptionLabel(libelle, carte)
        etiquette_libelle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        etiquette_libelle.setStyleSheet(f"color: {COULEUR_TEXTE_ATTENUE};")
        colonne.addWidget(etiquette_libelle)
        colonne.addStretch(1)
        return carte

    # ------------------------------------------------------------------
    # Courbe
    # ------------------------------------------------------------------

    def _construire_courbe(self, statistiques: Statistiques) -> QWidget:
        bloc = QWidget(self._contenu)
        colonne = QVBoxLayout(bloc)
        colonne.setContentsMargins(0, 0, 0, 0)
        colonne.setSpacing(4)

        colonne.addWidget(StrongBodyLabel("Évolution des scores", bloc))

        courbe = _CourbeScores(bloc)
        courbe.definir_donnees(statistiques.scores_recents, statistiques.score_moyen)
        colonne.addWidget(courbe)
        return bloc

    # ------------------------------------------------------------------
    # Oublis récents
    # ------------------------------------------------------------------

    def _construire_oublis(self, statistiques: Statistiques) -> QWidget:
        bloc = QWidget(self._contenu)
        colonne = QVBoxLayout(bloc)
        colonne.setContentsMargins(0, 0, 0, 0)
        colonne.setSpacing(6)

        colonne.addWidget(StrongBodyLabel("Ce que tu oublies le plus", bloc))

        for oubli in statistiques.oublis_recents[:NOMBRE_OUBLIS_AFFICHES]:
            ligne = BodyLabel(f"•  {oubli.point}  ({oubli.nom_fonction})", bloc)
            ligne.setWordWrap(True)
            colonne.addWidget(ligne)
        return bloc

    # ------------------------------------------------------------------
    # Fonctions mal expliquées
    # ------------------------------------------------------------------

    def _construire_fonctions(self, statistiques: Statistiques) -> QWidget:
        bloc = QWidget(self._contenu)
        colonne = QVBoxLayout(bloc)
        colonne.setContentsMargins(0, 0, 0, 0)
        colonne.setSpacing(8)

        colonne.addWidget(StrongBodyLabel("Fonctions les moins bien expliquées", bloc))

        for fonction in statistiques.fonctions_mal_expliquees[:NOMBRE_FONCTIONS_AFFICHEES]:
            colonne.addWidget(self._construire_ligne_fonction(fonction))
        return bloc

    def _construire_ligne_fonction(self, fonction: FonctionMalExpliquee) -> QWidget:
        ligne = QWidget(self._contenu)
        disposition = QHBoxLayout(ligne)
        disposition.setContentsMargins(0, 0, 0, 0)
        disposition.setSpacing(8)

        textes = QVBoxLayout()
        textes.setContentsMargins(0, 0, 0, 0)
        textes.setSpacing(0)

        nom = BodyLabel(fonction.nom_fonction, ligne)
        nom.setWordWrap(True)
        textes.addWidget(nom)

        chemin = CaptionLabel(fonction.chemin_fichier, ligne)
        chemin.setWordWrap(True)
        chemin.setStyleSheet(f"color: {COULEUR_TEXTE_ATTENUE};")
        textes.addWidget(chemin)

        disposition.addLayout(textes, stretch=1)

        score = CaptionLabel(
            f"{round(fonction.score_moyen)}/100, posée {fonction.nombre_de_fois} fois",
            ligne,
        )
        score.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        score.setStyleSheet(f"color: {COULEUR_TEXTE_ATTENUE};")
        disposition.addWidget(score)
        return ligne

    # ------------------------------------------------------------------
    # Répartition par langage
    # ------------------------------------------------------------------

    def _construire_langages(self, statistiques: Statistiques) -> QWidget:
        bloc = QWidget(self._contenu)
        colonne = QVBoxLayout(bloc)
        colonne.setContentsMargins(0, 0, 0, 0)
        colonne.setSpacing(6)

        colonne.addWidget(StrongBodyLabel("Répartition par langage", bloc))

        ligne = QWidget(bloc)
        disposition = FlowLayout(ligne, needAni=False)
        disposition.setContentsMargins(0, 0, 0, 0)
        disposition.setHorizontalSpacing(18)
        disposition.setVerticalSpacing(4)

        for langage in statistiques.repartition_par_langage:
            texte = (
                f"{langage.langage}   {round(langage.score_moyen)}/100"
                f"   ({langage.nombre_de_reponses})"
            )
            etiquette = CaptionLabel(texte, ligne)
            etiquette.setStyleSheet(f"color: {COULEUR_TEXTE_ATTENUE};")
            disposition.addWidget(etiquette)

        colonne.addWidget(ligne)
        return bloc


def _formater_score(score: float) -> str:
    return f"{round(score)}/100"


class _CourbeScores(QWidget):
    """L'évolution des scores récents, dessinée à la main.

    Un `QChart` complet serait disproportionné pour vingt points au plus :
    une ligne, un point d'arrivée et un repère de moyenne suffisent, et le
    dessin à la main garantit que le résultat reste lisible aussi bien avec
    un seul point qu'avec vingt.
    """

    _MARGE_HORIZONTALE = 10
    _MARGE_VERTICALE = 12
    _RAYON_POINT = 4

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(HAUTEUR_COURBE)
        self._scores: list[int] = []
        self._moyenne = 0.0

    def definir_donnees(self, scores: list[int], moyenne: float) -> None:
        self._scores = scores
        self._moyenne = moyenne
        self.update()

    def _position(self, index: int, score: int, largeur: float, hauteur: float) -> tuple[float, float]:
        if len(self._scores) > 1:
            x = self._MARGE_HORIZONTALE + largeur * index / (len(self._scores) - 1)
        else:
            x = self._MARGE_HORIZONTALE + largeur / 2
        # Échelle fixe sur 0-100 : c'est le barème du score, pas une plage
        # recalculée à chaque affichage qui exagérerait de petits écarts.
        y = self._MARGE_VERTICALE + hauteur * (1 - score / 100)
        return x, y

    def paintEvent(self, event: QPaintEvent) -> None:
        if not self._scores:
            return

        peintre = QPainter(self)
        peintre.setRenderHint(QPainter.RenderHint.Antialiasing)

        largeur = self.width() - 2 * self._MARGE_HORIZONTALE
        hauteur = self.height() - 2 * self._MARGE_VERTICALE
        if largeur <= 0 or hauteur <= 0:
            return

        self._dessiner_repere_moyenne(peintre, largeur, hauteur)

        points = [
            self._position(i, score, largeur, hauteur) for i, score in enumerate(self._scores)
        ]

        if len(points) > 1:
            self._dessiner_ligne(peintre, points)

        self._dessiner_point_final(peintre, points[-1])

    def _dessiner_repere_moyenne(self, peintre: QPainter, largeur: float, hauteur: float) -> None:
        couleur = QColor(COULEUR_TEXTE_ATTENUE)
        couleur.setAlpha(90)
        y = self._MARGE_VERTICALE + hauteur * (1 - self._moyenne / 100)

        crayon = QPen(couleur, 1)
        peintre.setPen(crayon)
        peintre.drawLine(
            int(self._MARGE_HORIZONTALE),
            int(y),
            int(self._MARGE_HORIZONTALE + largeur),
            int(y),
        )

    def _dessiner_ligne(self, peintre: QPainter, points: list[tuple[float, float]]) -> None:
        trace = QPainterPath()
        trace.moveTo(*points[0])
        for x, y in points[1:]:
            trace.lineTo(x, y)

        crayon = QPen(QColor(COULEUR_ACCENT))
        crayon.setWidthF(2)
        crayon.setCapStyle(Qt.PenCapStyle.RoundCap)
        crayon.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        peintre.setPen(crayon)
        peintre.drawPath(trace)

    def _dessiner_point_final(self, peintre: QPainter, point: tuple[float, float]) -> None:
        x, y = point
        r = self._RAYON_POINT

        # L'anneau de la couleur de fond détache le point de la ligne, sans
        # ajouter de contour qui alourdirait le tracé.
        anneau = QPen(QColor(COULEUR_FOND_PANNEAU))
        anneau.setWidthF(2)
        peintre.setPen(anneau)
        peintre.setBrush(QColor(COULEUR_ACCENT))
        peintre.drawEllipse(QRectF(x - r, y - r, 2 * r, 2 * r))
