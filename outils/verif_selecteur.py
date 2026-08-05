#!/usr/bin/env python3
"""Vérification du sélecteur : ce qu'il retient, ce qu'il préfère, ce qu'il coûte.

Le sélecteur ne sert plus une fonction au hasard, il sert une fonction qui a
quelque chose à dire. Trois promesses en découlent et se vérifient ici : rien
de vide n'est jamais proposé, ce qui apprend le plus sort le plus souvent, et
l'appel reste assez court pour tenir dans l'ouverture du panneau.

Aucune interface : le script tourne en console, affiche ses constats et rend
un code de sortie non nul si l'un d'eux échoue.

    python outils/verif_selecteur.py
"""

from __future__ import annotations

import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from connais_ton_code.modeles import Extrait  # noqa: E402
from connais_ton_code.reperage import (  # noqa: E402
    POIDS_COURANT,
    POIDS_NOTION,
    POIDS_SECURITE,
    Repere,
    reperer,
)
from connais_ton_code.selecteur import (  # noqa: E402
    _EXTRAITS_FACTICES,
    ANALYSES_MAX,
    APPOINT_RICHESSE,
    REPERES_EN_APPOINT,
    REPERES_MIN,
    SelecteurFactice,
    SelecteurProjet,
    poids_de,
)

_constats: list[tuple[bool, str]] = []


def _verifier(condition: bool, description: str) -> None:
    _constats.append((bool(condition), description))


# Le dépôt sur lequel le temps se mesure. C'est le projet lui-même : le seul
# corpus réel sous la main, et celui qui a motivé le chantier.
DEPOT = Path(__file__).resolve().parent.parent

# La borne du temps de `choisir`. Le recensement des fichiers en occupe déjà
# les quatre cinquièmes ; le repérage n'ajoute qu'une fraction. Un quart de
# seconde suffit sur ce dépôt, on laisse le double pour un cache disque froid
# ou une machine occupée — au-delà d'une demi-seconde, l'ouverture du panneau
# cesserait de passer pour instantanée, et c'est là que la promesse casse.
BORNE_MS = 500

# Le corpus fait main. Trois fonctions écrites pour leurs repères : une faille
# de sécurité, une tournure courante, et rien du tout. Le script vérifie ces
# poids avant de s'en servir — un motif de repérage qui bouge ne doit pas
# rendre les constats suivants faussement rassurants.
_LOURDE = '''def executer_requete(curseur, table, valeur):
    lignes = []
    curseur.execute(f"SELECT * FROM {table} WHERE nom = '{valeur}'")
    for ligne in curseur.fetchall():
        lignes.append(ligne)
    return lignes
'''

# Trois repères sur six lignes : de quoi tenir une série. Les deux autres
# fixtures n'en portent qu'un chacune, ce qui les met sous le plancher — c'est
# précisément ce qui permet de vérifier que le plancher trie.
_RICHE = '''def charger(table, valeur, cache={}):
    if table in cache:
        return cache[table]
    try:
        resultat = eval(valeur)
    except:
        resultat = None
    return resultat
'''

_LEGERE = '''def lister_actifs(elements):
    retenus = [element.libelle for element in elements]
    retenus.sort()
    return retenus
'''

_PLATE = '''def additionner(premier, second):
    total = premier
    total = total + second
    return total
'''


def _corpus(**fonctions: str) -> Path:
    """Écrit un projet jetable, un fichier par fonction."""
    dossier = Path(tempfile.mkdtemp(prefix="knowyourcode-selecteur-"))
    for nom, code in fonctions.items():
        (dossier / f"{nom}.py").write_text(code, encoding="utf-8")
    return dossier


def _tirer(dossier: Path, tirages: int, deja_vus: tuple[str, ...] = ()) -> Counter[str]:
    """Compte les noms de fonction rendus sur une série de tirages."""
    selecteur = SelecteurProjet()
    comptes: Counter[str] = Counter()
    for _ in range(tirages):
        extrait = selecteur.choisir(deja_vus, dossier)
        comptes[extrait.nom_fonction if extrait else "∅"] += 1
    return comptes


def verifier_le_bareme() -> None:
    """Contrôles sur la formule de pondération, sans toucher au disque."""
    securite = Repere(ligne=1, intitule="", categorie="securite", poids=POIDS_SECURITE)
    courant = Repere(ligne=1, intitule="", categorie="langage", poids=POIDS_COURANT)

    _verifier(
        poids_de([securite]) == POIDS_SECURITE,
        "un repère seul pèse exactement son poids",
    )
    _verifier(
        poids_de([courant] * 12)
        == POIDS_COURANT + APPOINT_RICHESSE * REPERES_EN_APPOINT,
        "l'appoint de richesse est plafonné, une fonction bavarde ne gonfle pas",
    )
    _verifier(
        poids_de([courant] * 12) < poids_de([securite]),
        "aucune accumulation de tournures courantes ne rattrape un repère lourd",
    )

    # C'est cette comparaison qui fixe l'appoint, et c'est la plus serrée : 54
    # contre 55. La relâcher ferait passer une fonction bavarde devant un
    # extrait qui porte une vraie notion — exactement ce que le barème refuse.
    notion = Repere(ligne=1, intitule="", categorie="langage", poids=POIDS_NOTION)
    _verifier(
        poids_de([courant] * 12) < poids_de([notion]),
        "ni la moindre notion, qui est la marge la plus étroite du barème",
    )


def _depot_ecrit(maigre_seul: bool) -> Path:
    """Un faux projet d'un ou deux fichiers, pour éprouver l'ordre du repli."""
    dossier = Path(tempfile.mkdtemp(prefix="knowyourcode-depot-"))
    (dossier / "maigre.py").write_text(_LEGERE, encoding="utf-8")
    if not maigre_seul:
        (dossier / "riche.py").write_text(_RICHE, encoding="utf-8")
    return dossier


def verifier_le_plancher_de_reperes() -> None:
    """Une carte n'est pas une série : les extraits trop pauvres sont écartés."""
    selecteur = SelecteurProjet()

    maigre = Extrait(
        identifiant="maigre.py:maigre",
        chemin_fichier="maigre.py",
        nom_fonction="maigre",
        langage="python",
        code=_LEGERE,
    )
    riche = Extrait(
        identifiant="riche.py:riche",
        chemin_fichier="riche.py",
        nom_fonction="riche",
        langage="python",
        code=_RICHE,
    )

    _verifier(
        len(reperer(_LEGERE, "python")) < REPERES_MIN <= len(reperer(_RICHE, "python")),
        "le corpus de référence encadre bien le plancher",
    )

    riches, maigres = selecteur._peser([maigre, riche])
    _verifier(
        [extrait.nom_fonction for extrait, _ in riches] == ["riche"],
        "un extrait à repère unique n'est pas compté parmi ceux qui tiennent une série",
    )
    _verifier(
        [extrait.nom_fonction for extrait, _ in maigres] == ["maigre"],
        "il est mis de côté, pas jeté",
    )

    # Le repli compte autant que le plancher : un petit projet où rien n'est
    # riche doit encore poser une question, pas rester muet.
    _verifier(
        selecteur.choisir([], _depot_ecrit(maigre_seul=True)) is not None,
        "faute de mieux, l'extrait pauvre est repris plutôt que rien",
    )

    # Une fois le neuf épuisé, revoir une bonne fonction vaut mieux que d'en
    # découvrir une qui n'a qu'une carte à offrir. La riche est donc marquée
    # comme déjà vue, la pauvre non : c'est la riche qui doit ressortir.
    dossier = _depot_ecrit(maigre_seul=False)
    recenses = {
        e.nom_fonction: e.identifiant
        for e in SelecteurProjet()._recenser(dossier)
    }
    tires = {
        selecteur.choisir([recenses["charger"]], dossier).nom_fonction
        for _ in range(20)
    }
    _verifier(
        tires == {"charger"},
        "le neuf pauvre ne passe pas devant la révision d'une bonne fonction",
    )


def verifier_le_corpus_de_reference() -> None:
    """Contrôles sur les extraits écrits pour cette vérification."""
    lourds = reperer(_LOURDE, "python")
    legers = reperer(_LEGERE, "python")

    _verifier(
        bool(lourds) and lourds[0].poids == POIDS_SECURITE,
        "la fonction de référence lourde porte bien un repère de sécurité",
    )
    _verifier(
        bool(legers) and legers[0].poids == POIDS_COURANT,
        "la fonction de référence légère ne porte qu'une tournure courante",
    )
    _verifier(
        not reperer(_PLATE, "python"),
        "la fonction de référence plate ne porte aucun repère",
    )


def verifier_les_refus() -> None:
    """Contrôles sur ce que le sélecteur refuse de servir."""
    selecteur = SelecteurProjet()

    _verifier(selecteur.choisir(()) is None, "sans dossier, rien n'est proposé")
    _verifier(
        selecteur.choisir((), DEPOT / "il-n-y-a-rien-ici") is None,
        "un dossier qui n'existe pas ne fait pas tomber le sélecteur",
    )

    vide = _corpus()
    _verifier(selecteur.choisir((), vide) is None, "un dossier sans code rend None")

    sterile = _corpus(plate=_PLATE, encore=_PLATE)
    comptes = _tirer(sterile, 40)
    _verifier(
        comptes["∅"] == 40,
        "un projet dont aucune fonction n'est repérable rend None, pas un extrait vide",
    )

    melange = _corpus(lourde=_LOURDE, legere=_LEGERE, plate=_PLATE)
    comptes = _tirer(melange, 300)
    _verifier(
        comptes["additionner"] == 0,
        "une fonction sans aucun repère n'est jamais choisie",
    )
    _verifier(
        comptes["∅"] == 0,
        "tant qu'un extrait est repérable, le sélecteur en sert un",
    )


def verifier_la_ponderation() -> None:
    """Contrôles sur le tirage pondéré."""
    dossier = _corpus(lourde=_LOURDE, legere=_LEGERE, plate=_PLATE)
    tirages = 1200
    comptes = _tirer(dossier, tirages)

    attendu = POIDS_SECURITE / (POIDS_SECURITE + POIDS_COURANT)
    _verifier(
        comptes["executer_requete"] > 2 * comptes["lister_actifs"],
        "un extrait à repère lourd sort nettement plus souvent qu'un extrait léger",
    )
    _verifier(
        abs(comptes["executer_requete"] / tirages - attendu) < 0.06,
        "la fréquence observée suit le barème et non un ordre de classement",
    )
    _verifier(
        comptes["lister_actifs"] > 0,
        "le tirage reste un tirage : le léger sort quand même parfois",
    )


def verifier_la_memoire() -> None:
    """Contrôles sur la préférence pour ce qui n'a jamais été vu."""
    dossier = _corpus(lourde=_LOURDE, legere=_LEGERE)
    vus = ("lourde.py:executer_requete",)

    comptes = _tirer(dossier, 60, deja_vus=vus)
    _verifier(
        comptes["lister_actifs"] == 60,
        "le neuf passe devant le poids tant qu'il reste du neuf à montrer",
    )

    tout_vu = vus + ("legere.py:lister_actifs",)
    comptes = _tirer(dossier, 60, deja_vus=tout_vu)
    _verifier(
        comptes["∅"] == 0 and comptes["executer_requete"] > comptes["lister_actifs"],
        "une fois le projet parcouru, on révise en repondérant plutôt que de se taire",
    )

    # Le repli joue aussi quand le neuf est stérile : reposer une bonne
    # fonction vaut mieux qu'en servir une qui n'a rien à dire.
    avec_plate = _corpus(lourde=_LOURDE, plate=_PLATE)
    comptes = _tirer(avec_plate, 40, deja_vus=("lourde.py:executer_requete",))
    _verifier(
        comptes["executer_requete"] == 40,
        "quand le neuf n'est pas repérable, on repasse par le corpus entier",
    )


def verifier_les_factices() -> None:
    """Contrôles sur les extraits de repli."""
    manquants = [
        extrait.identifiant
        for extrait in _EXTRAITS_FACTICES
        if not reperer(extrait.code, extrait.langage)
    ]
    _verifier(
        not manquants,
        f"tous les extraits factices portent au moins un repère ({len(_EXTRAITS_FACTICES)})",
    )

    sommet = max(
        poids_de(reperer(e.code, e.langage))
        for e in _EXTRAITS_FACTICES
        if reperer(e.code, e.langage)
    )
    _verifier(
        sommet >= POIDS_SECURITE,
        "le repli couvre jusqu'à la sécurité, la famille la plus rare",
    )

    factice = SelecteurFactice()
    servis = {factice.choisir(()) for _ in range(len(_EXTRAITS_FACTICES))}
    _verifier(
        len(servis) == len(_EXTRAITS_FACTICES),
        "le sélecteur factice fait le tour de ses extraits avant de se répéter",
    )


def verifier_le_temps() -> None:
    """Contrôle du coût réel, sur le dépôt lui-même."""
    selecteur = SelecteurProjet()
    candidats = selecteur._recenser(DEPOT)
    _verifier(
        len(candidats) > ANALYSES_MAX,
        f"le dépôt est un corpus assez gros pour que la mesure ait un sens "
        f"({len(candidats)} extraits)",
    )

    selecteur.choisir((), DEPOT)  # le premier appel paie le cache disque
    mesures = []
    for _ in range(7):
        depart = time.perf_counter()
        selecteur.choisir((), DEPOT)
        mesures.append((time.perf_counter() - depart) * 1000)
    mesures.sort()
    median = mesures[len(mesures) // 2]

    _verifier(
        median < BORNE_MS,
        f"choisir sur le dépôt tient sous {BORNE_MS} ms ({median:.0f} ms mesurées)",
    )

    # Le pire cas du repérage : un corpus où rien n'est repérable, donc où le
    # plafond d'analyses est la seule chose qui arrête la recherche. C'est lui
    # qui doit tenir, pas seulement le cas moyen.
    sterile = _corpus(**{f"plate{i}": _PLATE for i in range(200)})
    depart = time.perf_counter()
    SelecteurProjet().choisir((), sterile)
    pire = (time.perf_counter() - depart) * 1000
    _verifier(
        pire < BORNE_MS,
        f"un projet entièrement stérile tient lui aussi sous la borne "
        f"({pire:.0f} ms)",
    )


def verifier_les_copies() -> None:
    """Un worktree ou un dépôt imbriqué ne doit pas fournir de questions.

    Sans ce filtre, une machine où Claude Code a laissé des worktrees sous
    `.claude/worktrees/` fait poser des questions sur une autre branche que
    celle où l'on travaille, et repose la même fonction autant de fois qu'il
    y a de copies. Mesuré sur ce dépôt : 1540 extraits au lieu de 301.
    """
    with tempfile.TemporaryDirectory() as brut:
        racine = Path(brut)
        (racine / "vrai.py").write_text(
            "def vraie(a, b):\n"
            "    seuil = a or b or 'defaut'\n"
            "    if not seuil:\n"
            "        return None\n"
            "    return seuil\n",
            encoding="utf-8",
        )

        copie = racine / ".claude" / "worktrees" / "copie"
        copie.mkdir(parents=True)
        # Le `.git` d'un worktree est un fichier, celui d'un clone un dossier.
        (copie / ".git").write_text("gitdir: ailleurs\n", encoding="utf-8")
        (copie / "faux.py").write_text(
            "def fausse(a, b):\n"
            "    seuil = a or b or 'defaut'\n"
            "    if not seuil:\n"
            "        return None\n"
            "    return seuil\n",
            encoding="utf-8",
        )

        imbrique = racine / "dependance"
        (imbrique / ".git").mkdir(parents=True)
        (imbrique / "tiers.py").write_text(
            "def tierce(a, b):\n"
            "    seuil = a or b or 'defaut'\n"
            "    if not seuil:\n"
            "        return None\n"
            "    return seuil\n",
            encoding="utf-8",
        )

        noms = {e.nom_fonction for e in SelecteurProjet()._recenser(racine)}
        _verifier("vraie" in noms, "le code du projet lui-même est bien recensé")
        _verifier("fausse" not in noms, "un worktree n'est pas parcouru")
        _verifier("tierce" not in noms, "un dépôt imbriqué n'est pas parcouru non plus")


def main() -> int:
    verifier_le_bareme()
    verifier_le_plancher_de_reperes()
    verifier_les_copies()
    verifier_le_corpus_de_reference()
    verifier_les_refus()
    verifier_la_ponderation()
    verifier_la_memoire()
    verifier_les_factices()
    verifier_le_temps()

    for ok, description in _constats:
        print(f"{'  ok  ' if ok else 'ÉCHEC '} {description}")

    if not _constats:
        print("aucune vérification n'a pu être exécutée")
        return 1

    echecs = [description for ok, description in _constats if not ok]
    print()
    print(f"{len(_constats) - len(echecs)}/{len(_constats)} vérifications passées")
    return 1 if echecs else 0


if __name__ == "__main__":
    raise SystemExit(main())
