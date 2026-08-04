#!/usr/bin/env python3
"""Fabrique `KnowYourCode.app`, à lancer d'un double-clic.

Sans paquet, macOS ne connaît l'application que par l'exécutable qui tourne :
les notifications s'annoncent alors comme venant de « Python », avec l'icône
de Python. Le paquet lui donne un nom, une icône et une identité.

Le tour de main tient en deux fichiers. L'interpréteur du venv est copié dans
le paquet et accompagné de son `pyvenv.cfg` : Python retrouve ainsi son
environnement, et macOS voit un exécutable qui vit à l'intérieur du paquet,
donc lui attribue son identité. Un script de lancement se contente de
l'appeler avec le bon module.

Le chemin du dépôt est inscrit dans le script au moment de la fabrication : le
paquet n'est pas déplaçable d'une machine à l'autre, mais il se refait en une
commande.

    python outils/creer_app.py
"""

from __future__ import annotations

import os
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from PyQt6.QtWidgets import QApplication  # noqa: E402

from connais_ton_code.logo import pixmap_logo  # noqa: E402

NOM = "KnowYourCode"
IDENTIFIANT = "io.github.ynzue-es.knowyourcode"
VERSION = "0.1.0"

# Les tailles attendues par `iconutil` pour un jeu d'icônes complet.
TAILLES_ICONE = (16, 32, 128, 256, 512)


def _venv() -> Path:
    venv = RACINE / ".venv"
    if not (venv / "bin" / "python3").exists():
        raise SystemExit(
            "Aucun environnement virtuel dans .venv : lancez d'abord "
            "python3 -m venv .venv && pip install -r requirements.txt"
        )
    return venv


def ecrire_icone(destination: Path) -> None:
    """Assemble le .icns à partir du logo dessiné dans le code."""
    jeu = destination.parent / f"{NOM}.iconset"
    if jeu.exists():
        shutil.rmtree(jeu)
    jeu.mkdir(parents=True)

    for taille in TAILLES_ICONE:
        pixmap_logo(taille).save(str(jeu / f"icon_{taille}x{taille}.png"))
        pixmap_logo(taille * 2).save(str(jeu / f"icon_{taille}x{taille}@2x.png"))

    subprocess.run(
        ["iconutil", "-c", "icns", str(jeu), "-o", str(destination)], check=True
    )
    shutil.rmtree(jeu)


def ecrire_plist(chemin: Path, paquets: Path, amorce: Path) -> None:
    contenu = {
        "CFBundleName": NOM,
        "CFBundleDisplayName": NOM,
        "CFBundleExecutable": NOM,
        "CFBundleIdentifier": IDENTIFIANT,
        "CFBundleIconFile": f"{NOM}.icns",
        "CFBundlePackageType": "APPL",
        "CFBundleShortVersionString": VERSION,
        "CFBundleVersion": VERSION,
        "NSHighResolutionCapable": True,
        # Utilitaire de barre de menus : pas d'icône au Dock, pas de barre de
        # menus propre. C'est le pendant déclaratif du mode accessoire.
        "LSUIElement": True,
        # L'exécutable du paquet est l'interpréteur lui-même, qui ne reçoit
        # aucun argument de la part du système : c'est par l'environnement
        # qu'on lui indique quoi charger. Python importe `sitecustomize` tout
        # seul au démarrage, et c'est ce module qui lance l'application.
        "LSEnvironment": {"PYTHONPATH": f"{amorce}:{paquets}"},
    }
    chemin.write_bytes(plistlib.dumps(contenu))


def ecrire_amorce(dossier: Path) -> None:
    """Écrit le module qui démarre l'application, chemins inscrits en dur.

    Un script shell qui `exec`ait l'interpréteur ne convenait pas : le système
    perd alors la trace de l'application qu'il vient de lancer, et son icône
    de barre de menus n'est jamais placée. En faisant de l'interpréteur
    l'exécutable du paquet, il n'y a plus de changement de programme en cours
    de route. Reste à lui dire quoi exécuter, puisque le système ne lui passe
    aucun argument : `sitecustomize` est importé d'office par Python, c'est
    donc là que l'application démarre.
    """
    dossier.mkdir(parents=True, exist_ok=True)
    (dossier / "sitecustomize.py").write_text(
        '"""Amorce du paquet. Fabriqué par outils/creer_app.py."""\n'
        "\n"
        "import os\n"
        "import sys\n"
        "\n"
        f'RACINE = "{RACINE}"\n'
        "\n"
        "\n"
        "def _demarrer():\n"
        "    os.chdir(RACINE)\n"
        "    sys.path.insert(0, RACINE)\n"
        "\n"
        "    # Lancée d'un double-clic, l'application n'a aucun terminal où se\n"
        "    # plaindre : sans ce journal, une erreur de démarrage est invisible.\n"
        "    journal = os.path.expanduser('~/.knowyourcode/journal.log')\n"
        "    os.makedirs(os.path.dirname(journal), exist_ok=True)\n"
        "    sortie = open(journal, 'a', buffering=1, encoding='utf-8')\n"
        "    sys.stdout = sys.stderr = sortie\n"
        "\n"
        "    from connais_ton_code.application import lancer\n"
        "\n"
        "    raise SystemExit(lancer())\n"
        "\n"
        "\n"
        "_demarrer()\n",
        encoding="utf-8",
    )


def _interpreteur_reel() -> Path:
    """Trouve le vrai exécutable Python, et non le relais qui y mène.

    Sur les Python de python.org, `bin/python3` est un petit programme qui
    ré-exécute `Resources/Python.app/Contents/MacOS/Python`. Copier le relais
    ne servirait à rien : c'est le second qui deviendrait le processus, et
    macOS lui attribuerait l'identité de Python plutôt que la nôtre.
    """
    dans_le_cadriciel = (
        Path(sys.base_prefix) / "Resources" / "Python.app" / "Contents" / "MacOS" / "Python"
    )
    if dans_le_cadriciel.exists():
        return dans_le_cadriciel
    return Path(os.path.realpath(_venv() / "bin" / "python3"))


def copier_interpreteur(destination: Path) -> Path:
    """Installe dans le paquet un interpréteur, et rend le chemin des paquets.

    Un lien symbolique ne suffirait pas : macOS suivrait le lien et
    considérerait que l'exécutable vit hors du paquet, ce qui lui ferait
    perdre l'identité qu'on cherche justement à lui donner.
    """
    copie = destination / NOM
    shutil.copy2(_interpreteur_reel(), copie)
    copie.chmod(0o755)

    # Déplacer un binaire signé invalide sa signature, et macOS l'abat au
    # démarrage. Une signature locale suffit à le laisser vivre.
    subprocess.run(["codesign", "--force", "--sign", "-", str(copie)], check=True)

    version = f"python{sys.version_info.major}.{sys.version_info.minor}"
    return _venv() / "lib" / version / "site-packages"


def main() -> int:
    if sys.platform != "darwin":
        raise SystemExit("Ce script ne sert qu'à macOS.")

    _application = QApplication(sys.argv)  # noqa: F841

    paquet = RACINE / f"{NOM}.app"
    if paquet.exists():
        shutil.rmtree(paquet)

    binaires = paquet / "Contents" / "MacOS"
    ressources = paquet / "Contents" / "Resources"
    binaires.mkdir(parents=True)
    ressources.mkdir(parents=True)

    amorce = ressources / "amorce"
    paquets = copier_interpreteur(binaires)
    ecrire_amorce(amorce)
    ecrire_plist(paquet / "Contents" / "Info.plist", paquets, amorce)
    ecrire_icone(ressources / f"{NOM}.icns")

    # Sans cette secousse, le Finder garde en cache l'icône du paquet précédent.
    subprocess.run(["touch", str(paquet)], check=False)

    print(f"{paquet} est prêt.")
    print("Double-cliquez dessus, ou glissez-le dans le dossier Applications.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
