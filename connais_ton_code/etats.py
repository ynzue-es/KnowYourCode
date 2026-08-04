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
    """Le panneau est ouvert mais aucune question n'est posée."""

    QUESTION = auto()
    """Un extrait est affiché, la saisie est ouverte."""

    EVALUATION = auto()
    """La réponse est partie à l'évaluateur, le panneau reste utilisable."""

    RETOUR = auto()
    """Le verdict est affiché, on attend le passage à la suite."""


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
    Etat.QUESTION: frozenset({Etat.EVALUATION, Etat.REPOS, Etat.FERME}),
    Etat.EVALUATION: frozenset({Etat.RETOUR, Etat.FERME}),
    Etat.RETOUR: frozenset({Etat.REPOS, Etat.QUESTION, Etat.FERME}),
}


def transition_valide(depuis: Etat, vers: Etat) -> bool:
    """Dit si le passage d'un état à l'autre fait partie du cycle."""
    return vers in TRANSITIONS_AUTORISEES[depuis]
