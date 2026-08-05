"""Calcul de la progression à partir de l'historique.

Fonctions pures : aucune lecture ni écriture ici, seulement des entrées déjà
chargées et une valeur rendue. Le premier lancement, historique vide, est le
cas le plus fréquent : chaque calcul doit y rendre une valeur neutre plutôt
que de lever une exception.

Ce qu'on mesure a changé avec l'exercice. Une carte est juste ou fausse, il
n'y a plus de note à moyenner, et une moyenne de justes n'a jamais fait
revenir personne. Restent deux chiffres qui font revenir : la série de jours
d'affilée, qu'on ne veut pas casser, et la liste des notions qu'on rate, qui
dit quoi réviser. Tout le reste est du décor autour de ces deux-là.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from .modeles import ANCIENNE, CARTE, PASSE, EntreeHistorique

# Douze semaines de calendrier : assez pour voir une habitude s'installer ou
# se perdre, assez peu pour tenir sur une ligne.
JOURS_ACTIVITE = 7 * 12


@dataclass(frozen=True)
class Reussite:
    """Combien de cartes ont été réussies sur un sujet donné.

    Le sujet est une notion — « fermeture », « court-circuit » — ou une
    catégorie. Le même objet sert aux deux : ce qui se compte se compte
    pareil.
    """

    sujet: str
    justes: int
    total: int

    @property
    def taux(self) -> float:
        """Entre 0 et 1. Un sujet jamais posé n'apparaît pas dans la liste."""
        return self.justes / self.total if self.total else 0.0


@dataclass(frozen=True)
class JourActivite:
    """Le nombre de cartes répondues un jour donné."""

    jour: date
    nombre: int


@dataclass(frozen=True)
class Statistiques:
    """Photographie de la progression, prête à être affichée."""

    serie_en_cours: int = 0
    """Jours d'affilée avec au moins une carte, jusqu'à aujourd'hui."""
    meilleure_serie: int = 0
    """La plus longue jamais tenue, y compris celle qui court."""
    faite_aujourdhui: bool = False
    """Vrai si la journée est déjà remplie : la série ne risque plus rien."""
    jours_actifs: int = 0

    nombre_de_cartes: int = 0
    nombre_de_justes: int = 0
    taux_de_reussite: float = 0.0
    """Entre 0 et 1, sur toutes les cartes répondues."""
    nombre_de_passages: int = 0

    notions: list[Reussite] = field(default_factory=list)
    """Triées : la plus ratée d'abord. C'est la liste qui fait le cours."""
    categories: list[Reussite] = field(default_factory=list)
    """Même tri, sur langage, robustesse et sécurité."""

    fonctions_couvertes: int = 0
    fichiers_couverts: int = 0
    derniere_carte: datetime | None = None
    activite: list[JourActivite] = field(default_factory=list)
    """Les douze dernières semaines, du plus ancien au plus récent."""


def calculer_statistiques(
    entrees: Sequence[EntreeHistorique], aujourdhui: date | None = None
) -> Statistiques:
    """Calcule la progression à partir des entrées d'historique, une passe.

    `aujourdhui` est un paramètre plutôt qu'un appel à l'horloge : la série et
    le calendrier dépendent de la date du jour, et un calcul qui lit l'heure
    tout seul ne se vérifie pas.
    """
    jour_courant = aujourdhui or date.today()
    cartes = [e for e in entrees if e.issue == CARTE]
    passages = [e for e in entrees if e.issue == PASSE]
    comptes = _comptes_par_jour(entrees)
    jours = set(comptes)
    justes = sum(1 for carte in cartes if carte.juste)

    return Statistiques(
        serie_en_cours=_serie_en_cours(jours, jour_courant),
        meilleure_serie=_meilleure_serie(jours),
        faite_aujourdhui=jour_courant in jours,
        jours_actifs=len(jours),
        nombre_de_cartes=len(cartes),
        nombre_de_justes=justes,
        taux_de_reussite=justes / len(cartes) if cartes else 0.0,
        nombre_de_passages=len(passages),
        notions=_reussites(cartes, lambda carte: carte.notion),
        categories=_reussites(cartes, lambda carte: carte.categorie),
        fonctions_couvertes=len({e.identifiant for e in entrees}),
        fichiers_couverts=len({e.chemin_fichier for e in entrees}),
        derniere_carte=cartes[-1].date if cartes else None,
        activite=_activite(comptes, jour_courant),
    )


def _comptes_par_jour(entrees: Sequence[EntreeHistorique]) -> dict[date, int]:
    """Le nombre d'exercices faits chaque jour où il s'en est fait un.

    Un passage ne compte pas : ouvrir le panneau et refuser l'extrait n'est
    pas un exercice, et une série qu'on entretient en passant ne mesurerait
    plus rien. Les entrées de l'ancien exercice, elles, comptent : c'était un
    vrai travail, et un changement de format n'est pas une raison de faire
    disparaître trois semaines de régularité.
    """
    comptes: dict[date, int] = defaultdict(int)
    for entree in entrees:
        if entree.issue in (CARTE, ANCIENNE):
            comptes[entree.date.date()] += 1
    return dict(comptes)


def _serie_en_cours(jours: set[date], jour: date) -> int:
    """Jours consécutifs avec au moins une carte.

    Une série interrompue vaut zéro, pas son ancienne longueur : afficher
    « 7 jours » à quelqu'un qui n'a rien fait depuis un mois serait un
    mensonge encourageant. Une série qui s'arrête hier compte encore, en
    revanche : la journée n'est pas finie, il est encore temps.
    """
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


def _meilleure_serie(jours: set[date]) -> int:
    """La plus longue suite de jours consécutifs, depuis toujours.

    C'est le repère qui donne envie de battre son record quand la série en
    cours vient de tomber à un.
    """
    meilleure = 0
    for jour in jours:
        # On ne remonte une suite que depuis son premier jour : sans cette
        # garde, une suite de trente jours serait parcourue trente fois.
        if jour - timedelta(days=1) in jours:
            continue
        longueur = 0
        courant = jour
        while courant in jours:
            longueur += 1
            courant += timedelta(days=1)
        meilleure = max(meilleure, longueur)
    return meilleure


def _reussites(
    cartes: Sequence[EntreeHistorique],
    sujet: Callable[[EntreeHistorique], str | None],
) -> list[Reussite]:
    """Le taux de réussite par sujet, le plus raté en tête.

    Le tri met le taux d'abord, puis le volume : entre deux sujets ratés
    autant, celui qui revient le plus souvent est le plus urgent à réviser.
    Les cartes sans sujet — une ligne intéressante qui ne porte aucun nom
    enseignable — sont écartées plutôt que rangées sous une étiquette vide.
    """
    groupes: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for carte in cartes:
        nom = sujet(carte)
        if not nom:
            continue
        groupes[nom][0] += 1 if carte.juste else 0
        groupes[nom][1] += 1

    reussites = [
        Reussite(sujet=nom, justes=justes, total=total)
        for nom, (justes, total) in groupes.items()
    ]
    reussites.sort(key=lambda r: (r.taux, -r.total, r.sujet))
    return reussites


def _activite(comptes: dict[date, int], jour: date) -> list[JourActivite]:
    """Le calendrier des douze dernières semaines, jours vides compris.

    Les jours sans carte comptent autant que les autres : c'est justement
    leur alignement qui montre les trous.
    """
    debut = jour - timedelta(days=JOURS_ACTIVITE - 1)
    return [
        JourActivite(
            jour=debut + timedelta(days=decalage),
            nombre=comptes.get(debut + timedelta(days=decalage), 0),
        )
        for decalage in range(JOURS_ACTIVITE)
    ]
