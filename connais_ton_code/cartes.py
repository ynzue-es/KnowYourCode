"""Les cartes posées sur un extrait, et leur correction.

Une série est une poignée de cartes portant toutes sur le même bout de code.
Chacune tient en un geste — un clic, un mot — et se corrige ici, sur place :
le retour doit arriver dans la seconde, sinon on décroche avant d'avoir lu le
« pourquoi », qui est tout l'intérêt de l'exercice.

Ce module est le contrat entre le générateur, qui fabrique les cartes, et le
panneau, qui les pose. Il ne connaît ni Qt ni le modèle de langue.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from enum import Enum, auto

from .modeles import Extrait


class Forme(Enum):
    """Les cinq façons de poser une question sur un extrait."""

    QCM = auto()
    """Quatre propositions, une seule juste."""

    REPERER = auto()
    """« Quelle ligne fait ceci ? » : on répond en cliquant dans le code."""

    PREDIRE = auto()
    """« Que vaut ceci ? » : un mot, ou une valeur écrite en un mot."""

    VRAI_FAUX = auto()
    """Une affirmation sur le code, à accepter ou à rejeter."""

    NOMMER = auto()
    """« Comment s'appelle ce que fait la ligne 7 ? » : un mot."""


@dataclass(frozen=True)
class Carte:
    """Une question et de quoi la corriger sans rien demander à personne."""

    forme: Forme
    question: str
    """Posée telle quelle à l'écran, donc courte et sans ambiguïté."""
    reponse: str
    """La bonne réponse, écrite telle qu'on l'annonce.

    Pour une carte REPERER, c'est le numéro de la ligne cherchée.
    """
    explication: str
    """La prose qui dit pourquoi. C'est ce qu'on vient chercher."""
    options: tuple[str, ...] = ()
    """Les propositions de QCM ou de VRAI_FAUX, dans l'ordre d'affichage."""
    variantes: tuple[str, ...] = ()
    """D'autres formulations acceptées, pour les réponses tapées.

    Un mot juste écrit autrement reste juste : refuser « décorateur » parce
    qu'on attendait « décoration » n'apprend rien à personne.
    """
    ligne: int = 0
    """La ligne de l'extrait sur laquelle porter le regard, à partir de un.

    Zéro quand il n'y a rien à montrer. Une carte REPERER vaut toujours zéro :
    la ligne est justement ce qu'on cherche, la souligner donnerait la réponse.
    """


@dataclass(frozen=True)
class Serie:
    """Les trois ou quatre cartes posées d'affilée sur un même extrait."""

    extrait: Extrait
    cartes: tuple[Carte, ...]


@dataclass(frozen=True)
class Correction:
    """Ce qu'on affiche juste après une réponse."""

    juste: bool
    reponse_donnee: str
    bonne_reponse: str
    """Rendue en clair, même quand la réponse était juste."""
    explication: str


def bonne_reponse(carte: Carte) -> str:
    """Rend la bonne réponse telle qu'on la montre à l'utilisateur."""
    if carte.forme is Forme.REPERER:
        return f"ligne {carte.reponse}"
    return carte.reponse


def corriger(carte: Carte, reponse: str) -> Correction:
    """Corrige une réponse sur place, sans réseau ni modèle.

    La comparaison ignore la casse, les accents et la ponctuation de bord :
    l'exercice porte sur la lecture du code, pas sur l'orthographe.
    """
    donnee = _normaliser(reponse)
    attendues = {_normaliser(texte) for texte in (carte.reponse, *carte.variantes)}
    return Correction(
        juste=bool(donnee) and donnee in attendues,
        reponse_donnee=reponse,
        bonne_reponse=bonne_reponse(carte),
        explication=carte.explication,
    )


def _normaliser(texte: str) -> str:
    """Ramène une réponse à sa forme comparable."""
    sans_accent = "".join(
        caractere
        for caractere in unicodedata.normalize("NFD", texte)
        if not unicodedata.combining(caractere)
    )
    return " ".join(sans_accent.lower().split()).strip(" .,;:!?\"'`")
