"""Réglages persistés entre deux lancements : pour l'instant, les positions.

Le fichier est distinct de l'historique : perdre une position de fenêtre est
sans conséquence, perdre l'historique en aurait.
"""

from __future__ import annotations

from pathlib import Path

from .stockage import dossier_donnees, ecrire_json, lire_json

NOM_FICHIER = "reglages.json"
VERSION_FORMAT = 1


class Reglages:
    """Lit et écrit les préférences des fenêtres, repérées par un nom."""

    def __init__(self, chemin: Path | None = None) -> None:
        self.chemin = chemin or (dossier_donnees() / NOM_FICHIER)
        contenu = lire_json(self.chemin, {})
        self._contenu: dict = contenu if isinstance(contenu, dict) else {}

    def position(self, nom: str) -> tuple[int, int] | None:
        """Rend la dernière position connue, ou `None` au premier lancement."""
        positions = self._contenu.get("positions")
        if not isinstance(positions, dict):
            return None
        position = positions.get(nom)
        if not isinstance(position, dict):
            return None
        x, y = position.get("x"), position.get("y")
        if isinstance(x, int) and isinstance(y, int):
            return x, y
        return None

    def enregistrer_position(self, nom: str, x: int, y: int) -> None:
        self._contenu["version"] = VERSION_FORMAT
        positions = self._contenu.setdefault("positions", {})
        positions[nom] = {"x": x, "y": y}
        ecrire_json(self.chemin, self._contenu)
