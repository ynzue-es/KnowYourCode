"""Le cycle d'états du panneau.

Un seul état est actif à la fois et toutes les transitions passent par
l'orchestrateur : l'interface ne décide jamais seule de changer d'état, elle
signale une intention.
"""

from __future__ import annotations

from enum import Enum, auto


class Etat(Enum):
    """Les états du cycle."""

    FERME = auto()
    """État par défaut : seule l'icône de la barre de menus est visible."""

    REPOS = auto()
    """Le panneau est ouvert mais aucune série n'est en cours."""

    QUESTION = auto()
    """Une carte est posée sur l'extrait, on attend le geste de réponse."""

    RETOUR = auto()
    """La carte est corrigée : juste ou faux, et l'explication."""

    BILAN = auto()
    """La série est finie, son compte est affiché."""


# L'ancien état d'évaluation a disparu avec l'appel réseau : la correction est
# désormais locale, la carte passe de QUESTION à RETOUR dans le même geste. Un
# état qui ne dure jamais assez longtemps pour être vu n'a pas à exister.
#
# Une transition non listée ici est un bug de l'orchestrateur, pas un cas à
# gérer silencieusement : la table sert d'assertion. Tous les états mènent à
# FERME, parce que fermer le panneau doit toujours être possible.
#
# La progression et les réglages ne figurent pas ici : ils vivent dans une
# fenêtre séparée, qui s'ouvre et se ferme sans rien changer au cycle de
# l'exercice.
TRANSITIONS_AUTORISEES: dict[Etat, frozenset[Etat]] = {
    Etat.FERME: frozenset({Etat.REPOS, Etat.QUESTION}),
    Etat.REPOS: frozenset({Etat.QUESTION, Etat.FERME}),
    # Abandonner en cours de série ramène au repos ; on ne saute jamais
    # directement au bilan, qui ne compte que des cartes réellement vues.
    Etat.QUESTION: frozenset({Etat.RETOUR, Etat.REPOS, Etat.FERME}),
    # Après l'explication, il reste une carte ou il n'en reste plus.
    Etat.RETOUR: frozenset({Etat.QUESTION, Etat.BILAN, Etat.FERME}),
    Etat.BILAN: frozenset({Etat.QUESTION, Etat.REPOS, Etat.FERME}),
}


def transition_valide(depuis: Etat, vers: Etat) -> bool:
    """Dit si le passage d'un état à l'autre fait partie du cycle."""
    return vers in TRANSITIONS_AUTORISEES[depuis]
