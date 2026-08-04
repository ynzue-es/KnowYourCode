"""Détection d'une session Claude Code en train de travailler.

BOUCHON : seule la version factice existe pour l'instant.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Detecteur(Protocol):
    """Contrat : dire si le moment est venu de poser une question.

    L'orchestrateur interroge le détecteur à intervalle régulier depuis le fil
    principal. `session_active` doit donc rendre la main tout de suite : pas
    d'appel réseau, pas de parcours de disque coûteux. Une implémentation qui
    aurait besoin de travail long doit le faire dans son coin et se contenter
    de rendre ici un résultat déjà calculé.

    La méthode se lit comme un front montant, pas comme un état : elle rend
    vrai une seule fois par épisode d'activité. Sinon la fenêtre repose une
    question à chaque tour d'horloge tant que la session travaille.

    Implémentation prévue : surveiller les dates de modification des
    transcripts JSONL sous ~/.claude/projects/. Un fichier modifié dans les
    dernières secondes signale une session active ; on attend ensuite un
    retour au calme avant de réarmer la détection.
    """

    def session_active(self) -> bool:
        """Vrai si une session vient de passer en activité."""
        ...


class DetecteurFactice:
    """Détecteur piloté à la main, en attendant la vraie surveillance.

    La demande est posée par la pastille de test depuis le fil principal, puis
    consommée au tour d'horloge suivant : un clic donne exactement une
    question.
    """

    def __init__(self) -> None:
        self._demande_en_attente = False

    def demander_question(self) -> None:
        """Arme une question, consommée au prochain appel de `session_active`."""
        self._demande_en_attente = True

    def session_active(self) -> bool:
        demande = self._demande_en_attente
        self._demande_en_attente = False
        return demande
