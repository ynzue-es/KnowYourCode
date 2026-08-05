#!/usr/bin/env python3
"""Vérification du générateur de cartes, sans interface et sans réseau.

Le réseau est bouchonné : ce qu'on contrôle ici n'est pas Mistral mais ce que
le générateur fait de ce qu'on lui rend. Les deux moitiés du travail sont donc
séparables — la consigne se juge à l'usage, la lecture de la réponse se juge
ici, et c'est elle qui décide ce qui atteint l'écran.

Le script se ferme tout seul et rend un code de sortie non nul si un contrôle
échoue.

    python outils/verif_generateur.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import urllib.error
from pathlib import Path

# Avant tout import du paquet : la vérification ne doit écrire ni dans le cache
# réel ni dans l'historique.
DOSSIER_TEST = tempfile.mkdtemp(prefix="knowyourcode-generateur-")
os.environ["KNOWYOURCODE_DOSSIER"] = DOSSIER_TEST

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from connais_ton_code.cartes import Forme, defauts  # noqa: E402
from connais_ton_code.generateur import (  # noqa: E402
    CacheSeries,
    GenerateurFactice,
    GenerateurMistral,
    cle_de_cache,
)
from connais_ton_code.modeles import Extrait  # noqa: E402
from connais_ton_code.reperage import reperer  # noqa: E402

_constats: list[tuple[bool, str]] = []


def _verifier(condition: bool, description: str) -> None:
    _constats.append((bool(condition), description))


# Quatre repères de poids différents sur sept lignes : une valeur par défaut
# mutable, un `or` de repli, un gestionnaire de contexte, une clause `except`.
# De quoi couvrir les quatre formes et les deux catégories sans écrire un
# fichier entier.
CODE = """def charger_reglages(chemin, defauts={}):
    try:
        with open(chemin) as fichier:
            brut = fichier.read()
    except OSError:
        return defauts
    return json.loads(brut) or defauts
"""

CODE_SANS_REPERE = """def total(a, b):
    somme = a + b
    return somme
"""


def _extrait(identifiant: str = "reglages-1", code: str = CODE) -> Extrait:
    return Extrait(
        identifiant=identifiant,
        chemin_fichier="src/reglages.py",
        nom_fonction="charger_reglages",
        langage="python",
        code=code,
    )


_CARTE_QCM = {
    "forme": "qcm",
    "ligne": 1,
    "question": "Que reçoit le deuxième appel de charger_reglages fait sans defauts ?",
    "options": [
        "Le même dictionnaire que le premier appel",
        "Un dictionnaire vide construit pour lui",
        "La valeur None tant qu'on ne passe rien",
        "Une copie du dictionnaire de la signature",
    ],
    "bonne": 0,
    "attendu": [],
    "explication": (
        "Le dictionnaire écrit dans la signature de charger_reglages est "
        "construit une seule fois, à la définition. Chaque appel qui omet "
        "defauts reçoit donc le même objet, et une clé ajoutée pendant un "
        "appel se retrouve dans le suivant."
    ),
}

_CARTE_REPERER = {
    "forme": "reperer",
    "ligne": 7,
    "question": (
        "Quelle ligne remplace le résultat dès qu'il est vide, et pas "
        "seulement absent ?"
    ),
    "options": [],
    "bonne": 0,
    "attendu": [],
    "explication": (
        "Le repli remplace le résultat de json.loads par defauts dès que "
        "celui-ci est faux au sens de Python. Un fichier qui contient un "
        "objet vide déclenche donc le repli, alors qu'il portait bien une "
        "valeur."
    ),
}

_CARTE_NOMMER = {
    "forme": "nommer",
    "ligne": 3,
    "question": "Comment s'appelle ce que le mot-clé de la ligne 3 met en place ?",
    "options": [],
    "bonne": 0,
    "attendu": ["gestionnaire de contexte", "context manager"],
    "explication": (
        "Le bloc garantit que fichier est refermé à la sortie, y compris si "
        "la lecture lève. Sans lui, brut resterait à écrire pendant qu'un "
        "descripteur traîne ouvert jusqu'au ramasse-miettes."
    ),
}

_CARTE_PREDIRE = {
    "forme": "predire",
    "ligne": 5,
    "question": "Que rend charger_reglages si le chemin n'existe pas ?",
    "options": [],
    "bonne": 0,
    "attendu": ["defauts", "le dictionnaire par défaut"],
    "explication": (
        "La clause n'attrape que OSError : un chemin absent y tombe et "
        "charger_reglages rend defauts sans bruit. Une erreur de décodage, "
        "elle, n'est pas rattrapée et remonte à l'appelant."
    ),
}

# Aucun nom de ce code-ci : c'est le remplissage que la douane doit refuser.
_EXPLICATION_CREUSE = (
    "Cette construction fait partie des grands classiques du langage et il "
    "vaut mieux la connaître pour ne pas se faire piéger un jour."
)


def _reponse(*cartes: dict) -> str:
    return json.dumps({"cartes": list(cartes)}, ensure_ascii=False)


class _Bouchon(GenerateurMistral):
    """Un `GenerateurMistral` qui ne diffère que par l'appel réseau.

    Tout le reste est le code réel : la lecture du JSON, la douane et le cache
    sont ceux qui tourneront en production. Une réponse qui est une exception
    est levée, pour éprouver le chemin des pannes.
    """

    def __init__(self, reponse: str | Exception, cache: CacheSeries | None = None):
        super().__init__(
            cle="clé-de-vérification",
            cache=cache if cache is not None else _cache_neuf(),
        )
        self._reponse = reponse
        self.appels = 0
        self.dernier_message = ""

    def _interroger(self, message: str) -> str:
        self.appels += 1
        self.dernier_message = message
        if isinstance(self._reponse, Exception):
            raise self._reponse
        return self._reponse


_compteur_de_caches = 0


def _cache_neuf() -> CacheSeries:
    """Un cache vierge par contrôle, sinon le premier fausse les suivants."""
    global _compteur_de_caches
    _compteur_de_caches += 1
    return CacheSeries(
        chemin=Path(DOSSIER_TEST) / f"cache-{_compteur_de_caches}.json"
    )


def verifier_lecture() -> None:
    """Une réponse bien formée donne des cartes utilisables."""
    generateur = _Bouchon(
        _reponse(_CARTE_QCM, _CARTE_REPERER, _CARTE_NOMMER, _CARTE_PREDIRE)
    )
    serie = generateur.fabriquer(_extrait())

    _verifier(serie is not None, "une réponse bien formée donne une série")
    if serie is None:
        return

    _verifier(len(serie.cartes) == 4, "les quatre cartes demandées sont rendues")
    _verifier(
        serie.extrait.identifiant == "reglages-1",
        "la série porte l'extrait sur lequel on l'a demandée",
    )
    _verifier(
        all(not defauts(carte, CODE) for carte in serie.cartes),
        "aucune carte rendue ne traîne de défaut",
    )
    _verifier(
        [carte.forme for carte in serie.cartes]
        == [Forme.QCM, Forme.REPERER, Forme.NOMMER, Forme.PREDIRE],
        "chaque carte garde la forme annoncée",
    )

    qcm, a_reperer, a_nommer, a_predire = serie.cartes

    _verifier(qcm.ligne == 1, "la carte est rattachée à la ligne qu'on a désignée")
    _verifier(
        a_reperer.ligne == 0 and a_reperer.bonne == 7,
        "la carte à repérer cache sa ligne et en fait la réponse attendue",
    )
    _verifier(
        a_nommer.notion == "gestionnaire de contexte",
        "la notion du repère est reportée sur la carte à nommer",
    )
    _verifier(
        (qcm.categorie, a_nommer.categorie) == ("robustesse", "langage"),
        "la catégorie du repère est reportée sur la carte",
    )
    _verifier(
        a_predire.attendu == ("defauts", "le dictionnaire par défaut"),
        "les formulations acceptées sont conservées telles quelles",
    )

    _verifier(
        "  1 | def charger_reglages" in generateur.dernier_message,
        "le code est soumis avec ses numéros de ligne",
    )
    _verifier(
        'la forme "nommer" y est interdite' in generateur.dernier_message
        and "« gestionnaire de contexte »" in generateur.dernier_message,
        "la consigne dit ligne par ligne si une notion est à faire nommer",
    )


def verifier_douane() -> None:
    """Ce qui sort du modèle passe par `defauts`, et ce qui cloche est jeté."""
    creuse = dict(_CARTE_NOMMER, explication=_EXPLICATION_CREUSE)
    serie = _Bouchon(
        _reponse(_CARTE_QCM, _CARTE_REPERER, creuse, _CARTE_PREDIRE)
    ).fabriquer(_extrait())

    _verifier(
        serie is not None and len(serie.cartes) == 3,
        "une explication qui ne cite rien du code est jetée, les autres passent",
    )
    _verifier(
        serie is not None
        and all(_EXPLICATION_CREUSE not in c.explication for c in serie.cartes),
        "la carte creuse n'est pas rafistolée mais bien absente",
    )

    hors_sujet = dict(_CARTE_QCM, ligne=4)
    serie = _Bouchon(_reponse(hors_sujet, _CARTE_REPERER)).fabriquer(_extrait())
    _verifier(
        serie is not None and len(serie.cartes) == 1,
        "une carte posée sur une ligne qu'on n'a pas désignée est jetée",
    )

    # La ligne 1 n'a pas de notion : le repérage l'a dit, la carte ne peut donc
    # pas demander de la nommer.
    sans_notion = dict(_CARTE_QCM, forme="nommer", options=[], attendu=["mutable"])
    serie = _Bouchon(_reponse(sans_notion, _CARTE_REPERER)).fabriquer(_extrait())
    _verifier(
        serie is not None and len(serie.cartes) == 1,
        "une carte « nommer » sur une ligne sans notion est jetée",
    )

    trois_options = dict(_CARTE_QCM, options=_CARTE_QCM["options"][:3])
    serie = _Bouchon(_reponse(trois_options, _CARTE_REPERER)).fabriquer(_extrait())
    _verifier(
        serie is not None and len(serie.cartes) == 1,
        "un QCM à trois options est jeté",
    )

    serie = _Bouchon(_reponse(creuse)).fabriquer(_extrait())
    _verifier(serie is None, "si aucune carte ne survit, la série vaut None")


def verifier_le_numero_de_ligne() -> None:
    """Le numéro de ligne se lit sous toutes les formes que le modèle emploie.

    Le code est soumis numéroté, et le modèle recopie volontiers la ligne
    entière au lieu de son seul numéro. Exiger un entier nu coûtait les trois
    quarts d'une série pour une question de forme : trois cartes sur quatre
    étaient jetées alors qu'elles désignaient la bonne ligne.
    """
    for valeur, attendu in (
        (1, "un entier nu"),
        ("1", "un entier en chaîne"),
        (" 1 ", "un entier entouré d'espaces"),
        ("  1 | def charger_reglages(chemin):", "la ligne entière recopiée"),
        ("1 | def charger_reglages(chemin):", "la ligne sans son alignement"),
    ):
        serie = _Bouchon(
            _reponse(dict(_CARTE_QCM, ligne=valeur))
        ).fabriquer(_extrait())
        _verifier(
            serie is not None and serie.cartes[0].ligne == 1,
            f"le numéro de ligne se lit quand le modèle rend {attendu}",
        )

    # L'indulgence s'arrête là : elle ne sert qu'à retrouver un numéro, jamais
    # à en inventer un. Une ligne qu'on n'a pas désignée reste écartée.
    for valeur, ce_que_c_est in (
        (True, "un booléen, qui vaudrait la ligne 1 en Python"),
        ("quatre", "un nombre écrit en toutes lettres"),
        ("", "une valeur vide"),
        (None, "rien du tout"),
    ):
        serie = _Bouchon(
            _reponse(dict(_CARTE_QCM, ligne=valeur), _CARTE_REPERER)
        ).fabriquer(_extrait())
        _verifier(
            serie is not None and len(serie.cartes) == 1,
            f"une carte est jetée quand sa ligne est {ce_que_c_est}",
        )


def verifier_pannes() -> None:
    """Aucune panne ne remonte : tout se traduit par `None`."""
    _verifier(
        _Bouchon("ceci n'est pas du JSON {").fabriquer(_extrait()) is None,
        "un JSON illisible rend None sans lever",
    )
    _verifier(
        _Bouchon(json.dumps({"verdict": "je n'ai pas compris"})).fabriquer(_extrait())
        is None,
        "un JSON valide mais sans cartes rend None",
    )
    _verifier(
        _Bouchon(json.dumps({"cartes": "quatre"})).fabriquer(_extrait()) is None,
        "des cartes qui ne sont pas une liste rendent None",
    )
    _verifier(
        _Bouchon(urllib.error.URLError("réseau coupé")).fabriquer(_extrait()) is None,
        "une panne réseau rend None sans lever",
    )
    _verifier(
        _Bouchon(
            urllib.error.HTTPError(
                "https://exemple", 429, "Too Many Requests", {}, None
            )
        ).fabriquer(_extrait())
        is None,
        "un refus HTTP rend None sans lever",
    )


def verifier_sans_repere() -> None:
    """Sans repère, on ne demande rien à personne."""
    _verifier(
        reperer(CODE_SANS_REPERE, "python") == [],
        "le code témoin n'a aucun repère",
    )

    generateur = _Bouchon(_reponse(_CARTE_QCM))
    serie = generateur.fabriquer(_extrait("total-1", CODE_SANS_REPERE))
    _verifier(serie is None, "un extrait sans repère rend None")
    _verifier(
        generateur.appels == 0,
        "un extrait sans repère ne coûte même pas un appel",
    )


def verifier_cache() -> None:
    """Une série fabriquée une fois ne se repaie pas."""
    cache = _cache_neuf()
    generateur = _Bouchon(
        _reponse(_CARTE_QCM, _CARTE_REPERER, _CARTE_NOMMER, _CARTE_PREDIRE),
        cache=cache,
    )
    extrait = _extrait()

    premiere = generateur.fabriquer(extrait)
    seconde = generateur.fabriquer(extrait)

    _verifier(generateur.appels == 1, "la deuxième demande ne refait pas d'appel")
    _verifier(
        premiere is not None
        and seconde is not None
        and premiere.cartes == seconde.cartes,
        "la série resservie est identique à celle qu'on avait fabriquée",
    )

    # Le même identifiant, une ligne de plus : les cartes d'avant parleraient
    # d'un code qui n'est plus celui qu'on affiche.
    retouche = _extrait(code=CODE + "\n\n# une ligne de plus\n")
    generateur.fabriquer(retouche)
    _verifier(generateur.appels == 2, "un code retouché refait un appel")
    _verifier(
        cle_de_cache(extrait) != cle_de_cache(retouche),
        "l'empreinte du code change la clé de cache",
    )

    tiede = CacheSeries(chemin=Path(DOSSIER_TEST) / "cache-tiede.json", anciennete=-1)
    tiede.ecrire("une-cle", premiere.cartes if premiere else ())
    _verifier(
        tiede.lire("une-cle") is None,
        "une série trop vieille est ignorée plutôt que resservie",
    )

    chemin = Path(DOSSIER_TEST) / "cache-plafond.json"
    borne = CacheSeries(chemin=chemin, gardees=2)
    for numero in range(4):
        borne.ecrire(f"cle-{numero}", premiere.cartes if premiere else ())
    contenu = json.loads(chemin.read_text(encoding="utf-8"))
    _verifier(
        len(contenu["series"]) == 2,
        "le cache s'arrête à son plafond au lieu de gonfler sans fin",
    )
    _verifier(
        set(contenu["series"]) == {"cle-2", "cle-3"},
        "ce sont les séries les plus récentes qui restent",
    )

    # Datée de maintenant, pour que ce soit bien son contenu qui la fasse
    # écarter et non sa péremption.
    abime = Path(DOSSIER_TEST) / "cache-abime.json"
    abime.write_text(
        json.dumps(
            {
                "version": 1,
                "series": {"une-cle": {"date": time.time(), "cartes": [1, 2]}},
            }
        ),
        encoding="utf-8",
    )
    _verifier(
        CacheSeries(chemin=abime).lire("une-cle") is None,
        "une entrée de cache abîmée vaut une absence, pas une exception",
    )


def verifier_factice() -> None:
    """Le factice tient debout tout seul, sans clé ni réseau."""
    extrait = _extrait()
    serie = GenerateurFactice().fabriquer(extrait)

    _verifier(serie is not None, "le générateur factice rend une série")
    if serie is None:
        return

    _verifier(len(serie.cartes) == 4, "le factice remplit la série")
    _verifier(
        all(not defauts(carte, CODE) for carte in serie.cartes),
        "toutes les cartes du factice passent la douane",
    )
    _verifier(
        {carte.forme for carte in serie.cartes} >= {Forme.QCM, Forme.REPERER},
        "le factice ne pose pas quatre fois la même forme",
    )
    _verifier(
        all(len(carte.question) <= 160 for carte in serie.cartes),
        "les intitulés recopiés sont taillés pour tenir dans une question",
    )
    _verifier(
        GenerateurFactice().fabriquer(_extrait("total-1", CODE_SANS_REPERE)) is None,
        "le factice rend None lui aussi quand il n'y a rien à demander",
    )


def main() -> int:
    verifier_lecture()
    verifier_douane()
    verifier_le_numero_de_ligne()
    verifier_pannes()
    verifier_sans_repere()
    verifier_cache()
    verifier_factice()

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
