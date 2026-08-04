"""Structures de données échangées entre les briques de l'application.

Ces objets sont volontairement passifs et sans dépendance à Qt : les briques
bouchonnées comme leurs futures versions réelles doivent pouvoir être testées
sans interface graphique.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class Extrait:
    """Un bout de code soumis à l'utilisateur.

    L'identifiant sert de clé de déduplication dans l'historique : il doit
    rester stable d'un lancement à l'autre pour un même bout de code, sinon la
    même fonction sera reposée indéfiniment. La future sélection par diff le
    calculera à partir du chemin et du nom de la fonction.
    """

    identifiant: str
    chemin_fichier: str
    nom_fonction: str
    langage: str
    """Nom de lexer Pygments : "python", "typescript" ou "tsx"."""
    code: str


@dataclass(frozen=True)
class Evaluation:
    """Le retour rendu à l'utilisateur après sa réponse."""

    verdict: str
    """Une ou deux phrases de synthèse, affichées en premier."""
    score: int
    """Note sur 100, utilisée plus tard pour mesurer la progression."""
    points_oublies: list[str] = field(default_factory=list)
    """Ce que la réponse n'a pas mentionné, un point par entrée."""


@dataclass(frozen=True)
class EntreeHistorique:
    """Une ligne de l'historique, relue depuis le disque et validée.

    Reflète ce qu'écrit `Historique._ajouter` : `score`, `verdict` et
    `reponse` n'existent que pour les entrées répondues, jamais pour un
    passage.
    """

    identifiant: str
    chemin_fichier: str
    nom_fonction: str
    langage: str
    date: datetime
    issue: str
    """"repondu" ou "passe"."""
    score: int | None = None
    verdict: str | None = None
    reponse: str | None = None
    points_oublies: list[str] = field(default_factory=list)
