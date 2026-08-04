"""La marque du projet : un ordinateur portable affichant `</>`.

Tout est décrit en tracés plutôt qu'importé d'un fichier image. Un seul
dessin sert alors à quatre endroits qui ne peuvent pas diverger : le fichier
du dépôt, l'icône de la barre de menus, celle du Dock et celle de
l'application dans le Finder. C'est aussi ce qui permet à l'icône de la barre
d'être monochrome et à celle du Finder d'être en couleur sans les redessiner.

Les coordonnées sont exprimées dans un carré de 512, et mises à l'échelle au
moment du rendu.
"""

from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (
    QColor,
    QPainter,
    QPainterPath,
    QPainterPathStroker,
    QPixmap,
    QTransform,
)

COTE_REFERENCE = 512

FOND = "#1f2023"
BORDURE = "#33363b"

# Blanc sur noir : le contraste maximal, et la seule teinte qui reste elle-même
# quel que soit le fond sur lequel l'icône atterrit.
MARQUE = "#f5f6f8"

RAYON_FOND = 112

# L'écran, coins arrondis en haut seulement : en bas il rejoint le socle.
_ECRAN = QRectF(30, 58, 452, 307)
_RAYON_ECRAN = 30

# Le socle déborde de l'écran des deux côtés, comme le repose-poignets d'un
# portable vu de face.
_SOCLE = QRectF(0, 386, 512, 68)
_RAYON_SOCLE = 30

_EPAISSEUR_TRAIT = 30


def _ecran() -> QPainterPath:
    arrondi = QPainterPath()
    arrondi.addRoundedRect(_ECRAN, _RAYON_ECRAN, _RAYON_ECRAN)

    # Un rectangle plaqué sur la moitié basse annule l'arrondi du bas.
    bas = QPainterPath()
    bas.addRect(
        QRectF(
            _ECRAN.x(),
            _ECRAN.center().y(),
            _ECRAN.width(),
            _ECRAN.height() / 2,
        )
    )
    return arrondi.united(bas)


def _socle() -> QPainterPath:
    arrondi = QPainterPath()
    arrondi.addRoundedRect(_SOCLE, _RAYON_SOCLE, _RAYON_SOCLE)

    haut = QPainterPath()
    haut.addRect(QRectF(_SOCLE.x(), _SOCLE.y(), _SOCLE.width(), _RAYON_SOCLE))
    return arrondi.united(haut)


def _trait(points: list[tuple[float, float]]) -> QPainterPath:
    """Transforme une ligne brisée en surface, pour pouvoir la soustraire."""
    ligne = QPainterPath(QPointF(*points[0]))
    for point in points[1:]:
        ligne.lineTo(QPointF(*point))

    epaississeur = QPainterPathStroker()
    epaississeur.setWidth(_EPAISSEUR_TRAIT)
    epaississeur.setCapStyle(Qt.PenCapStyle.RoundCap)
    epaississeur.setJoinStyle(Qt.PenJoinStyle.RoundJoin)

    # Le contour d'un angle vif se recoupe sur lui-même ; sans cette
    # simplification, le remplissage prend l'intersection pour un trou et
    # laisse un losange dans la pointe du chevron.
    return epaississeur.createStroke(ligne).simplified()


def symbole_code() -> QPainterPath:
    """Les trois signes affichés à l'écran, sous forme de surface."""
    total = QPainterPath()
    total.addPath(_trait([(175, 143), (100, 211), (175, 279)]))
    total.addPath(_trait([(293, 108), (226, 305)]))
    total.addPath(_trait([(347, 143), (422, 211), (347, 279)]))
    return total.simplified()


def marque(avec_code: bool = True) -> QPainterPath:
    """La silhouette complète, le code étant évidé de l'écran.

    Évidé et non posé par-dessus : la forme reste d'un seul tenant, ce qui la
    rend utilisable telle quelle en icône monochrome comme en couleur.
    """
    silhouette = _ecran().united(_socle())
    if not avec_code:
        return silhouette
    return silhouette.subtracted(symbole_code())


def ajuster(tracé: QPainterPath, cible: QRectF) -> QPainterPath:
    """Met un tracé à l'échelle pour tenir dans `cible`, sans le déformer."""
    boite = tracé.boundingRect()
    if boite.isEmpty():
        return tracé

    facteur = min(cible.width() / boite.width(), cible.height() / boite.height())
    transformation = QTransform()
    transformation.translate(
        cible.center().x() - boite.center().x() * facteur,
        cible.center().y() - boite.center().y() * facteur,
    )
    transformation.scale(facteur, facteur)
    return transformation.map(tracé)


def dessiner_logo(peintre: QPainter) -> None:
    """Dessine le logo en couleur dans un carré de `COTE_REFERENCE`."""
    peintre.setRenderHint(QPainter.RenderHint.Antialiasing)

    cadre = QRectF(6, 6, COTE_REFERENCE - 12, COTE_REFERENCE - 12)
    fond = QPainterPath()
    fond.addRoundedRect(cadre, RAYON_FOND, RAYON_FOND)
    peintre.fillPath(fond, QColor(FOND))

    stylo = peintre.pen()
    stylo.setColor(QColor(BORDURE))
    stylo.setWidthF(6)
    peintre.setPen(stylo)
    peintre.drawPath(fond)

    utile = COTE_REFERENCE * 0.60
    cible = QRectF(
        (COTE_REFERENCE - utile) / 2, (COTE_REFERENCE - utile) / 2, utile, utile
    )
    peintre.fillPath(ajuster(marque(True), cible), QColor(MARQUE))


def pixmap_marque(hauteur: int, couleur: str = MARQUE) -> QPixmap:
    """Rend la marque seule, sans son fond arrondi.

    Dans le panneau, le fond du logo aurait la couleur du panneau : il ne se
    verrait pas, sinon par son liseré. Seul le dessin est utile là.
    """
    tracé = marque(True)
    boite = tracé.boundingRect()
    largeur = max(1, round(hauteur * boite.width() / boite.height()))

    image = QPixmap(largeur * 2, hauteur * 2)
    image.setDevicePixelRatio(2.0)
    image.fill(Qt.GlobalColor.transparent)

    peintre = QPainter(image)
    peintre.setRenderHint(QPainter.RenderHint.Antialiasing)
    peintre.fillPath(
        ajuster(tracé, QRectF(0, 0, largeur, hauteur)), QColor(couleur)
    )
    peintre.end()
    return image


def pixmap_logo(cote: int) -> QPixmap:
    """Rend le logo à la taille demandée, fond transparent hors des coins."""
    image = QPixmap(cote, cote)
    image.fill(Qt.GlobalColor.transparent)

    peintre = QPainter(image)
    peintre.scale(cote / COTE_REFERENCE, cote / COTE_REFERENCE)
    dessiner_logo(peintre)
    peintre.end()
    return image
