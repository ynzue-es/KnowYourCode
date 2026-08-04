"""Détection d'une session Claude Code en train de travailler."""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Protocol, runtime_checkable

DOSSIER_TRANSCRIPTS = Path.home() / ".claude" / "projects"

# Aucun délai par défaut : le moment juste est celui où l'utilisateur envoie un
# prompt, et une question déjà en attente empêche de toute façon la suivante.
# Le réglage existe dans reglages.json pour qui veut espacer davantage.
INTERVALLE_MINIMUM_S = 0.0

# Claude Code injecte dans le transcript des lignes qui ressemblent à des
# messages de l'utilisateur sans en être : retours de commandes, rappels du
# système, comptes rendus de tâches. Elles commencent toutes par une balise.
_DEBUT_DE_BALISE = re.compile(r"^<[a-z][a-z0-9-]*>")


@runtime_checkable
class Detecteur(Protocol):
    """Contrat : dire si le moment est venu de poser une question.

    L'orchestrateur interroge le détecteur à intervalle régulier depuis le fil
    principal. `session_active` doit donc rendre la main tout de suite : pas
    d'appel réseau, pas de parcours de disque coûteux.

    La méthode se lit comme un évènement, pas comme un état : elle rend vrai
    une seule fois par déclenchement. Sinon la question se reposerait à chaque
    tour d'horloge tant que la session travaille.

    `projet_actif` dit sur quel dossier porter les questions. Rendre `None`
    est valable et veut dire « je ne sais pas » : le sélecteur se rabattra
    alors sur ce qu'il peut.
    """

    def session_active(self) -> bool:
        """Vrai si une session vient de se mettre au travail."""
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


def _est_un_prompt(donnees: dict) -> bool:
    """Dit si une ligne du transcript est un prompt tapé par l'utilisateur.

    Les résultats d'outils sont enregistrés comme des messages de
    l'utilisateur, alors que c'est Claude qui se répond à lui-même : sur ce
    transcript, 436 lignes contre 33 vrais prompts. Seul le contenu textuel
    compte. Restent les lignes injectées par Claude Code, retours de commandes
    et comptes rendus de tâches, qui commencent toutes par une balise.
    """
    if donnees.get("type") != "user":
        return False

    message = donnees.get("message")
    if not isinstance(message, dict):
        return False

    contenu = message.get("content")
    if isinstance(contenu, str):
        textes = [contenu]
    elif isinstance(contenu, list):
        textes = [
            bloc.get("text", "")
            for bloc in contenu
            if isinstance(bloc, dict) and bloc.get("type") == "text"
        ]
    else:
        return False

    return any(
        texte.strip() and not _DEBUT_DE_BALISE.match(texte.strip())
        for texte in textes
    )


class DetecteurClaudeCode:
    """Guette le moment où une session Claude Code se met au travail.

    Ce moment est celui où l'utilisateur envoie un prompt, pas celui où le
    fichier bouge : Claude Code écrit dans son transcript pendant tout son
    tour, si bien qu'une simple date de modification ne distingue pas le début
    du travail de son déroulement. On lit donc ce qui s'est ajouté au
    transcript depuis le dernier passage, et on y cherche un prompt.
    """

    def __init__(
        self,
        dossier: Path = DOSSIER_TRANSCRIPTS,
        intervalle_minimum: float = INTERVALLE_MINIMUM_S,
    ) -> None:
        self._dossier = dossier
        self._intervalle_minimum = intervalle_minimum

        self._transcript: Path | None = None
        self._position = 0
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
        prompt = self._nouveau_prompt()
        maintenant = time.time()
        assez_espace = (
            maintenant - self._derniere_invitation >= self._intervalle_minimum
        )

        if not self._demande_forcee and not (prompt and assez_espace):
            return False

        self._demande_forcee = False
        self._derniere_invitation = maintenant
        if self._transcript is not None:
            self._projet = _dossier_du_transcript(self._transcript)
        return True

    def _nouveau_prompt(self) -> bool:
        """Lit ce qui s'est ajouté au transcript et y cherche un prompt."""
        dernier = _transcript_le_plus_recent(self._dossier)
        if dernier is None:
            return False

        transcript = dernier[0]
        try:
            taille = transcript.stat().st_size
        except OSError:
            return False

        # Un transcript qu'on découvre, c'est soit le premier tour, soit un
        # changement de session : on se cale à la fin plutôt que de rejouer un
        # historique entier et de déclencher sur des prompts d'hier.
        if transcript != self._transcript:
            self._transcript = transcript
            self._position = taille
            return False

        if taille < self._position:
            self._position = 0
        if taille == self._position:
            return False

        try:
            with transcript.open("rb") as fichier:
                fichier.seek(self._position)
                ajout = fichier.read()
        except OSError:
            return False
        self._position = taille

        for ligne in ajout.decode("utf-8", errors="replace").splitlines():
            try:
                donnees = json.loads(ligne)
            except json.JSONDecodeError:
                continue
            if isinstance(donnees, dict) and _est_un_prompt(donnees):
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
