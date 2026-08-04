"""Le rappel glissé dans le compteur d'attente de Claude Code.

Une notification système suppose une autorisation, disparaît en trois secondes
et macOS refuse parfois de la demander. Le compteur d'attente, lui, est déjà
sous les yeux à chaque tour : c'est le meilleur endroit pour rappeler qu'on
peut réviser au lieu de regarder tourner.

Claude Code lit ces phrases dans la clé `spinnerVerbs` de son fichier de
réglages. Le mode « replace » remplace sa liste d'origine ; « append » aurait
noyé nos quatorze phrases dans une centaine de verbes anglais.
"""

from __future__ import annotations

import json
from pathlib import Path

from .stockage import dossier_donnees

REGLAGES_CLAUDE = Path.home() / ".claude" / "settings.json"
CLE = "spinnerVerbs"

NOM_FICHIER_PHRASES = "phrases.json"

# Claude Code coupe au-delà : mieux vaut une phrase entière qu'une phrase
# tronquée au milieu d'un mot. La mesure porte sur la phrase habillée, seule
# forme que le terminal affichera.
LONGUEUR_MAXIMALE = 60

BALISE = "kyc"

# Les phrases sont écrites nues : l'habillage est posé au dernier moment, ce
# qui permet de le changer sans réécrire les quatorze.
PHRASES_PAR_DEFAUT = (
    "Révise pendant que je travaille",
    "Connais ton code, pas seulement ton client",
    "Explique une fonction en attendant",
    "Sais-tu encore ce que fait ce fichier",
    "Contrôle avec KnowYourCode",
    "Relis ce que tu ne relis plus",
    "Une question t'attend en haut à droite",
    "Reprends la main sur ton code",
    "Profite de l'attente pour réviser",
    "Vérifie que tu suis toujours",
    "Ton code, tu le connais vraiment",
    "Explique ta dernière fonction en deux minutes",
    "Ouvre KnowYourCode et prends une question",
    "Garde la maîtrise de ce que j'écris",
)


def habiller(texte: str) -> str:
    """Entoure une phrase de la balise du projet."""
    return f"<{BALISE}>{texte}</{BALISE}>"


def chemin_phrases() -> Path:
    """Le fichier où poser ses propres phrases, hors du dépôt."""
    return dossier_donnees() / NOM_FICHIER_PHRASES


def phrases() -> list[str]:
    """Les phrases à installer : celles de l'utilisateur, sinon les nôtres.

    Les siennes vivent dans son dossier de données, pas dans le dépôt : on
    change ses phrases sans toucher au code ni craindre de les perdre à la
    prochaine mise à jour. Elles s'écrivent nues, la balise est ajoutée ici.
    """
    fichier = chemin_phrases()
    try:
        contenu = json.loads(fichier.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        contenu = None

    brutes = contenu if isinstance(contenu, list) else list(PHRASES_PAR_DEFAUT)
    retenues = [
        habiller(texte.strip())
        for texte in brutes
        if isinstance(texte, str) and texte.strip()
        and len(habiller(texte.strip())) < LONGUEUR_MAXIMALE
    ]
    return retenues or [habiller(texte) for texte in PHRASES_PAR_DEFAUT]


def _lire_reglages(chemin: Path) -> dict | None:
    try:
        contenu = json.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return contenu if isinstance(contenu, dict) else None


def est_installe(chemin: Path = REGLAGES_CLAUDE) -> bool:
    """Dit si le rappel est en place dans les réglages de Claude Code."""
    reglages = _lire_reglages(chemin)
    if reglages is None:
        return False
    bloc = reglages.get(CLE)
    return isinstance(bloc, dict) and bool(bloc.get("verbs"))


def installer(chemin: Path = REGLAGES_CLAUDE) -> bool:
    """Pose le rappel. Rend faux si les réglages sont illisibles.

    Le fichier est relu puis réécrit en entier : il contient les réglages
    personnels de quelqu'un, il n'est pas question d'en perdre un seul.
    """
    reglages = _lire_reglages(chemin)
    if reglages is None:
        return False

    reglages[CLE] = {"mode": "replace", "verbs": phrases()}
    return _ecrire(chemin, reglages)


def retirer(chemin: Path = REGLAGES_CLAUDE) -> bool:
    """Retire le rappel et rend à Claude Code ses propres verbes."""
    reglages = _lire_reglages(chemin)
    if reglages is None:
        return False

    reglages.pop(CLE, None)
    return _ecrire(chemin, reglages)


def _ecrire(chemin: Path, reglages: dict) -> bool:
    try:
        chemin.write_text(
            json.dumps(reglages, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError:
        return False
    return True
