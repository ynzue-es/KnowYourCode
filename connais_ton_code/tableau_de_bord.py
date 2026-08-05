"""L'affichage de la progression.

Il ne calcule rien : `statistiques.py` a déjà transformé l'historique en
valeurs prêtes à afficher.

La hiérarchie suit celle de l'exercice. La série de jours passe devant tout le
reste, seule et en très grand, parce que c'est elle qu'on vient regarder et
elle qu'on ne veut pas casser. Viennent ensuite les notions ratées, qui disent
quoi réviser, puis le calendrier, où ce sont les trous qui parlent.

Le choix des formes suit le travail que fait chaque donnée. Un chiffre qui
résume se pose en grand plutôt qu'en graphique. Une régularité se lit en
calendrier. Des parts se lisent en barres, parce qu'on y compare des
longueurs.

Les couleurs suivent la même règle. Une série unique n'a rien à distinguer :
elle prend la couleur d'accent. Une intensité prend une seule teinte, du vide
au plein. Des catégories prennent des teintes distinctes, vérifiées avec un
validateur de palette plutôt qu'à l'œil, pour rester séparables en vision
déficiente.
"""

from __future__ import annotations

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPaintEvent
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QToolTip, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    SmoothScrollArea,
    StrongBodyLabel,
    TitleLabel,
)

from .couverture import Couverture
from .statistiques import Reussite, Statistiques

LARGEUR = 560
HAUTEUR = 440

_COULEUR_CARTE = "#1f2126"
_COULEUR_TEXTE = "#e8eaed"
_COULEUR_SECONDAIRE = "#a9adb5"
_COULEUR_ATTENUE = "#7c818a"

# Série unique : la couleur ne distingue rien, elle marque seulement la donnée.
_ACCENT = "#4c8dff"

# Palette catégorielle passée au validateur en fond sombre : bande de clarté,
# plancher de saturation, séparation en vision déficiente et contraste, les
# cinq contrôles au vert.
_CATEGORIES = ("#4c8dff", "#c9821f", "#2fa87f")

# Une seule teinte, du vide au plein : c'est une intensité, pas une identité.
_ECHELLE_ACTIVITE = ("#23262c", "#2b569f", "#3a72d0", "#4c8dff", "#7dabff")

_BON = "#2fa87f"
_MAUVAIS = "#c9821f"

# Au-dessus, la notion est acquise et le chiffre n'a pas à alerter.
_SEUIL_ACQUIS = 0.6

_COTE_CASE = 18
_ECART_CASE = 5
_LARGEUR_JOURS = 26
_HAUTEUR_BARRES = 104

# Les catégories sont écrites sans accent dans les données, pour rester des
# clés commodes ; l'écran, lui, mérite du français.
_NOM_CATEGORIE = {
    "langage": "Langage",
    "robustesse": "Robustesse",
    "securite": "Sécurité",
}

# Combien de lignes on montre avant que la liste cesse d'être une liste et
# devienne un mur.
_NOTIONS_MONTREES = 8


class _Carte(QFrame):
    """Un chiffre qui se suffit à lui-même, posé en grand."""

    def __init__(self, valeur: str, libelle: str, detail: str = "") -> None:
        super().__init__()
        self.setObjectName("carte")
        self.setStyleSheet(
            f"#carte {{ background-color: {_COULEUR_CARTE}; border-radius: 10px; }}"
        )
        self.setFixedHeight(96)

        colonne = QVBoxLayout(self)
        colonne.setContentsMargins(14, 10, 14, 10)
        colonne.setSpacing(0)

        chiffre = TitleLabel(valeur, self)
        chiffre.setStyleSheet(f"color: {_COULEUR_TEXTE};")
        colonne.addWidget(chiffre)

        nom = CaptionLabel(libelle, self)
        nom.setStyleSheet(f"color: {_COULEUR_ATTENUE};")
        colonne.addWidget(nom)

        colonne.addStretch(1)
        if detail:
            precision = CaptionLabel(detail, self)
            precision.setStyleSheet(f"color: {_COULEUR_SECONDAIRE};")
            precision.setWordWrap(True)
            colonne.addWidget(precision)


class _Serie(QFrame):
    """La série de jours, seule sur sa ligne et deux fois plus grosse.

    Elle ne partage pas la rangée des autres chiffres : mise à côté d'eux,
    elle se lirait comme une statistique parmi d'autres, alors que c'est le
    seul nombre qu'on perd en ne revenant pas.
    """

    def __init__(self, statistiques: Statistiques) -> None:
        super().__init__()
        self.setObjectName("serie")
        self.setStyleSheet(
            f"#serie {{ background-color: {_COULEUR_CARTE}; border-radius: 10px; }}"
        )
        self.setFixedHeight(112)

        ligne = QHBoxLayout(self)
        ligne.setContentsMargins(18, 12, 18, 12)
        ligne.setSpacing(14)

        jours = statistiques.serie_en_cours
        chiffre = TitleLabel(str(jours), self)
        chiffre.setStyleSheet(
            f"color: {_ACCENT if jours else _COULEUR_ATTENUE}; font-size: 46px;"
        )
        ligne.addWidget(chiffre, 0, Qt.AlignmentFlag.AlignVCenter)

        colonne = QVBoxLayout()
        colonne.setSpacing(2)
        colonne.addStretch(1)
        colonne.addWidget(
            StrongBodyLabel("jour d'affilée" if jours == 1 else "jours d'affilée", self)
        )

        if statistiques.faite_aujourdhui:
            etat = "C'est fait pour aujourd'hui."
        elif jours:
            etat = "Une carte aujourd'hui et la série tient."
        else:
            etat = "Une carte aujourd'hui et la série repart."
        message = CaptionLabel(etat, self)
        message.setStyleSheet(
            f"color: {_BON if statistiques.faite_aujourdhui else _COULEUR_SECONDAIRE};"
        )
        colonne.addWidget(message)

        record = CaptionLabel(
            f"Meilleure série : {statistiques.meilleure_serie} jour(s) — "
            f"{statistiques.jours_actifs} jour(s) d'activité en tout",
            self,
        )
        record.setStyleSheet(f"color: {_COULEUR_ATTENUE};")
        colonne.addWidget(record)
        colonne.addStretch(1)

        ligne.addLayout(colonne, 1)


class _Calendrier(QWidget):
    """Douze semaines de régularité, une case par jour.

    Ce sont les trous qui portent l'information, donc les jours sans carte
    sont dessinés comme les autres, en creux.
    """

    def __init__(self, jours: list, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._jours = jours
        self._maximum = max((jour.nombre for jour in jours), default=0)
        self.setMouseTracking(True)

        self._decalage = jours[0].jour.weekday() if jours else 0
        colonnes = (len(jours) + self._decalage + 6) // 7 if jours else 0
        self.setFixedHeight(7 * (_COTE_CASE + _ECART_CASE))
        self.setFixedWidth(_LARGEUR_JOURS + colonnes * (_COTE_CASE + _ECART_CASE))

    def _case(self, index: int) -> QRectF:
        position = index + self._decalage
        return QRectF(
            _LARGEUR_JOURS + (position // 7) * (_COTE_CASE + _ECART_CASE),
            (position % 7) * (_COTE_CASE + _ECART_CASE),
            _COTE_CASE,
            _COTE_CASE,
        )

    def _teinte(self, nombre: int) -> str:
        if nombre <= 0 or self._maximum <= 0:
            return _ECHELLE_ACTIVITE[0]
        # Quatre paliers plutôt qu'un dégradé continu : l'œil compare mal deux
        # nuances voisines, il compare bien quatre niveaux.
        palier = min(4, 1 + (nombre - 1) * 3 // max(1, self._maximum))
        return _ECHELLE_ACTIVITE[palier]

    def paintEvent(self, event: QPaintEvent) -> None:
        peintre = QPainter(self)
        peintre.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Une lettre un jour sur deux : les sept d'affilée formeraient une
        # colonne de bruit que personne ne lit.
        peintre.setPen(QColor(_COULEUR_ATTENUE))
        for rang, lettre in enumerate(("", "M", "", "J", "", "S", "")):
            if not lettre:
                continue
            peintre.drawText(
                QRectF(0, rang * (_COTE_CASE + _ECART_CASE), _LARGEUR_JOURS - 8, _COTE_CASE),
                int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight),
                lettre,
            )

        peintre.setPen(Qt.PenStyle.NoPen)
        for index, jour in enumerate(self._jours):
            peintre.setBrush(QColor(self._teinte(jour.nombre)))
            peintre.drawRoundedRect(self._case(index), 3, 3)
        peintre.end()

    def mouseMoveEvent(self, event) -> None:
        for index, jour in enumerate(self._jours):
            if not self._case(index).contains(event.position()):
                continue
            if jour.nombre == 0:
                compte = "aucune carte"
            elif jour.nombre == 1:
                compte = "1 carte"
            else:
                compte = f"{jour.nombre} cartes"
            QToolTip.showText(
                event.globalPosition().toPoint(),
                f"{jour.jour.strftime('%d/%m/%Y')} : {compte}",
                self,
            )
            return
        QToolTip.hideText()


class _Barres(QWidget):
    """Un taux de réussite par catégorie, en barres horizontales.

    Les barres vont de zéro à cent et non jusqu'au meilleur des trois : c'est
    une part, pas un classement, et la ramener au maximum ferait passer 40 %
    pour un bon score dès que les autres sont pires.
    """

    def __init__(self, reussites: list[Reussite], parent=None) -> None:
        super().__init__(parent)
        self._reussites = reussites
        self.setFixedHeight(_HAUTEUR_BARRES)

    def paintEvent(self, event: QPaintEvent) -> None:
        if not self._reussites:
            return

        peintre = QPainter(self)
        peintre.setRenderHint(QPainter.RenderHint.Antialiasing)

        largeur_libelle = 88.0
        largeur_valeur = 68.0
        # Deux pixels de fond entre deux barres : sans cet écart, deux barres
        # voisines se lisent comme une seule.
        hauteur = self.height() / len(self._reussites) - 2
        disponible = max(1.0, self.width() - largeur_libelle - largeur_valeur - 8)

        for rang, reussite in enumerate(self._reussites):
            haut = rang * (hauteur + 2)

            peintre.setPen(QColor(_COULEUR_ATTENUE))
            peintre.drawText(
                QRectF(0, haut, largeur_libelle, hauteur),
                int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                _NOM_CATEGORIE.get(reussite.sujet, reussite.sujet),
            )

            peintre.setPen(Qt.PenStyle.NoPen)
            peintre.setBrush(QColor(_ECHELLE_ACTIVITE[0]))
            peintre.drawRoundedRect(
                QRectF(largeur_libelle, haut + 3, disponible, hauteur - 6), 4, 4
            )

            if reussite.taux > 0:
                peintre.setBrush(QColor(_CATEGORIES[rang % len(_CATEGORIES)]))
                peintre.drawRoundedRect(
                    QRectF(
                        largeur_libelle,
                        haut + 3,
                        max(8.0, disponible * reussite.taux),
                        hauteur - 6,
                    ),
                    4,
                    4,
                )

            peintre.setPen(QColor(_COULEUR_SECONDAIRE))
            peintre.drawText(
                QRectF(self.width() - largeur_valeur, haut, largeur_valeur, hauteur),
                int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight),
                f"{reussite.taux * 100:.0f} %  ({reussite.justes}/{reussite.total})",
            )
        peintre.end()


class TableauDeBord(QWidget):
    """La progression, sous forme lisible."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # Taille minimale et non figée : la fenêtre doit pouvoir grandir.
        self.setMinimumSize(LARGEUR, HAUTEUR)

        # La mesure du projet survit à un réaffichage : rouvrir la fenêtre ne
        # doit pas remettre le bloc à vide le temps d'un nouveau parcours.
        self._couverture: Couverture | None = None
        self._bloc_couverture: QWidget | None = None

        exterieur = QVBoxLayout(self)
        exterieur.setContentsMargins(0, 0, 0, 0)

        self._contenu = QWidget()
        self._colonne = QVBoxLayout(self._contenu)
        self._colonne.setContentsMargins(0, 0, 12, 0)
        self._colonne.setSpacing(14)
        self._colonne.addStretch(1)

        defilement = SmoothScrollArea(self)
        defilement.setWidget(self._contenu)
        defilement.setWidgetResizable(True)
        defilement.setFrameShape(QFrame.Shape.NoFrame)
        defilement.setStyleSheet("QScrollArea, QWidget { background: transparent; }")
        defilement.viewport().setStyleSheet("background: transparent;")
        exterieur.addWidget(defilement)

    # ------------------------------------------------------------------
    # Remplissage
    # ------------------------------------------------------------------

    def afficher(self, statistiques: Statistiques) -> None:
        """Remplit la vue. Peut être rappelée autant de fois qu'on veut."""
        self._vider()
        self._bloc_couverture = None

        # Le seuil est le jour d'activité et non la carte : quelqu'un qui
        # arrive de l'ancien exercice a une série à voir avant d'avoir répondu
        # à sa première carte.
        if statistiques.jours_actifs == 0:
            self._poser(self._message_vide())
            return

        self._poser(_Serie(statistiques))
        self._poser(self._cartes(statistiques))

        # Le bloc est posé vide et se remplit quand la mesure arrive. Le poser
        # après coup le ferait apparaître au milieu de la page une fois qu'on
        # a commencé à lire.
        self._bloc_couverture = self._section("Ce qu'il reste à voir", None)
        self._poser(self._bloc_couverture)
        self.definir_couverture(self._couverture)
        self._poser(
            self._section(
                "Régularité",
                self._centrer(_Calendrier(statistiques.activite)),
                "Une case par jour sur les douze dernières semaines. "
                "Plus la case est claire, plus tu as répondu de cartes ce jour-là.",
            )
        )
        if statistiques.notions:
            self._poser(self._notions(statistiques))
        if statistiques.categories:
            self._poser(
                self._section(
                    "Par catégorie",
                    _Barres(statistiques.categories),
                    "La part de cartes réussies dans chaque famille de questions.",
                )
            )

    def _poser(self, bloc: QWidget) -> None:
        self._colonne.insertWidget(self._colonne.count() - 1, bloc)

    def _vider(self) -> None:
        while self._colonne.count() > 1:
            element = self._colonne.takeAt(0)
            widget = element.widget()
            if widget is not None:
                # `deleteLater` ne supprime qu'au prochain tour de boucle : sans
                # ce masquage, l'ancien contenu resterait visible par-dessus.
                widget.hide()
                widget.deleteLater()

    # ------------------------------------------------------------------
    # Blocs
    # ------------------------------------------------------------------

    def _centrer(self, contenu: QWidget) -> QWidget:
        """Met un contenu de largeur fixe au milieu de son cadre."""
        bloc = QWidget()
        ligne = QHBoxLayout(bloc)
        ligne.setContentsMargins(0, 0, 0, 0)
        ligne.addStretch(1)
        ligne.addWidget(contenu)
        ligne.addStretch(1)
        return bloc

    def _message_vide(self) -> QWidget:
        bloc = QWidget()
        colonne = QVBoxLayout(bloc)
        colonne.addStretch(1)
        message = BodyLabel(
            "Réponds à tes premières cartes pour lancer ta série.", bloc
        )
        message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        message.setStyleSheet(f"color: {_COULEUR_SECONDAIRE};")
        colonne.addWidget(message)
        colonne.addStretch(1)
        return bloc

    def _cartes(self, statistiques: Statistiques) -> QWidget:
        bloc = QWidget()
        ligne = QHBoxLayout(bloc)
        ligne.setContentsMargins(0, 0, 0, 0)
        ligne.setSpacing(10)

        for valeur, libelle, detail in (
            (
                f"{statistiques.taux_de_reussite * 100:.0f} %",
                "Réussite",
                f"{statistiques.nombre_de_justes} carte(s) juste(s)",
            ),
            (
                str(statistiques.nombre_de_cartes),
                "Cartes répondues",
                f"{statistiques.nombre_de_passages} extrait(s) passé(s)",
            ),
            (
                str(statistiques.fonctions_couvertes),
                "Fonctions vues",
                f"dans {statistiques.fichiers_couverts} fichier(s)",
            ),
        ):
            ligne.addWidget(_Carte(valeur, libelle, detail))
        return bloc

    def _notions(self, statistiques: Statistiques) -> QWidget:
        bloc = self._section(
            "Les notions que tu rates",
            None,
            "Elles sont déjà triées : la première est celle à revoir.",
        )
        colonne = bloc.layout()
        for notion in statistiques.notions[:_NOTIONS_MONTREES]:
            ligne = QHBoxLayout()
            ligne.setSpacing(8)
            ligne.addWidget(BodyLabel(notion.sujet, bloc))
            ligne.addStretch(1)

            part = StrongBodyLabel(f"{notion.taux * 100:.0f} %", bloc)
            part.setStyleSheet(
                f"color: {_BON if notion.taux >= _SEUIL_ACQUIS else _MAUVAIS};"
            )
            ligne.addWidget(part)

            detail = CaptionLabel(f"{notion.justes}/{notion.total}", bloc)
            detail.setStyleSheet(f"color: {_COULEUR_ATTENUE};")
            ligne.addWidget(detail)
            colonne.addLayout(ligne)
        return bloc

    def definir_couverture(self, couverture: Couverture | None) -> None:
        """Pose la mesure du projet, qui arrive après le reste.

        Le tableau s'affiche sans attendre : parcourir le projet entier prend
        le temps qu'il faut, et une fenêtre qui se fige une demi-seconde à
        l'ouverture se remarque plus qu'un chiffre qui arrive une demi-seconde
        après tout le monde.
        """
        self._couverture = couverture
        if self._bloc_couverture is None:
            return

        colonne = self._bloc_couverture.layout()
        while colonne.count() > 1:
            element = colonne.takeAt(1)
            widget = element.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

        if couverture is None or not couverture.fonctions_interrogeables:
            colonne.addWidget(
                self._attenue("Le projet n'a pas pu être parcouru.")
            )
            return

        # « de ce projet » n'est pas une précision de style : la carte du haut
        # compte les fonctions vues depuis toujours, tous projets confondus, et
        # les deux chiffres se contrediraient à l'œil sans cette mention.
        colonne.addLayout(
            self._compteur(
                "Notions de ce projet",
                couverture.notions_vues,
                couverture.notions_du_projet,
                couverture.part_des_notions,
            )
        )
        colonne.addLayout(
            self._compteur(
                "Fonctions de ce projet",
                couverture.fonctions_vues,
                couverture.fonctions_interrogeables,
                couverture.part_des_fonctions,
            )
        )

        if couverture.notions_restantes:
            restantes = ", ".join(couverture.notions_restantes[:_NOTIONS_MONTREES])
            if len(couverture.notions_restantes) > _NOTIONS_MONTREES:
                restantes += "…"
            colonne.addWidget(self._attenue(f"Jamais posées : {restantes}"))

        colonne.addWidget(
            self._attenue(
                "Sur les fonctions que l'application sait interroger, c'est-à-dire "
                "celles où elle a repéré de quoi tenir une série."
            )
        )

    def _compteur(self, libelle: str, vus: int, total: int, part: float) -> QHBoxLayout:
        ligne = QHBoxLayout()
        ligne.setSpacing(8)
        ligne.addWidget(BodyLabel(libelle))
        ligne.addStretch(1)
        ligne.addWidget(StrongBodyLabel(f"{part * 100:.0f} %"))
        detail = CaptionLabel(f"{vus}/{total}")
        detail.setStyleSheet(f"color: {_COULEUR_ATTENUE};")
        ligne.addWidget(detail)
        return ligne

    def _attenue(self, texte: str) -> QWidget:
        legende = CaptionLabel(texte)
        legende.setStyleSheet(f"color: {_COULEUR_ATTENUE};")
        legende.setWordWrap(True)
        return legende

    def _section(
        self, titre: str, contenu: QWidget | None, note: str = ""
    ) -> QWidget:
        bloc = QFrame()
        bloc.setObjectName("section")
        bloc.setStyleSheet(
            f"#section {{ background-color: {_COULEUR_CARTE}; border-radius: 10px; }}"
        )
        colonne = QVBoxLayout(bloc)
        colonne.setContentsMargins(14, 12, 14, 14)
        colonne.setSpacing(8)
        colonne.addWidget(StrongBodyLabel(titre, bloc))

        if contenu is not None:
            colonne.addWidget(contenu)
        if note:
            legende = CaptionLabel(note, bloc)
            legende.setStyleSheet(f"color: {_COULEUR_ATTENUE};")
            legende.setWordWrap(True)
            colonne.addWidget(legende)
        return bloc
