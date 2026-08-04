"""Calcul des statistiques de progression à partir de l'historique.

Fonctions pures : aucune lecture ni écriture ici, seulement des entrées déjà
chargées et une valeur rendue. Le premier lancement, historique vide, est le
cas le plus fréquent : chaque calcul doit y rendre une valeur neutre plutôt
que de lever une exception.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime

from .modeles import EntreeHistorique

# Fenêtre utilisée à la fois pour la moyenne récente et pour les oublis
# récents : c'est ce qu'on vient de réviser, pas tout l'historique.
NOMBRE_REPONSES_RECENTES = 10
NOMBRE_SCORES_COURBE = 20


@dataclass(frozen=True)
class FonctionMalExpliquee:
    """Une fonction posée au moins une fois, avec son score moyen."""

    identifiant: str
    nom_fonction: str
    chemin_fichier: str
    nombre_de_fois: int
    score_moyen: float


@dataclass(frozen=True)
class OubliRecent:
    """Un point non mentionné lors d'une réponse récente."""

    point: str
    nom_fonction: str
    date: datetime


@dataclass(frozen=True)
class StatistiquesLangage:
    """Score moyen et volume de réponses pour un langage donné."""

    langage: str
    nombre_de_reponses: int
    score_moyen: float


@dataclass(frozen=True)
class Statistiques:
    """Photographie de la progression, prête à être affichée."""

    nombre_de_questions: int
    nombre_de_reponses: int
    nombre_de_passages: int
    score_moyen: float
    score_moyen_recent: float
    scores_recents: list[int] = field(default_factory=list)
    """Ordre chronologique, les plus anciens d'abord : c'est l'ordre d'une courbe."""
    fonctions_mal_expliquees: list[FonctionMalExpliquee] = field(default_factory=list)
    """Triées du pire score moyen au meilleur."""
    oublis_recents: list[OubliRecent] = field(default_factory=list)
    """Les plus récents d'abord."""
    repartition_par_langage: list[StatistiquesLangage] = field(default_factory=list)
    derniere_reponse: datetime | None = None


def calculer_statistiques(entrees: Sequence[EntreeHistorique]) -> Statistiques:
    """Calcule les statistiques à partir des entrées d'historique, une passe."""
    reponses = [e for e in entrees if e.issue == "repondu" and e.score is not None]
    passages = [e for e in entrees if e.issue == "passe"]
    dix_dernieres = reponses[-NOMBRE_REPONSES_RECENTES:]

    return Statistiques(
        nombre_de_questions=len(entrees),
        nombre_de_reponses=len(reponses),
        nombre_de_passages=len(passages),
        score_moyen=_moyenne(e.score for e in reponses),
        score_moyen_recent=_moyenne(e.score for e in dix_dernieres),
        scores_recents=[e.score for e in reponses[-NOMBRE_SCORES_COURBE:]],
        fonctions_mal_expliquees=_fonctions_mal_expliquees(reponses),
        oublis_recents=_oublis_recents(dix_dernieres),
        repartition_par_langage=_repartition_par_langage(reponses),
        derniere_reponse=reponses[-1].date if reponses else None,
    )


def _moyenne(scores: Iterable[int]) -> float:
    valeurs = list(scores)
    return sum(valeurs) / len(valeurs) if valeurs else 0.0


def _fonctions_mal_expliquees(
    reponses: Sequence[EntreeHistorique],
) -> list[FonctionMalExpliquee]:
    par_identifiant: dict[str, list[EntreeHistorique]] = defaultdict(list)
    for reponse in reponses:
        par_identifiant[reponse.identifiant].append(reponse)

    fonctions = [
        FonctionMalExpliquee(
            identifiant=identifiant,
            # Le nom ou le chemin d'une fonction peut changer d'une réponse à
            # l'autre si le fichier a bougé entretemps : on garde le plus récent.
            nom_fonction=groupe[-1].nom_fonction,
            chemin_fichier=groupe[-1].chemin_fichier,
            nombre_de_fois=len(groupe),
            score_moyen=_moyenne(r.score for r in groupe),
        )
        for identifiant, groupe in par_identifiant.items()
    ]
    fonctions.sort(key=lambda f: f.score_moyen)
    return fonctions


def _oublis_recents(dix_dernieres: Sequence[EntreeHistorique]) -> list[OubliRecent]:
    oublis: list[OubliRecent] = []
    for reponse in reversed(dix_dernieres):
        for point in reponse.points_oublies:
            oublis.append(
                OubliRecent(point=point, nom_fonction=reponse.nom_fonction, date=reponse.date)
            )
    return oublis


def _repartition_par_langage(
    reponses: Sequence[EntreeHistorique],
) -> list[StatistiquesLangage]:
    par_langage: dict[str, list[int]] = defaultdict(list)
    for reponse in reponses:
        par_langage[reponse.langage].append(reponse.score)

    return [
        StatistiquesLangage(
            langage=langage, nombre_de_reponses=len(scores), score_moyen=_moyenne(scores)
        )
        for langage, scores in sorted(par_langage.items())
    ]
