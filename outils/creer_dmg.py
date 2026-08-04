#!/usr/bin/env python3
"""Fabrique le DMG distribuable : un paquet autonome, signé, notarisable.

`creer_app.py` fabrique un paquet qui pointe vers ce dépôt : parfait pour
travailler, inutile à donner. Ici on gèle Python, Qt et le code dans le paquet
lui-même, on le signe, et on l'enferme dans une image disque avec le raccourci
vers Applications auquel tout le monde s'attend.

    python outils/creer_dmg.py                    # signature ad hoc, essai local
    python outils/creer_dmg.py --notariser        # la vraie chaîne, pour publier

Le gel passe par PyInstaller plutôt que py2app : py2app raisonne en termes
d'environnement à recopier et se laisse facilement contaminer par le venv de
la machine, tandis que PyInstaller part du graphe des imports et rend un
paquet où plus aucun chemin du dépôt ne subsiste — ce qui est précisément le
défaut qu'on cherche à corriger.

Trois enseignements de `creer_app.py` restent valables ici et sont préservés :
l'exécutable du paquet est un vrai binaire et non un script qui en appelle un
autre, sans quoi macOS perd l'identité de l'application et n'installe jamais
son icône de barre de menus ; `LSUIElement` retire l'icône du Dock ; et le
`.icns` est dessiné depuis `logo.py`, jamais chargé d'un fichier image.
"""

from __future__ import annotations

import argparse
import os
import platform
import plistlib
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

NOM = "KnowYourCode"
IDENTIFIANT = "io.github.ynzue-es.knowyourcode"

DROITS = RACINE / "outils" / "droits.plist"
TRAVAIL = RACINE / "build"
SORTIE = RACINE / "dist"

# Les tailles attendues par `iconutil` pour un jeu d'icônes complet.
TAILLES_ICONE = (16, 32, 128, 256, 512)

# Le profil de trousseau enregistré par `xcrun notarytool store-credentials`,
# et les variables d'environnement qui permettent de s'en passer (le workflow
# GitHub n'a pas de trousseau persistant où le ranger).
VARIABLES_ASC = ("ASC_ISSUER_ID", "ASC_KEY_ID", "ASC_CLE_P8")

# Les magies Mach-O, en tête de tout binaire exécutable : 64 bits, 32 bits, et
# les archives universelles. Reconnaître un binaire à ses quatre premiers
# octets évite d'appeler `file` sur les quelques milliers de fichiers du paquet.
_MAGIES_MACH_O = {
    b"\xcf\xfa\xed\xfe",
    b"\xce\xfa\xed\xfe",
    b"\xca\xfe\xba\xbe",
    b"\xbe\xba\xfe\xca",
}

# Ce qui n'a rien à faire dans le paquet. PyInstaller n'embarque que ce qu'il
# voit importé, mais il suffit qu'une dépendance tâte le terrain dans un
# `try: import` pour l'entraîner tout entière : mieux vaut fermer la porte.
MODULES_ECARTES = (
    "tkinter",
    "PyObjCTest",
    "setuptools",
    "pip",
    "pkg_resources",
    "pydoc_data",
    "unittest",
    "numpy",
    "PIL",
)


class Echec(Exception):
    """Une étape a échoué pour une raison qu'on sait expliquer."""


def etape(message: str) -> None:
    print(f"\n\033[1m→ {message}\033[0m", flush=True)


def executer(commande: list[str], **kwargs) -> subprocess.CompletedProcess:
    """Lance une commande et laisse remonter son échec avec sa sortie."""
    resultat = subprocess.run(
        commande, capture_output=True, text=True, check=False, **kwargs
    )
    if resultat.returncode != 0:
        detail = (resultat.stderr or resultat.stdout).strip()
        raise Echec(f"{' '.join(commande[:3])}… a échoué :\n{detail}")
    return resultat


def version_du_projet() -> str:
    """Lit la version dans `pyproject.toml`, seule source de vérité.

    Le numéro finit dans le nom du DMG. Le recopier ici en ferait une
    deuxième version, qui divergerait un jour de la première, et le fichier
    publié mentirait sur son contenu.
    """
    contenu = tomllib.loads((RACINE / "pyproject.toml").read_text(encoding="utf-8"))
    return contenu["project"]["version"]


# --------------------------------------------------------------------------
# L'icône
# --------------------------------------------------------------------------


def ecrire_icone(destination: Path) -> None:
    """Assemble le .icns à partir du logo dessiné dans le code.

    Le rendu se fait sur la plateforme `offscreen` : peindre un `QPixmap` ne
    demande aucun serveur de fenêtres, et la fabrication doit pouvoir tourner
    sur un runner d'intégration continue qui n'a pas de session graphique.
    """
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PyQt6.QtWidgets import QApplication

    from connais_ton_code.logo import pixmap_logo

    _application = QApplication(sys.argv)  # noqa: F841

    jeu = destination.parent / f"{NOM}.iconset"
    if jeu.exists():
        shutil.rmtree(jeu)
    jeu.mkdir(parents=True)

    for taille in TAILLES_ICONE:
        pixmap_logo(taille).save(str(jeu / f"icon_{taille}x{taille}.png"))
        pixmap_logo(taille * 2).save(str(jeu / f"icon_{taille}x{taille}@2x.png"))

    executer(["iconutil", "-c", "icns", str(jeu), "-o", str(destination)])
    shutil.rmtree(jeu)


# --------------------------------------------------------------------------
# Le gel
# --------------------------------------------------------------------------


_AMORCE = '''"""Point d'entrée du paquet gelé. Fabriqué par outils/creer_dmg.py."""

import os
import sys


def _ouvrir_le_journal():
    brut = os.environ.get("KNOWYOURCODE_DOSSIER")
    dossier = os.path.expanduser(brut) if brut else os.path.expanduser(
        "~/.knowyourcode"
    )
    os.makedirs(dossier, exist_ok=True)
    chemin = os.path.join(dossier, "journal.log")
    sys.stdout = sys.stderr = open(chemin, "a", buffering=1, encoding="utf-8")


_ouvrir_le_journal()

from connais_ton_code.application import lancer  # noqa: E402

raise SystemExit(lancer())
'''


def ecrire_amorce(destination: Path) -> Path:
    """Écrit le script que PyInstaller prendra pour point d'entrée.

    Aucun chemin n'y est inscrit, contrairement à l'amorce de `creer_app.py` :
    c'est toute la différence entre un paquet qui ne vaut que sur cette
    machine et un paquet qu'on peut donner.

    Le journal est ouvert avant l'import du paquet applicatif : lancée d'un
    double-clic, l'application n'a aucun terminal où se plaindre, et une
    erreur d'import — une dépendance oubliée au gel, typiquement — serait
    autrement parfaitement invisible.
    """
    destination.mkdir(parents=True, exist_ok=True)
    script = destination / "amorce.py"
    script.write_text(_AMORCE, encoding="utf-8")
    return script


def geler(icone: Path) -> Path:
    """Gèle l'application en un .app autonome et rend son chemin.

    `--windowed` produit un vrai paquet, dont l'exécutable est le binaire
    d'amorçage de PyInstaller : c'est bien un programme et non un script qui
    en relaie un autre, ce dont dépend l'identité que macOS accorde à
    l'application, et donc son icône de barre de menus.
    """
    amorce = ecrire_amorce(TRAVAIL / "amorce")

    commande = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--name",
        NOM,
        "--icon",
        str(icone),
        "--osx-bundle-identifier",
        IDENTIFIANT,
        # Le paquet applicatif vit à la racine du dépôt, pas à côté de l'amorce.
        "--paths",
        str(RACINE),
        # Les briques sont toutes importées par `application.py`, mais les
        # ramasser en bloc met le gel à l'abri d'un module qui ne serait
        # atteint que par un import tardif.
        "--collect-submodules",
        "connais_ton_code",
        "--distpath",
        str(TRAVAIL / "paquets"),
        "--workpath",
        str(TRAVAIL / "travail"),
        "--specpath",
        str(TRAVAIL),
        # PyInstaller raconte par le menu chaque module qu'il ramasse : sans
        # ça, les avertissements qui comptent se perdent dans le flot.
        "--log-level",
        "WARN",
    ]
    for module in MODULES_ECARTES:
        commande += ["--exclude-module", module]
    commande.append(str(amorce))

    executer(commande, cwd=str(RACINE), env={**os.environ, "PYTHONPATH": str(RACINE)})

    paquet = TRAVAIL / "paquets" / f"{NOM}.app"
    if not paquet.is_dir():
        raise Echec(f"PyInstaller n'a pas produit {paquet}.")

    # PyInstaller laisse à côté du paquet la version en dossier simple, qui
    # pèse autant que lui et ne sert à rien pour une distribution macOS.
    doublon = TRAVAIL / "paquets" / NOM
    if doublon.is_dir():
        shutil.rmtree(doublon)

    return paquet


def alleger(paquet: Path) -> None:
    """Retire ce que le gel a embarqué par acquit de conscience.

    PyInstaller ramasse les greffons Qt en bloc. Arrive ainsi `libqpdf`, un
    lecteur de PDF déguisé en format d'image, qui traîne derrière lui le
    cadriciel QtPdf et ses sept mégaoctets — pour une application qui n'ouvre
    jamais de PDF. Les traductions de Qt subissent le même sort, sauf le
    français et l'anglais : elles ne servent qu'aux boutons des boîtes de
    dialogue du système.

    Ce ménage se fait avant la signature, faute de quoi il la briserait.
    """
    superflu = [
        *paquet.rglob("libqpdf.dylib"),
        *paquet.rglob("QtPdf.framework"),
        *(
            traduction
            for traduction in paquet.rglob("translations/*.qm")
            if not traduction.stem.endswith(("_fr", "_en"))
        ),
    ]
    for chemin in superflu:
        if chemin.is_symlink() or chemin.is_file():
            chemin.unlink()
        elif chemin.is_dir():
            shutil.rmtree(chemin)

    # PyInstaller pose à la racine des raccourcis vers les binaires enfouis
    # dans les cadriciels. Ceux qui menaient à QtPdf ne mènent plus nulle
    # part, et `codesign` refuse de sceller un paquet qu'il n'arrive pas à
    # lire en entier : il échoue alors sur un « No such file or directory »
    # qui ne nomme que le paquet.
    for lien in paquet.rglob("*"):
        if lien.is_symlink() and not lien.exists():
            lien.unlink()


def ajuster_plist(paquet: Path, version: str) -> None:
    """Complète l'Info.plist de PyInstaller de ce que macOS attend ici.

    PyInstaller ne connaît pas la vocation du programme qu'il gèle : sans
    `LSUIElement`, l'application apparaîtrait au Dock et dans le sélecteur
    d'applications, ce qui n'a aucun sens pour un utilitaire qui ne montre
    jamais de fenêtre principale.
    """
    chemin = paquet / "Contents" / "Info.plist"
    contenu = plistlib.loads(chemin.read_bytes())
    contenu.update(
        {
            "CFBundleName": NOM,
            "CFBundleDisplayName": NOM,
            "CFBundleIdentifier": IDENTIFIANT,
            "CFBundleShortVersionString": version,
            "CFBundleVersion": version,
            "NSHighResolutionCapable": True,
            "LSUIElement": True,
            "LSMinimumSystemVersion": "11.0",
            "NSHumanReadableCopyright": "MIT — Yannis Nzue Essono",
        }
    )
    chemin.write_bytes(plistlib.dumps(contenu))


# --------------------------------------------------------------------------
# La signature
# --------------------------------------------------------------------------


def identite_disponible(demandee: str | None) -> str | None:
    """Choisit l'identité de signature, ou rend None s'il n'y en a aucune.

    Une identité explicite n'est pas vérifiée : si elle est mauvaise,
    `codesign` le dira mieux que nous.
    """
    if demandee:
        return demandee

    resultat = subprocess.run(
        ["security", "find-identity", "-v", "-p", "codesigning"],
        capture_output=True,
        text=True,
        check=False,
    )
    trouvees = re.findall(r'"(Developer ID Application: [^"]+)"', resultat.stdout)
    return trouvees[0] if trouvees else None


def _est_mach_o(chemin: Path) -> bool:
    try:
        with chemin.open("rb") as fichier:
            return fichier.read(4) in _MAGIES_MACH_O
    except OSError:
        return False


def _a_signer(paquet: Path) -> list[Path]:
    """Rend les éléments à signer, du plus profond au plus superficiel.

    Apple déconseille `codesign --deep`, qui applique aveuglément les mêmes
    options à tout ce qu'il croise et produit régulièrement des paquets que la
    notarisation refuse. On parcourt donc soi-même, en signant les feuilles
    avant les branches : sceller un cadriciel dont un `.dylib` changerait
    ensuite invaliderait le sceau.
    """
    elements: list[Path] = []
    for chemin in paquet.rglob("*"):
        if chemin.is_dir():
            if chemin.suffix in (".framework", ".app"):
                elements.append(chemin)
            continue
        if chemin.is_symlink():
            continue
        if chemin.suffix in (".so", ".dylib") or _est_mach_o(chemin):
            elements.append(chemin)

    # Les cadriciels sont scellés d'un bloc : leur contenu est déjà couvert.
    cadriciels = [element for element in elements if element.suffix == ".framework"]
    elements = [
        element
        for element in elements
        if element.suffix == ".framework"
        or not any(cadriciel in element.parents for cadriciel in cadriciels)
    ]
    return sorted(elements, key=lambda chemin: len(chemin.parts), reverse=True)


def signer(paquet: Path, identite: str | None) -> None:
    """Signe le paquet avec runtime durci, de l'intérieur vers l'extérieur.

    `identite` à None vaut signature ad hoc : le paquet démarre sur cette
    machine, mais aucune autre ne l'acceptera. C'est le mode d'essai.
    """
    reelle = identite is not None
    signature = identite or "-"

    base = ["codesign", "--force", "--options", "runtime", "--sign", signature]
    # L'horodatage exige le serveur d'Apple et une vraie identité ; une
    # signature ad hoc n'a rien à horodater et la commande refuserait.
    base += ["--timestamp"] if reelle else ["--timestamp=none"]

    elements = _a_signer(paquet)
    print(f"  {len(elements)} binaires et cadriciels à sceller")
    for element in elements:
        # Un fichier en lecture seule fait échouer la réécriture de sa
        # signature ; certaines roues Python en livrent.
        element.chmod(element.stat().st_mode | stat.S_IWUSR)
        executer(base + [str(element)])

    # Les droits ne valent que sur l'exécutable principal : c'est lui que le
    # runtime durci interroge au lancement.
    executer(base + ["--entitlements", str(DROITS), str(paquet)])
    # `--deep` est déconseillé pour signer, mais c'est le bon outil pour
    # relire : il redescend dans tout ce qui vient d'être scellé.
    executer(["codesign", "--verify", "--deep", "--strict", str(paquet)])

    if reelle:
        print(f"  signé par « {signature} », horodaté")
    else:
        print(
            "  \033[33msignature ad hoc\033[0m : le paquet tourne ici, mais "
            "macOS le refusera\n  sur toute autre machine. Voir outils/PUBLIER.md."
        )


# --------------------------------------------------------------------------
# L'image disque
# --------------------------------------------------------------------------


def construire_dmg(paquet: Path, version: str) -> Path:
    """Enferme le paquet dans un DMG compressé, avec le lien vers Applications.

    `hdiutil` plutôt que `create-dmg` : la commande est fournie par macOS, et
    une chaîne de publication qui dépend d'un outil à installer casse le jour
    où on la lance ailleurs.
    """
    SORTIE.mkdir(parents=True, exist_ok=True)
    dmg = SORTIE / f"{NOM}-{version}-{platform.machine()}.dmg"
    dmg.unlink(missing_ok=True)

    with tempfile.TemporaryDirectory(prefix="knowyourcode-dmg-") as brut:
        scene = Path(brut) / "scene"
        scene.mkdir()

        # `ditto` plutôt que `shutil.copytree` : lui seul reporte les
        # attributs étendus, dont la signature dépend.
        executer(["ditto", str(paquet), str(scene / paquet.name)])
        (scene / "Applications").symlink_to("/Applications")

        executer(
            [
                "hdiutil",
                "create",
                "-volname",
                f"{NOM} {version}",
                "-srcfolder",
                str(scene),
                "-fs",
                "HFS+",
                "-format",
                "UDZO",
                "-imagekey",
                "zlib-level=9",
                "-ov",
                "-quiet",
                str(dmg),
            ]
        )
    return dmg


# --------------------------------------------------------------------------
# La notarisation
# --------------------------------------------------------------------------


def _identifiants_notarisation(profil: str | None) -> list[str]:
    """Rend les arguments d'authentification de `notarytool`.

    Deux chemins possibles : un profil rangé dans le trousseau, pratique sur
    une machine de travail, ou une clé d'API passée par l'environnement, seule
    option quand il n'y a pas de trousseau qui survit à la session.
    """
    if profil:
        return ["--keychain-profile", profil]

    manquantes = [nom for nom in VARIABLES_ASC if not os.environ.get(nom)]
    if not manquantes:
        return [
            "--issuer",
            os.environ["ASC_ISSUER_ID"],
            "--key-id",
            os.environ["ASC_KEY_ID"],
            "--key",
            os.environ["ASC_CLE_P8"],
        ]

    raise Echec(
        "Impossible de notariser : aucun identifiant App Store Connect.\n"
        "  Soit --profil-trousseau NOM, après un "
        "`xcrun notarytool store-credentials`,\n"
        "  soit les variables " + ", ".join(VARIABLES_ASC) + " "
        f"(manquent : {', '.join(manquantes)}).\n"
        "  Le mode d'emploi complet est dans outils/PUBLIER.md."
    )


def notariser(dmg: Path, profil: str | None) -> None:
    """Soumet le DMG à Apple, y agrafe le ticket, et contrôle le résultat.

    L'agrafage est ce qui rend le DMG utilisable hors ligne : sans lui, la
    machine qui l'ouvre doit interroger Apple pour savoir qu'il est notarisé.
    """
    identifiants = _identifiants_notarisation(profil)

    print("  soumission à Apple, l'attente dure de quelques minutes à une heure…")
    resultat = executer(
        ["xcrun", "notarytool", "submit", str(dmg), "--wait", *identifiants]
    )
    print(resultat.stdout.strip())
    if "status: Accepted" not in resultat.stdout:
        raise Echec(
            "Apple n'a pas accepté le paquet. `xcrun notarytool log <id> "
            + " ".join(identifiants)
            + "` en donne le détail."
        )

    executer(["xcrun", "stapler", "staple", str(dmg)])
    executer(
        [
            "spctl",
            "-a",
            "-t",
            "open",
            "--context",
            "context:primary-signature",
            "-v",
            str(dmg),
        ]
    )
    print("  ticket agrafé, Gatekeeper accepte l'image.")


# --------------------------------------------------------------------------


def _analyser_arguments() -> argparse.Namespace:
    analyseur = argparse.ArgumentParser(
        description="Fabrique le DMG distribuable de KnowYourCode.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    analyseur.add_argument(
        "--identite",
        help="Nom de l'identité de signature. Par défaut, la première "
        "« Developer ID Application » du trousseau.",
    )
    analyseur.add_argument(
        "--sans-signature",
        action="store_true",
        help="Ne signe pas du tout. Le paquet ne démarrera nulle part, "
        "y compris ici : pour inspecter le gel, rien de plus.",
    )
    analyseur.add_argument(
        "--notariser",
        action="store_true",
        help="Soumet le DMG à Apple et y agrafe le ticket.",
    )
    analyseur.add_argument(
        "--profil-trousseau",
        help="Profil enregistré par `xcrun notarytool store-credentials`. "
        f"À défaut, les variables {', '.join(VARIABLES_ASC)}.",
    )
    return analyseur.parse_args()


def main() -> int:
    if sys.platform != "darwin":
        print("Ce script ne sert qu'à macOS.", file=sys.stderr)
        return 1

    arguments = _analyser_arguments()
    version = version_du_projet()

    try:
        if arguments.notariser:
            if arguments.sans_signature:
                raise Echec(
                    "--notariser et --sans-signature s'excluent : Apple ne "
                    "notarise que ce qui est signé."
                )
            # Buter sur un identifiant manquant maintenant plutôt qu'après
            # trois minutes de gel.
            _identifiants_notarisation(arguments.profil_trousseau)

        TRAVAIL.mkdir(parents=True, exist_ok=True)

        etape(f"Icône de {NOM} {version}")
        icone = TRAVAIL / f"{NOM}.icns"
        ecrire_icone(icone)

        etape("Gel de l'application (quelques minutes)")
        paquet = geler(icone)
        alleger(paquet)
        ajuster_plist(paquet, version)
        poids = executer(["du", "-sh", str(paquet)]).stdout.split()[0]
        print(f"  {paquet} — {poids}")

        if arguments.sans_signature:
            etape("Signature sautée (--sans-signature)")
        else:
            identite = identite_disponible(arguments.identite)
            etape("Signature" + (f" par « {identite} »" if identite else " ad hoc"))
            signer(paquet, identite)

        etape("Image disque")
        dmg = construire_dmg(paquet, version)
        poids = executer(["du", "-sh", str(dmg)]).stdout.split()[0]
        print(f"  {dmg} — {poids}")

        if arguments.notariser:
            etape("Notarisation")
            notariser(dmg, arguments.profil_trousseau)

        print(f"\n\033[1m{dmg}\033[0m est prêt.")
        return 0

    except Echec as echec:
        print(f"\n\033[31mÉchec\033[0m : {echec}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
