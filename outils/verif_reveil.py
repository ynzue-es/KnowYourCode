#!/usr/bin/env python3
"""Vérification du réveil : le hook posé, retiré, et ce qu'il ne touche pas.

Ce module écrit dans `~/.claude/settings.json`, qui contient les réglages
personnels de quelqu'un et les hooks d'autres outils que le nôtre. C'est la
seule partie du projet qui modifie un fichier dont elle n'est pas propriétaire,
et c'est pour ça qu'elle se vérifie ligne à ligne — sur des copies, jamais sur
le fichier réel.

    python outils/verif_reveil.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Avant tout import du paquet : rien ne doit toucher au dossier de données réel.
DOSSIER_TEST = tempfile.mkdtemp(prefix="knowyourcode-reveil-")
os.environ["KNOWYOURCODE_DOSSIER"] = DOSSIER_TEST

from connais_ton_code import reveil  # noqa: E402

_constats: list[tuple[bool, str]] = []


def _verifier(condition: bool, description: str) -> None:
    _constats.append((bool(condition), description))


def _reglages(contenu: dict) -> Path:
    """Écrit un faux `settings.json` et rend son chemin."""
    chemin = Path(tempfile.mkdtemp(prefix="knowyourcode-reglages-")) / "settings.json"
    chemin.write_text(json.dumps(contenu, ensure_ascii=False), encoding="utf-8")
    return chemin


# Un hook qui n'est pas le nôtre, et qui doit survivre à tout ce qu'on fait.
_HOOK_ETRANGER = {
    "hooks": [{"type": "command", "command": "echo bonjour"}],
}


def verifier_la_pose() -> None:
    chemin = _reglages({"theme": "auto"})

    _verifier(not reveil.est_installe(chemin), "au départ, aucun réveil n'est posé")
    _verifier(reveil.installer(chemin), "la pose réussit sur des réglages lisibles")
    _verifier(reveil.est_installe(chemin), "le réveil est reconnu une fois posé")

    ecrit = json.loads(chemin.read_text(encoding="utf-8"))
    _verifier(ecrit.get("theme") == "auto", "les réglages personnels sont conservés")
    _verifier(
        reveil.EVENEMENT in ecrit.get("hooks", {}),
        "le hook est posé sur l'événement d'envoi de prompt",
    )

    # Actionner l'interrupteur deux fois ne doit pas empiler deux hooks : la
    # commande partirait alors en double à chaque prompt.
    reveil.installer(chemin)
    ecrit = json.loads(chemin.read_text(encoding="utf-8"))
    _verifier(
        len(ecrit["hooks"][reveil.EVENEMENT]) == 1,
        "poser deux fois ne pose qu'un seul hook",
    )


def verifier_le_retrait() -> None:
    chemin = _reglages({"theme": "auto"})
    reveil.installer(chemin)

    _verifier(reveil.retirer(chemin), "le retrait réussit")
    _verifier(not reveil.est_installe(chemin), "le réveil n'est plus reconnu")

    ecrit = json.loads(chemin.read_text(encoding="utf-8"))
    _verifier(ecrit.get("theme") == "auto", "le retrait conserve les réglages personnels")
    _verifier(
        "hooks" not in ecrit,
        "le retrait ne laisse pas de tableau vide derrière lui",
    )


def verifier_les_hooks_des_autres() -> None:
    """Le contrôle qui compte : ne jamais emporter le hook de quelqu'un d'autre."""
    chemin = _reglages({"hooks": {reveil.EVENEMENT: [_HOOK_ETRANGER]}})

    reveil.installer(chemin)
    ecrit = json.loads(chemin.read_text(encoding="utf-8"))
    entrees = ecrit["hooks"][reveil.EVENEMENT]
    _verifier(len(entrees) == 2, "notre hook s'ajoute à celui qui était déjà là")
    _verifier(_HOOK_ETRANGER in entrees, "le hook étranger est intact après la pose")

    reveil.retirer(chemin)
    ecrit = json.loads(chemin.read_text(encoding="utf-8"))
    _verifier(
        ecrit["hooks"][reveil.EVENEMENT] == [_HOOK_ETRANGER],
        "le retrait n'emporte que le nôtre",
    )

    # Un hook posé sur un autre événement n'a aucune raison d'être touché.
    chemin = _reglages({"hooks": {"PreToolUse": [_HOOK_ETRANGER]}})
    reveil.installer(chemin)
    reveil.retirer(chemin)
    ecrit = json.loads(chemin.read_text(encoding="utf-8"))
    _verifier(
        ecrit.get("hooks", {}).get("PreToolUse") == [_HOOK_ETRANGER],
        "un hook posé sur un autre événement n'est pas touché",
    )


def verifier_les_refus() -> None:
    absent = Path(DOSSIER_TEST) / "il-n-y-a-rien" / "settings.json"
    _verifier(
        not reveil.installer(absent),
        "poser sur un fichier de réglages absent échoue sans lever",
    )
    _verifier(
        not reveil.est_installe(absent),
        "un fichier absent n'est pas pris pour un réveil posé",
    )

    illisible = Path(tempfile.mkdtemp()) / "settings.json"
    illisible.write_text("{ceci n'est pas du JSON", encoding="utf-8")
    _verifier(
        not reveil.installer(illisible),
        "des réglages illisibles ne sont pas écrasés",
    )
    _verifier(
        illisible.read_text(encoding="utf-8") == "{ceci n'est pas du JSON",
        "le fichier illisible est laissé exactement tel quel",
    )


def verifier_la_commande() -> None:
    """La commande du hook doit vraiment toucher le fichier, et sortir à zéro.

    Elle s'exécute sur le chemin critique de l'envoi d'un prompt : si elle
    échoue, Claude Code encombre la session de messages pour un service qui
    n'est qu'un confort.
    """
    fichier = reveil.chemin_reveil()
    if fichier.exists():
        fichier.unlink()

    resultat = subprocess.run(
        reveil._commande(), shell=True, capture_output=True, text=True
    )
    _verifier(resultat.returncode == 0, "la commande du hook sort avec un code nul")
    _verifier(fichier.exists(), "la commande du hook touche bien le fichier de réveil")

    avant = fichier.stat().st_mtime_ns
    os.utime(fichier, ns=(avant - 5_000_000_000, avant - 5_000_000_000))
    subprocess.run(reveil._commande(), shell=True, capture_output=True)
    _verifier(
        fichier.stat().st_mtime_ns > avant - 5_000_000_000,
        "un second appel rafraîchit la date, ce que l'application guette",
    )


def main() -> int:
    verifier_la_pose()
    verifier_le_retrait()
    verifier_les_hooks_des_autres()
    verifier_les_refus()
    verifier_la_commande()

    for ok, description in _constats:
        print(f"{'  ok  ' if ok else 'ÉCHEC '} {description}")

    echecs = [description for ok, description in _constats if not ok]
    print()
    print(f"{len(_constats) - len(echecs)}/{len(_constats)} vérifications passées")
    return 1 if echecs else 0


if __name__ == "__main__":
    raise SystemExit(main())
