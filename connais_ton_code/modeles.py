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
    """Le retour d'un modèle sur une explication tapée. Vestige.

    Plus personne ne devrait en produire : une carte se corrige en local et
    rend une `Correction`. La classe survit le temps que le panneau,
    l'orchestrateur et l'évaluateur passent aux cartes à leur tour — la
    supprimer aujourd'hui casserait leurs imports sans rien apporter.
    """

    verdict: str
    """Une ou deux phrases de synthèse, affichées en premier."""
    score: int
    """Note sur 100."""
    points_oublies: list[str] = field(default_factory=list)
    """Ce que la réponse n'a pas mentionné, un point par entrée."""


# Les trois natures de ligne que l'historique peut contenir. `ANCIENNE` n'est
# jamais écrite : c'est l'étiquette que la relecture pose sur une explication
# notée de l'ancien exercice, qui n'a plus de carte à montrer mais reste la
# preuve qu'on a travaillé ce jour-là.
CARTE = "carte"
PASSE = "passe"
ANCIENNE = "ancienne"


@dataclass(frozen=True)
class EntreeHistorique:
    """Une ligne de l'historique, relue depuis le disque et validée.

    Une entrée est d'abord une carte répondue : sa forme, la notion qu'elle
    enseignait, sa catégorie, la ligne visée, et juste ou faux. Le reste
    identifie l'extrait d'où elle venait, ce qui permet de ne pas le
    reproposer aussitôt.

    `forme`, `categorie`, `notion`, `ligne` et `juste` ne veulent rien dire en
    dehors d'`issue == CARTE` : un passage n'a pas de bonne réponse, et une
    entrée de l'ancien exercice n'a pas de forme.
    """

    identifiant: str
    chemin_fichier: str
    nom_fonction: str
    langage: str
    date: datetime
    issue: str
    """`CARTE`, `PASSE` ou `ANCIENNE`."""
    forme: str = ""
    """Nom du membre de `cartes.Forme` : "QCM", "REPERER"…"""
    categorie: str = ""
    """Une des catégories de `reperage` : langage, robustesse, sécurité."""
    notion: str | None = None
    """La notion enseignée, quand la ligne en portait une."""
    ligne: int = 0
    """Ligne visée dans l'extrait, numérotée à partir de 1."""
    juste: bool = False
