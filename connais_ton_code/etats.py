"""Le cycle d'états de la fenêtre.

Un seul état est actif à la fois et toutes les transitions passent par
l'orchestrateur : l'interface ne décide jamais seule de changer d'état, elle
signale une intention.
"""

from __future__ import annotations

from enum import Enum, auto


class Etat(Enum):
    """Les quatre états du cycle."""

    MASQUEE = auto()
    """État par défaut : rien à l'écran, on attend une détection."""

    QUESTION = auto()
    """Un extrait est affiché, la saisie est ouverte."""

    EVALUATION = auto()
    """La réponse est partie à l'évaluateur, l'interface reste utilisable."""

    RETOUR = auto()
    """Le verdict est affiché, on attend le passage à la suite."""


# Une transition non listée ici est un bug de l'orchestrateur, pas un cas à
# gérer silencieusement : la table sert d'assertion.
TRANSITIONS_AUTORISEES: dict[Etat, frozenset[Etat]] = {
    Etat.MASQUEE: frozenset({Etat.QUESTION}),
    Etat.QUESTION: frozenset({Etat.EVALUATION, Etat.MASQUEE}),
    Etat.EVALUATION: frozenset({Etat.RETOUR, Etat.MASQUEE}),
    Etat.RETOUR: frozenset({Etat.MASQUEE, Etat.QUESTION}),
}


def transition_valide(depuis: Etat, vers: Etat) -> bool:
    """Dit si le passage d'un état à l'autre fait partie du cycle."""
    return vers in TRANSITIONS_AUTORISEES[depuis]
