"""Ouvrir le panneau au moment où Claude Code se met au travail.

La règle de la maison est que rien ne s'ouvre tout seul. Ce module n'y
contrevient pas : ce qu'elle interdit, c'est d'interrompre quelqu'un qui
travaille. Or l'instant où l'on envoie un prompt est précisément celui où l'on
*cesse* de travailler, pour attendre. C'est le moment que le produit vise
depuis le début.

Le réglage est éteint par défaut, et il touche `~/.claude/settings.json`, qui
sert à toutes les sessions de la machine : il ne se pose que sur décision
explicite, par l'interrupteur de la grande fenêtre.

Le hook ne parle pas à l'application — il n'a aucun moyen de le faire. Il se
contente de toucher un fichier, que l'application surveille. Pas de port, pas
d'autorisation à accorder, rien qui reste ouvert entre deux lancements.
"""

from __future__ import annotations

import json
from pathlib import Path

from .stockage import dossier_donnees

REGLAGES_CLAUDE = Path.home() / ".claude" / "settings.json"

# L'événement émis quand un prompt part. Le nom est celui que reconnaît Claude
# Code ; s'il venait à changer, le hook cesserait simplement de se déclencher,
# sans rien casser d'autre.
EVENEMENT = "UserPromptSubmit"

NOM_FICHIER = "reveil"

# La marque qui permet de reconnaître notre hook parmi ceux de l'utilisateur.
# Sans elle, retirer le réglage retirerait aussi les hooks des autres.
MARQUE = "knowyourcode-reveil"


def chemin_reveil() -> Path:
    """Le fichier que le hook touche et que l'application surveille."""
    return dossier_donnees() / NOM_FICHIER


def _commande() -> str:
    """La ligne que Claude Code exécutera à chaque prompt.

    Elle doit être brève et sans effet de bord : elle s'exécute sur le chemin
    critique de l'envoi, et tout ce qu'elle coûte, c'est l'utilisateur qui
    l'attend. Le `:` final garantit un code de sortie nul même si le dossier
    est en lecture seule — un hook qui échoue encombrerait la session de
    messages pour un service qui n'est qu'un confort.
    """
    fichier = chemin_reveil()
    return (
        f"mkdir -p {fichier.parent} && touch {fichier} 2>/dev/null; "
        f": {MARQUE}"
    )


def _lire_reglages(chemin: Path) -> dict | None:
    """Lit les réglages de Claude Code, ou rend `None` s'ils sont illisibles.

    On ne crée pas le fichier : s'il n'existe pas, c'est que Claude Code n'a
    jamais tourné sur cette machine, et poser un hook n'aurait aucun sens.
    """
    try:
        contenu = json.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    return contenu if isinstance(contenu, dict) else None


def _entrees(reglages: dict) -> list:
    """Les entrées déjà posées sur notre événement, quelles qu'elles soient."""
    hooks = reglages.get("hooks")
    if not isinstance(hooks, dict):
        return []
    entrees = hooks.get(EVENEMENT)
    return entrees if isinstance(entrees, list) else []


def _est_le_notre(entree: object) -> bool:
    return MARQUE in json.dumps(entree, ensure_ascii=False)


def est_installe(chemin: Path = REGLAGES_CLAUDE) -> bool:
    """Dit si le réveil est en place dans les réglages de Claude Code."""
    reglages = _lire_reglages(chemin)
    if reglages is None:
        return False
    return any(_est_le_notre(entree) for entree in _entrees(reglages))


def installer(chemin: Path = REGLAGES_CLAUDE) -> bool:
    """Pose le hook. Rend faux si les réglages sont illisibles ou absents.

    Le fichier est relu puis réécrit en entier : il contient les réglages
    personnels de quelqu'un, et d'autres hooks que les nôtres. On n'ajoute
    qu'une entrée, et on retire d'abord la précédente pour ne pas en empiler
    une de plus à chaque fois que l'interrupteur est actionné.
    """
    reglages = _lire_reglages(chemin)
    if reglages is None:
        return False

    hooks = reglages.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        return False

    gardees = [e for e in _entrees(reglages) if not _est_le_notre(e)]
    gardees.append(
        {"hooks": [{"type": "command", "command": _commande()}]}
    )
    hooks[EVENEMENT] = gardees
    return _ecrire(chemin, reglages)


def retirer(chemin: Path = REGLAGES_CLAUDE) -> bool:
    """Retire notre hook, et lui seul.

    Les entrées des autres restent en place ; la clé de l'événement disparaît
    seulement si nous étions les derniers à l'occuper, pour ne pas laisser un
    tableau vide dans un fichier qu'on relit à la main.
    """
    reglages = _lire_reglages(chemin)
    if reglages is None:
        return False

    hooks = reglages.get("hooks")
    if not isinstance(hooks, dict):
        return True

    gardees = [e for e in _entrees(reglages) if not _est_le_notre(e)]
    if gardees:
        hooks[EVENEMENT] = gardees
    else:
        hooks.pop(EVENEMENT, None)
    if not hooks:
        reglages.pop("hooks", None)
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
