"""Sur quel projet porter les questions.

Ce module ne surveille rien et ne déclenche rien : il répond seulement à la
question « où l'utilisateur travaille-t-il en ce moment ». La réponse se lit
dans les transcripts de Claude Code, qui gardent le dossier de travail de
chaque session.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol, runtime_checkable

DOSSIER_TRANSCRIPTS = Path.home() / ".claude" / "projects"


@runtime_checkable
class Projet(Protocol):
    """Contrat : dire dans quel dossier chercher du code à faire expliquer.

    Appelé sur le fil principal juste avant d'afficher une question, donc il
    doit rendre la main vite. Rendre `None` est une réponse valable et veut
    dire « je ne sais pas » : le sélecteur se rabattra sur ce qu'il peut.
    """

    def projet_actif(self) -> Path | None:
        """Le dossier du projet sur lequel une session travaille."""
        ...


def _transcript_le_plus_recent(dossier: Path) -> Path | None:
    """Rend le transcript modifié en dernier.

    Le parcours est volontairement plat : les transcripts vivent tous à un
    niveau de profondeur, et un `rglob` sur le dossier personnel coûterait
    trop cher.
    """
    dernier: tuple[Path, float] | None = None
    try:
        projets = list(dossier.iterdir())
    except OSError:
        return None

    for projet in projets:
        try:
            for fichier in projet.glob("*.jsonl"):
                date = fichier.stat().st_mtime
                if dernier is None or date > dernier[1]:
                    dernier = (fichier, date)
        except OSError:
            continue
    return dernier[0] if dernier is not None else None


def _dossier_du_transcript(transcript: Path, lignes_max: int = 400) -> Path | None:
    """Retrouve le dossier de travail à partir du contenu du transcript.

    Le nom du dossier parent encode le chemin en remplaçant les barres par des
    tirets, ce qui n'est pas réversible dès qu'un nom de dossier contient
    lui-même un tiret. Le champ `cwd`, présent sur une partie des lignes, lui,
    est exact.
    """
    try:
        with transcript.open(encoding="utf-8") as fichier:
            for numero, ligne in enumerate(fichier):
                if numero >= lignes_max:
                    break
                try:
                    donnees = json.loads(ligne)
                except json.JSONDecodeError:
                    continue
                chemin = donnees.get("cwd")
                if isinstance(chemin, str) and chemin:
                    return Path(chemin)
    except OSError:
        return None
    return None


class ProjetClaudeCode:
    """Lit le projet en cours dans les transcripts sous ~/.claude/projects/."""

    def __init__(self, dossier: Path = DOSSIER_TRANSCRIPTS) -> None:
        self._dossier = dossier

    def disponible(self) -> bool:
        """Dit s'il y a des transcripts à lire."""
        return self._dossier.is_dir()

    def projet_actif(self) -> Path | None:
        transcript = _transcript_le_plus_recent(self._dossier)
        if transcript is None:
            return None
        return _dossier_du_transcript(transcript)


class ProjetFactice:
    """Rend un dossier fixé d'avance, ou aucun.

    Sert aux vérifications, qui ne doivent dépendre ni du disque ni d'une
    session Claude Code en cours.
    """

    def __init__(self, dossier: Path | None = None) -> None:
        self._dossier = dossier

    def projet_actif(self) -> Path | None:
        return self._dossier
