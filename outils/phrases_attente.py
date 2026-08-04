#!/usr/bin/env python3
"""Pose ou retire le rappel dans le compteur d'attente de Claude Code.

L'interrupteur du panneau fait la même chose. Ce script existe pour ceux qui
préfèrent la ligne de commande, et pour vérifier ce qui a été écrit.

    python outils/phrases_attente.py            pose le rappel
    python outils/phrases_attente.py --retirer  le retire
"""

from __future__ import annotations

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from connais_ton_code import rappel  # noqa: E402


def main() -> int:
    if not rappel.REGLAGES_CLAUDE.exists():
        print(f"{rappel.REGLAGES_CLAUDE} est introuvable. Lancez Claude Code une fois.")
        return 1

    retrait = "--retirer" in sys.argv[1:]
    reussi = rappel.retirer() if retrait else rappel.installer()
    if not reussi:
        print(f"{rappel.REGLAGES_CLAUDE} est illisible : rien n'a été modifié.")
        return 1

    if retrait:
        print("Rappel retiré. Claude Code retrouve ses propres verbes.")
    else:
        phrases = rappel.phrases()
        print(f"{len(phrases)} phrases posées dans {rappel.REGLAGES_CLAUDE}.")
        print(f"Pour les vôtres, écrivez-les dans {rappel.chemin_phrases()}.")

    print("Redémarrez Claude Code pour voir le changement.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
