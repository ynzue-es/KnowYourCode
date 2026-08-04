#!/usr/bin/env python3
"""Génère le logo du projet en SVG et en PNG.

Le logo est décrit ici plutôt que dessiné dans un éditeur : il tient en une
vingtaine de lignes, et le régénérer après un changement de couleur coûte une
commande au lieu d'une après-midi.

Les glyphes sont convertis en tracés avant d'être écrits : un SVG qui
référencerait une police s'afficherait autrement sur une machine qui ne l'a
pas, ce qui arrive à peu près partout hors de macOS.

    python outils/creer_logo.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtCore import QRectF, QSize, Qt
from PyQt6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPainterPath, QPixmap
from PyQt6.QtSvg import QSvgGenerator
from PyQt6.QtWidgets import QApplication

COTE = 512
RAYON = 112

FOND = "#1f2023"
BORDURE = "#33363b"
ACCENT = "#4c8dff"
TEXTE = "#f2f3f5"

# Les accolades disent « du code », le point d'interrogation dit « explique ».
# Réunis, ils tiennent encore à seize pixels dans une barre de menus.
MORCEAUX = (("{", ACCENT), ("?", TEXTE), ("}", ACCENT))

# Négatif : Menlo réserve de l'air autour de chaque glyphe, et sans le
# reprendre les trois signes se lisent comme trois symboles au lieu d'un.
ESPACEMENT = -18

RACINE = Path(__file__).resolve().parent.parent


def _police() -> QFont:
    police = QFont("Menlo")
    police.setPixelSize(250)
    police.setBold(True)
    return police


def dessiner(peintre: QPainter) -> None:
    peintre.setRenderHint(QPainter.RenderHint.Antialiasing)

    cadre = QRectF(6, 6, COTE - 12, COTE - 12)
    fond = QPainterPath()
    fond.addRoundedRect(cadre, RAYON, RAYON)
    peintre.fillPath(fond, QColor(FOND))

    stylo = peintre.pen()
    stylo.setColor(QColor(BORDURE))
    stylo.setWidthF(6)
    peintre.setPen(stylo)
    peintre.drawPath(fond)

    police = _police()
    metriques = QFontMetricsF(police)
    largeurs = [metriques.horizontalAdvance(texte) for texte, _ in MORCEAUX]
    total = sum(largeurs) + ESPACEMENT * (len(MORCEAUX) - 1)

    position = (COTE - total) / 2
    # Le centrage se fait sur la hauteur des capitales, pas sur celle de la
    # police : les jambages inutilisés décaleraient le bloc vers le haut.
    ligne_de_base = (COTE + metriques.capHeight()) / 2

    for (texte, couleur), largeur in zip(MORCEAUX, largeurs):
        tracé = QPainterPath()
        tracé.addText(position, ligne_de_base, police, texte)
        peintre.fillPath(tracé, QColor(couleur))
        position += largeur + ESPACEMENT


def ecrire_svg(chemin: Path) -> None:
    generateur = QSvgGenerator()
    generateur.setFileName(str(chemin))
    generateur.setSize(QSize(COTE, COTE))
    generateur.setViewBox(QRectF(0, 0, COTE, COTE))
    generateur.setTitle("KnowYourCode")

    peintre = QPainter()
    peintre.begin(generateur)
    dessiner(peintre)
    peintre.end()


def ecrire_png(chemin: Path, cote: int) -> None:
    image = QPixmap(cote, cote)
    image.fill(Qt.GlobalColor.transparent)

    peintre = QPainter(image)
    peintre.scale(cote / COTE, cote / COTE)
    dessiner(peintre)
    peintre.end()

    image.save(str(chemin))


def main() -> int:
    # La référence doit vivre jusqu'à la fin : sans elle, l'application est
    # ramassée et la base de polices disparaît sous les pieds du peintre.
    _application = QApplication(sys.argv)  # noqa: F841
    dossier = RACINE / "ressources"
    dossier.mkdir(exist_ok=True)

    ecrire_svg(dossier / "logo.svg")
    ecrire_png(dossier / "logo.png", 512)
    print("écrits :", dossier / "logo.svg", "et", dossier / "logo.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
