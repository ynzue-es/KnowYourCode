"""Évaluation de la réponse de l'utilisateur.

BOUCHON : seule la version factice existe pour l'instant.
"""

from __future__ import annotations

import time
from typing import Protocol, runtime_checkable

from .modeles import Evaluation, Extrait


@runtime_checkable
class Evaluateur(Protocol):
    """Contrat : comparer une explication au code qu'elle prétend décrire.

    `evaluer` est appelé dans un fil secondaire et a le droit d'être lent ou
    de faire du réseau, mais il ne doit toucher à aucun objet Qt. Il doit
    toujours rendre une `Evaluation` : une panne réseau se traduit par un
    verdict expliquant l'échec, pas par une exception qui laisserait
    l'interface bloquée sur l'indicateur d'attente.

    Implémentation prévue : un appel à l'API Anthropic en Haiku, avec le code
    et la réponse dans le message, et une sortie structurée pour obtenir le
    verdict, la note et la liste des points oubliés.
    """

    def evaluer(self, extrait: Extrait, reponse: str) -> Evaluation:
        """Rend le verdict sur `reponse` au regard de `extrait`."""
        ...


class EvaluateurFactice:
    """Retour en dur, après une seconde, pour éprouver le cycle d'états.

    Le délai est volontaire : il rend visible l'état d'évaluation et permet de
    vérifier que la fenêtre reste utilisable pendant l'attente.
    """

    def __init__(self, delai_secondes: float = 1.0) -> None:
        self._delai_secondes = delai_secondes

    def evaluer(self, extrait: Extrait, reponse: str) -> Evaluation:
        time.sleep(self._delai_secondes)

        if not reponse.strip():
            return Evaluation(
                verdict="Réponse vide : impossible de juger quoi que ce soit.",
                score=0,
                points_oublies=["Tout le raisonnement de la fonction."],
            )

        return Evaluation(
            verdict=(
                f"Évaluation factice de {len(reponse.split())} mots sur "
                f"{extrait.nom_fonction}. Le vrai verdict viendra de Haiku."
            ),
            score=72,
            points_oublies=[
                "Le cas limite quand l'entrée est vide.",
                "La raison du tri avant le regroupement.",
                "Ce que la fonction fait en cas d'erreur réseau.",
            ],
        )
