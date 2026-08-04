"""Détection d'une session Claude Code en train de travailler."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Protocol, runtime_checkable

DOSSIER_TRANSCRIPTS = Path.home() / ".claude" / "projects"

# En dessous, une session qui écrit dans son transcript est considérée comme
# active. Claude Code écrit en continu pendant qu'il travaille, donc quelques
# secondes suffisent à distinguer « en train de réfléchir » de « terminé ».
SECONDES_ACTIVITE = 20.0

# Deux sollicitations rapprochées agacent plus qu'elles n'entraînent : une
# session bavarde produit une rafale par réponse. Cinq minutes laissent passer
# les allers-retours d'une même tâche sans se taire toute la matinée. Le
# réglage se change dans reglages.json, parce que la bonne valeur dépend de la
# façon de travailler et qu'aucune estimation ne la trouvera à la place de
# l'utilisateur.
INTERVALLE_MINIMUM_S = 300.0


@runtime_checkable
class Detecteur(Protocol):
    """Contrat : dire si le moment est venu de poser une question.

    L'orchestrateur interroge le détecteur à intervalle régulier depuis le fil
    principal. `session_active` doit donc rendre la main tout de suite : pas
    d'appel réseau, pas de parcours de disque coûteux.

    La méthode se lit comme un front montant, pas comme un état : elle rend
    vrai une seule fois par épisode d'activité. Sinon la fenêtre reposerait
    une question à chaque tour d'horloge tant que la session travaille.

    `projet_actif` dit sur quel dossier porter les questions. Rendre `None`
    est valable et veut dire « je ne sais pas » : le sélecteur se rabattra
    alors sur ce qu'il peut.
    """

    def session_active(self) -> bool:
        """Vrai si une session vient de passer en activité."""
        ...

    def projet_actif(self) -> Path | None:
        """Le dossier du projet sur lequel une session travaille."""
        ...


def _transcript_le_plus_recent(dossier: Path) -> tuple[Path, float] | None:
    """Rend le transcript modifié en dernier, avec sa date.

    Le parcours est volontairement plat : les transcripts vivent tous à un
    niveau de profondeur, et un `rglob` sur le dossier personnel coûterait
    trop cher pour un appel qui a lieu chaque seconde.
    """
    dernier: tuple[Path, float] | None = None
    try:
        projets = list(dossier.iterdir())
    except OSError:
        return None

    for projet in projets:
        try:
            fichiers = projet.glob("*.jsonl")
            for fichier in fichiers:
                date = fichier.stat().st_mtime
                if dernier is None or date > dernier[1]:
                    dernier = (fichier, date)
        except OSError:
            continue
    return dernier


def _dossier_du_transcript(transcript: Path, lignes_max: int = 400) -> Path | None:
    """Retrouve le dossier de travail à partir du contenu du transcript.

    Le nom du dossier parent encode le chemin en remplaçant les barres par des
    tirets, ce qui n'est pas réversible dès qu'un nom de dossier contient
    lui-même un tiret. Le champ `cwd`, présent sur une partie des lignes, lui,
    est exact.
    """
    try:
        with transcript.open(encoding="utf-8") as fichier:
            for numero, ligne in enumerate(fichier):
                if numero >= lignes_max:
                    break
                try:
                    donnees = json.loads(ligne)
                except json.JSONDecodeError:
                    continue
                chemin = donnees.get("cwd")
                if isinstance(chemin, str) and chemin:
                    return Path(chemin)
    except OSError:
        return None
    return None


class DetecteurClaudeCode:
    """Surveille les transcripts JSONL sous ~/.claude/projects/."""

    def __init__(
        self,
        dossier: Path = DOSSIER_TRANSCRIPTS,
        secondes_activite: float = SECONDES_ACTIVITE,
        intervalle_minimum: float = INTERVALLE_MINIMUM_S,
    ) -> None:
        self._dossier = dossier
        self._secondes_activite = secondes_activite
        self._intervalle_minimum = intervalle_minimum

        self._etait_active = False
        self._derniere_invitation = 0.0
        self._projet: Path | None = None
        self._demande_forcee = False

    def disponible(self) -> bool:
        """Dit si la surveillance a quelque chose à surveiller."""
        return self._dossier.is_dir()

    def demander_question(self) -> None:
        """Force une détection au prochain tour, pour l'entrée de menu."""
        self._demande_forcee = True

    def session_active(self) -> bool:
        dernier = _transcript_le_plus_recent(self._dossier)
        if dernier is not None:
            transcript, date = dernier
            maintenant = time.time()
            active = maintenant - date < self._secondes_activite

            # Le front montant seul ne suffit pas : une session qui répond
            # dix fois dans l'heure produit dix fronts.
            nouvelle = active and not self._etait_active
            assez_espace = (
                maintenant - self._derniere_invitation >= self._intervalle_minimum
            )
            self._etait_active = active

            if self._demande_forcee or (nouvelle and assez_espace):
                self._demande_forcee = False
                self._derniere_invitation = maintenant
                self._projet = _dossier_du_transcript(transcript)
                return True
        elif self._demande_forcee:
            self._demande_forcee = False
            return True

        return False

    def projet_actif(self) -> Path | None:
        if self._projet is not None:
            return self._projet
        dernier = _transcript_le_plus_recent(self._dossier)
        if dernier is None:
            return None
        return _dossier_du_transcript(dernier[0])


class DetecteurFactice:
    """Détecteur piloté à la main, sans lecture de disque.

    Sert aux vérifications, et de repli quand ~/.claude/projects/ n'existe
    pas encore sur la machine.
    """

    def __init__(self, projet: Path | None = None) -> None:
        self._demande_en_attente = False
        self._projet = projet

    def demander_question(self) -> None:
        """Arme une détection, consommée au prochain appel de `session_active`."""
        self._demande_en_attente = True

    def session_active(self) -> bool:
        demande = self._demande_en_attente
        self._demande_en_attente = False
        return demande

    def projet_actif(self) -> Path | None:
        return self._projet
