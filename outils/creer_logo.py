#!/usr/bin/env python3
"""Écrit le logo du projet en SVG et en PNG.

Le dessin lui-même vit dans `connais_ton_code/logo.py`, parce qu'il sert aussi
à l'icône du Dock au moment de l'exécution. Ce script ne fait que le poser
dans des fichiers, pour le README et pour l'icône de l'application.

Les glyphes sont convertis en tracés avant d'être écrits : un SVG qui
référencerait une police s'afficherait autrement sur une machine qui ne l'a
pas, ce qui arrive à peu près partout hors de macOS.

    python outils/creer_logo.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtCore import QRectF, QSize
from PyQt6.QtGui import QPainter
from PyQt6.QtSvg import QSvgGenerator
from PyQt6.QtWidgets import QApplication

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from connais_ton_code.logo import COTE_REFERENCE, dessiner_logo, pixmap_logo  # noqa: E402


def ecrire_svg(chemin: Path) -> None:
    generateur = QSvgGenerator()
    generateur.setFileName(str(chemin))
    generateur.setSize(QSize(COTE_REFERENCE, COTE_REFERENCE))
    generateur.setViewBox(QRectF(0, 0, COTE_REFERENCE, COTE_REFERENCE))
    generateur.setTitle("KnowYourCode")

    peintre = QPainter()
    peintre.begin(generateur)
    dessiner_logo(peintre)
    peintre.end()


def main() -> int:
    # La référence doit vivre jusqu'à la fin : sans elle, l'application est
    # ramassée et la base de polices disparaît sous les pieds du peintre.
    _application = QApplication(sys.argv)  # noqa: F841

    dossier = RACINE / "ressources"
    dossier.mkdir(exist_ok=True)

    ecrire_svg(dossier / "logo.svg")
    pixmap_logo(512).save(str(dossier / "logo.png"))
    print("écrits :", dossier / "logo.svg", "et", dossier / "logo.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
