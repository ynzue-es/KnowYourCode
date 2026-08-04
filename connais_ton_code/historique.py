"""Mémoire des questions déjà posées et des réponses données.

Deux usages, l'un immédiat et l'autre à venir : ne pas reposer deux fois la
même question, et pouvoir relire sa progression dans le temps.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .modeles import EntreeHistorique, Evaluation, Extrait
from .stockage import dossier_donnees, ecrire_json, lire_json

NOM_FICHIER = "historique.json"
VERSION_FORMAT = 1


def _maintenant_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _entree_depuis_brut(brut: object) -> EntreeHistorique | None:
    """Valide et convertit une entrée lue du JSON, ou `None` si elle ne l'est pas.

    Le fichier peut contenir des traces d'un format plus ancien ou une écriture
    interrompue : mieux vaut ignorer la ligne que faire tomber l'application au
    démarrage.
    """
    if not isinstance(brut, dict):
        return None
    try:
        identifiant = brut["identifiant"]
        chemin_fichier = brut["chemin_fichier"]
        nom_fonction = brut["nom_fonction"]
        langage = brut["langage"]
        issue = brut["issue"]
        date = datetime.fromisoformat(brut["date"])
    except (KeyError, TypeError, ValueError):
        return None
    champs_texte = (identifiant, chemin_fichier, nom_fonction, langage, issue)
    if not all(isinstance(champ, str) for champ in champs_texte):
        return None
    if issue not in ("repondu", "passe"):
        return None

    score: int | None = None
    verdict: str | None = None
    reponse: str | None = None
    points_oublies: list[str] = []
    if issue == "repondu":
        try:
            score = int(brut["score"])
            verdict = brut["verdict"]
        except (KeyError, TypeError, ValueError):
            return None
        if not isinstance(verdict, str):
            return None
        reponse_brute = brut.get("reponse")
        if reponse_brute is not None and not isinstance(reponse_brute, str):
            return None
        reponse = reponse_brute
        points_bruts = brut.get("points_oublies", [])
        if not isinstance(points_bruts, list) or not all(
            isinstance(point, str) for point in points_bruts
        ):
            return None
        points_oublies = list(points_bruts)

    return EntreeHistorique(
        identifiant=identifiant,
        chemin_fichier=chemin_fichier,
        nom_fonction=nom_fonction,
        langage=langage,
        date=date,
        issue=issue,
        score=score,
        verdict=verdict,
        reponse=reponse,
        points_oublies=points_oublies,
    )


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

    def entrees(self) -> list[EntreeHistorique]:
        """Les entrées valides, la plus ancienne d'abord.

        Le fichier n'étant que réordonné par ajout, l'ordre sur disque est
        déjà chronologique ; les entrées invalides sont simplement écartées.
        """
        entrees = (_entree_depuis_brut(brute) for brute in self._entrees)
        return [entree for entree in entrees if entree is not None]

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
