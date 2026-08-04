"""Mémoire des questions déjà posées et des réponses données.

Deux usages, l'un immédiat et l'autre à venir : ne pas reposer deux fois la
même question, et pouvoir relire sa progression dans le temps.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .modeles import Evaluation, Extrait
from .stockage import dossier_donnees, ecrire_json, lire_json

NOM_FICHIER = "historique.json"
VERSION_FORMAT = 1


def _maintenant_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


class Historique:
    """Journal append-only des questions posées, adossé à un fichier JSON.

    Le fichier entier est relu au démarrage et réécrit à chaque ajout : à
    quelques questions par jour, la simplicité vaut mieux qu'un format
    incrémental.
    """

    def __init__(self, chemin: Path | None = None) -> None:
        self.chemin = chemin or (dossier_donnees() / NOM_FICHIER)
        contenu = lire_json(self.chemin, {"version": VERSION_FORMAT, "entrees": []})
        entrees = contenu.get("entrees") if isinstance(contenu, dict) else None
        self._entrees: list[dict] = entrees if isinstance(entrees, list) else []

    def identifiants_deja_vus(self) -> set[str]:
        """Les extraits déjà proposés, répondus ou passés."""
        return {
            entree["identifiant"]
            for entree in self._entrees
            if isinstance(entree, dict) and "identifiant" in entree
        }

    def enregistrer_reponse(
        self, extrait: Extrait, reponse: str, evaluation: Evaluation
    ) -> None:
        self._ajouter(
            extrait,
            {
                "issue": "repondu",
                "reponse": reponse,
                "verdict": evaluation.verdict,
                "score": evaluation.score,
                "points_oublies": list(evaluation.points_oublies),
            },
        )

    def enregistrer_passage(self, extrait: Extrait) -> None:
        """Note qu'un extrait a été passé, pour ne pas le reproposer aussitôt."""
        self._ajouter(extrait, {"issue": "passe"})

    def _ajouter(self, extrait: Extrait, details: dict) -> None:
        self._entrees.append(
            {
                "identifiant": extrait.identifiant,
                "chemin_fichier": extrait.chemin_fichier,
                "nom_fonction": extrait.nom_fonction,
                "langage": extrait.langage,
                "date": _maintenant_iso(),
                **details,
            }
        )
        ecrire_json(
            self.chemin, {"version": VERSION_FORMAT, "entrees": self._entrees}
        )
