#!/usr/bin/env python3
"""Installe les phrases de rappel dans le compteur d'attente de Claude Code.

Une notification système suppose une autorisation, se rate en trois secondes,
et macOS refuse parfois de la demander. Le compteur d'attente de Claude Code,
lui, est déjà sous les yeux à chaque tour : c'est le meilleur endroit pour
rappeler qu'on peut réviser au lieu de regarder tourner.

Claude Code lit ces phrases dans `spinnerVerbs` de ~/.claude/settings.json.
Le mode « replace » remplace la liste d'origine ; « append » l'aurait noyée
dans une centaine de verbes anglais.

    python outils/phrases_attente.py
"""

from __future__ import annotations

import json
from pathlib import Path

REGLAGES = Path.home() / ".claude" / "settings.json"

# Claude Code coupe au-delà : mieux vaut une phrase entière qu'une phrase
# tronquée au milieu d'un mot.
LONGUEUR_MAXIMALE = 60

# Le `</>` est le logo du projet, ramené à ce qu'un terminal sait afficher.
PHRASES = (
    "</> Révise pendant que je travaille",
    "</> Connais ton code, pas seulement ton client",
    "</> Explique une fonction en attendant",
    "</> Sais-tu encore ce que fait ce fichier",
    "</> Contrôle avec KnowYourCode",
    "</> Relis ce que tu ne relis plus",
    "</> Une question t'attend en haut à droite",
    "</> Reprends la main sur ton code",
    "</> Profite de l'attente pour réviser",
    "</> Vérifie que tu suis toujours",
    "</> Ton code, tu le connais vraiment",
    "</> Deux minutes pour expliquer ta dernière fonction",
    "</> Ouvre KnowYourCode et prends une question",
    "</> Garde la maîtrise de ce que j'écris",
)


def main() -> int:
    trop_longues = [phrase for phrase in PHRASES if len(phrase) >= LONGUEUR_MAXIMALE]
    if trop_longues:
        raise SystemExit(f"Phrases trop longues : {trop_longues}")

    if not REGLAGES.exists():
        raise SystemExit(f"{REGLAGES} est introuvable. Lancez Claude Code une fois.")

    # Relecture complète puis réécriture complète : le fichier contient les
    # réglages personnels de l'utilisateur, il n'est pas question d'en perdre
    # un seul en n'écrivant que notre bloc.
    contenu = json.loads(REGLAGES.read_text(encoding="utf-8"))
    contenu["spinnerVerbs"] = {"mode": "replace", "verbs": list(PHRASES)}
    REGLAGES.write_text(
        json.dumps(contenu, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    autres = [cle for cle in contenu if cle != "spinnerVerbs"]
    print(f"{len(PHRASES)} phrases installées dans {REGLAGES}.")
    print("Réglages conservés :", ", ".join(autres) if autres else "aucun autre")
    print("Redémarrez Claude Code pour les voir.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
