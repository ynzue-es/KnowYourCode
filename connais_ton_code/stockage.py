"""Emplacement et écriture des fichiers JSON locaux.

Tout est écrit sous un seul dossier, en clair, pour rester inspectable à la
main : ces données servent à mesurer sa propre progression, pas à alimenter un
service.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

VARIABLE_DOSSIER = "KNOWYOURCODE_DOSSIER"


def dossier_donnees() -> Path:
    """Rend le dossier des données, créé si besoin.

    La variable d'environnement sert aux tests et aux vérifications, qui ne
    doivent pas polluer l'historique réel.
    """
    brut = os.environ.get(VARIABLE_DOSSIER)
    dossier = Path(brut).expanduser() if brut else Path.home() / ".knowyourcode"
    dossier.mkdir(parents=True, exist_ok=True)
    return dossier


def lire_json(chemin: Path, defaut: Any) -> Any:
    """Lit un JSON en tolérant l'absence et la corruption du fichier.

    Un fichier illisible est mis de côté plutôt que supprimé : c'est peut-être
    des mois d'historique, et l'application doit quand même démarrer.
    """
    if not chemin.exists():
        return defaut

    try:
        return json.loads(chemin.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        try:
            chemin.replace(chemin.with_suffix(chemin.suffix + ".corrompu"))
        except OSError:
            pass
        return defaut


def ecrire_json(chemin: Path, contenu: Any) -> None:
    """Écrit un JSON de façon atomique.

    L'application peut être tuée d'un Ctrl+C au milieu d'une écriture ; passer
    par un fichier temporaire évite de laisser un historique tronqué.
    """
    temporaire = chemin.with_suffix(chemin.suffix + ".tmp")
    temporaire.write_text(
        json.dumps(contenu, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporaire.replace(chemin)
