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
from datetime import date, datetime, timedelta

from .modeles import EntreeHistorique

# Fenêtre utilisée à la fois pour la moyenne récente et pour les oublis
# récents : c'est ce qu'on vient de réviser, pas tout l'historique.
NOMBRE_REPONSES_RECENTES = 10
NOMBRE_SCORES_COURBE = 20

# Douze semaines de calendrier : assez pour voir une habitude s'installer ou
# se perdre, assez peu pour tenir sur une ligne.
JOURS_ACTIVITE = 7 * 12

# La tendance compare deux paquets de même taille : sans cela, une bonne
# journée récente pèserait autant qu'un mois de moyenne.
TAILLE_COMPARAISON = 5

# Les tranches disent quelque chose que la moyenne cache : on peut avoir 65 de
# moyenne en étant régulier, ou en alternant les 30 et les 95.
TRANCHES = ((0, "0 à 39"), (40, "40 à 59"), (60, "60 à 79"), (80, "80 à 100"))


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
class JourActivite:
    """Le nombre de réponses données un jour donné."""

    jour: date
    nombre: int


@dataclass(frozen=True)
class TrancheScores:
    """Combien de réponses sont tombées dans une tranche de notes."""

    libelle: str
    borne_basse: int
    nombre: int


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

    serie_en_cours: int = 0
    """Jours consécutifs avec au moins une réponse, jusqu'à aujourd'hui."""
    meilleur_score: int = 0
    tendance: float | None = None
    """Écart entre les cinq dernières réponses et les cinq précédentes."""
    fonctions_couvertes: int = 0
    fichiers_couverts: int = 0
    activite: list[JourActivite] = field(default_factory=list)
    """Les douze dernières semaines, du plus ancien au plus récent."""
    repartition_scores: list[TrancheScores] = field(default_factory=list)


def calculer_statistiques(
    entrees: Sequence[EntreeHistorique], aujourdhui: date | None = None
) -> Statistiques:
    """Calcule les statistiques à partir des entrées d'historique, une passe.

    `aujourdhui` est un paramètre plutôt qu'un appel à l'horloge : la série et
    le calendrier dépendent de la date du jour, et un calcul qui lit l'heure
    tout seul ne se vérifie pas.
    """
    jour_courant = aujourdhui or date.today()
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
        serie_en_cours=_serie_en_cours(reponses, jour_courant),
        meilleur_score=max((r.score for r in reponses), default=0),
        tendance=_tendance(reponses),
        fonctions_couvertes=len({e.identifiant for e in entrees}),
        fichiers_couverts=len({e.chemin_fichier for e in entrees}),
        activite=_activite(reponses, jour_courant),
        repartition_scores=_repartition_scores(reponses),
    )


def _serie_en_cours(reponses: Sequence[EntreeHistorique], jour: date) -> int:
    """Jours consécutifs avec au moins une réponse.

    Une série interrompue vaut zéro, pas son ancienne longueur : afficher
    « 7 jours » à quelqu'un qui n'a rien fait depuis un mois serait un
    mensonge encourageant.
    """
    jours = {reponse.date.date() for reponse in reponses}
    if not jours:
        return 0

    depart = jour if jour in jours else jour - timedelta(days=1)
    if depart not in jours:
        return 0

    serie = 0
    while depart in jours:
        serie += 1
        depart -= timedelta(days=1)
    return serie


def _tendance(reponses: Sequence[EntreeHistorique]) -> float | None:
    """Écart de moyenne entre les dernières réponses et celles d'avant.

    Rend `None` tant qu'il n'y a pas deux paquets complets : une tendance
    calculée sur deux réponses ne dirait rien.
    """
    if len(reponses) < TAILLE_COMPARAISON * 2:
        return None
    recentes = reponses[-TAILLE_COMPARAISON:]
    precedentes = reponses[-TAILLE_COMPARAISON * 2 : -TAILLE_COMPARAISON]
    return _moyenne(r.score for r in recentes) - _moyenne(
        r.score for r in precedentes
    )


def _activite(
    reponses: Sequence[EntreeHistorique], jour: date
) -> list[JourActivite]:
    """Le calendrier des douze dernières semaines, jours vides compris.

    Les jours sans réponse comptent autant que les autres : c'est justement
    leur alignement qui montre les trous.
    """
    comptes: dict[date, int] = defaultdict(int)
    for reponse in reponses:
        comptes[reponse.date.date()] += 1

    debut = jour - timedelta(days=JOURS_ACTIVITE - 1)
    return [
        JourActivite(jour=debut + timedelta(days=decalage),
                     nombre=comptes.get(debut + timedelta(days=decalage), 0))
        for decalage in range(JOURS_ACTIVITE)
    ]


def _repartition_scores(
    reponses: Sequence[EntreeHistorique],
) -> list[TrancheScores]:
    comptes = [0] * len(TRANCHES)
    for reponse in reponses:
        for rang in range(len(TRANCHES) - 1, -1, -1):
            if reponse.score >= TRANCHES[rang][0]:
                comptes[rang] += 1
                break

    return [
        TrancheScores(libelle=libelle, borne_basse=borne, nombre=comptes[rang])
        for rang, (borne, libelle) in enumerate(TRANCHES)
    ]


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
