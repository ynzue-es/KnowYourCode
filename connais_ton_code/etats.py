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

    TABLEAU = auto()
    """Le tableau de bord des statistiques est affiché."""


# Une transition non listée ici est un bug de l'orchestrateur, pas un cas à
# gérer silencieusement : la table sert d'assertion. Tous les états mènent à
# FERME, parce que fermer le panneau doit toujours être possible.
#
# QUESTION et EVALUATION ne mènent pas à TABLEAU : la saisie d'une réponse ou
# une évaluation en cours sont un travail non enregistré, et y couper court
# pour aller voir des statistiques le ferait perdre. Depuis FERME, REPOS ou
# RETOUR, en revanche, rien n'est en train de s'écrire, donc rien à perdre.
TRANSITIONS_AUTORISEES: dict[Etat, frozenset[Etat]] = {
    Etat.FERME: frozenset({Etat.REPOS, Etat.QUESTION, Etat.TABLEAU}),
    Etat.REPOS: frozenset({Etat.QUESTION, Etat.FERME, Etat.TABLEAU}),
    Etat.QUESTION: frozenset({Etat.EVALUATION, Etat.REPOS, Etat.FERME}),
    Etat.EVALUATION: frozenset({Etat.RETOUR, Etat.FERME}),
    Etat.RETOUR: frozenset({Etat.REPOS, Etat.QUESTION, Etat.FERME, Etat.TABLEAU}),
    # Depuis le tableau, on retrouve le cycle normal des questions : poser_question
    # choisit un extrait s'il y en a un (→ QUESTION) ou retombe au repos sinon
    # (→ REPOS), donc les deux issues doivent être valides ici.
    Etat.TABLEAU: frozenset({Etat.QUESTION, Etat.REPOS, Etat.FERME}),
}


def transition_valide(depuis: Etat, vers: Etat) -> bool:
    """Dit si le passage d'un état à l'autre fait partie du cycle."""
    return vers in TRANSITIONS_AUTORISEES[depuis]
