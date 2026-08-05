#!/usr/bin/env python3
"""Vérification de la progression : l'historique et son calcul.

Rien d'ici n'ouvre de fenêtre ni ne touche au réseau. Ce sont les deux briques
dont dépend la promesse du produit — revenir tous les jours — et elles se
vérifient entièrement à froid : d'un côté la relecture du fichier, y compris
celui qu'un utilisateur a déjà sur son disque au format de l'ancien exercice,
de l'autre le calcul de la série et des taux.

Le script se ferme tout seul et rend un code de sortie non nul si une des
vérifications échoue.

    python outils/verif_progression.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

# Avant tout import du paquet : la vérification ne doit pas écrire dans
# l'historique réel.
DOSSIER_TEST = tempfile.mkdtemp(prefix="knowyourcode-progression-")
os.environ["KNOWYOURCODE_DOSSIER"] = DOSSIER_TEST

# Lancé depuis n'importe où, le script doit trouver le paquet, qui est un
# dossier au-dessus du sien.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from connais_ton_code.cartes import Carte, Correction, Forme  # noqa: E402
from connais_ton_code.historique import Historique  # noqa: E402
from connais_ton_code.modeles import (  # noqa: E402
    ANCIENNE,
    CARTE,
    PASSE,
    EntreeHistorique,
    Extrait,
)
from connais_ton_code.reperage import LANGAGE, ROBUSTESSE, SECURITE  # noqa: E402
from connais_ton_code.statistiques import (  # noqa: E402
    JOURS_ACTIVITE,
    calculer_statistiques,
)

_constats: list[tuple[bool, str]] = []


def _verifier(condition: bool, description: str) -> None:
    _constats.append((bool(condition), description))


def _carte(
    jour: int,
    juste: bool,
    notion: str | None = "fermeture",
    categorie: str = LANGAGE,
    identifiant: str = "fct-a",
) -> EntreeHistorique:
    """Une carte répondue tel jour d'août 2026, pour les contrôles de calcul."""
    return EntreeHistorique(
        identifiant=identifiant,
        chemin_fichier="src/a.py",
        nom_fonction="additionner",
        langage="python",
        date=datetime(2026, 8, jour, 10, tzinfo=timezone.utc),
        issue=CARTE,
        forme=Forme.QCM.name,
        categorie=categorie,
        notion=notion,
        ligne=3,
        juste=juste,
    )


def verifier_serie() -> None:
    """Contrôles sur la série de jours d'affilée.

    C'est le chiffre que l'utilisateur vient regarder, et le seul qu'il peut
    perdre. Il dépend de la date du jour : elle est passée en paramètre, sinon
    la vérification changerait de résultat à minuit.
    """
    jour = date(2026, 8, 5)

    suite = calculer_statistiques(
        [_carte(3, True), _carte(4, True), _carte(5, False)], aujourdhui=jour
    )
    _verifier(suite.serie_en_cours == 3, "trois jours d'affilée font une série de trois")
    _verifier(
        suite.faite_aujourdhui,
        "une carte répondue aujourd'hui met la journée à l'abri",
    )

    trou = calculer_statistiques(
        [_carte(1, True), _carte(3, True), _carte(5, True)], aujourdhui=jour
    )
    _verifier(trou.serie_en_cours == 1, "un jour manquant casse la série")

    ancienne = calculer_statistiques([_carte(1, True), _carte(2, True)], aujourdhui=jour)
    _verifier(
        ancienne.serie_en_cours == 0,
        "une série finie avant-hier ne compte plus",
    )
    _verifier(
        not ancienne.faite_aujourdhui,
        "sans carte du jour, la journée n'est pas faite",
    )

    veille = calculer_statistiques([_carte(3, True), _carte(4, True)], aujourdhui=jour)
    _verifier(
        veille.serie_en_cours == 2,
        "une série qui s'arrête hier compte encore, la journée n'est pas finie",
    )

    record = calculer_statistiques(
        [_carte(j, True) for j in (1, 2, 3, 4)] + [_carte(j, True) for j in (14, 15)],
        aujourdhui=date(2026, 8, 15),
    )
    _verifier(
        record.meilleure_serie == 4,
        "la meilleure série retient la plus longue suite, pas la dernière",
    )
    _verifier(
        record.serie_en_cours == 2,
        "la série en cours reste celle qui touche aujourd'hui",
    )

    _verifier(
        calculer_statistiques(
            [_carte(j, True) for j in (3, 4, 5)], aujourdhui=jour
        ).meilleure_serie
        == 3,
        "la série en cours compte aussi comme meilleure série",
    )

    deux_fois = calculer_statistiques(
        [_carte(5, True), _carte(5, False), _carte(5, True)], aujourdhui=jour
    )
    _verifier(
        deux_fois.serie_en_cours == 1 and deux_fois.jours_actifs == 1,
        "trois cartes le même jour font un jour, pas trois",
    )


def verifier_reussite() -> None:
    """Contrôles sur les taux par notion et par catégorie.

    C'est la liste qui fait le cours : si elle range mal, elle envoie réviser
    ce qu'on maîtrise déjà.
    """
    jour = date(2026, 8, 5)
    entrees = [
        _carte(1, True, notion="fermeture"),
        _carte(1, False, notion="fermeture"),
        _carte(2, False, notion="court-circuit", categorie=ROBUSTESSE),
        _carte(2, False, notion="court-circuit", categorie=ROBUSTESSE),
        _carte(3, True, notion="décorateur"),
        _carte(3, True, notion="décorateur"),
        _carte(4, True, notion=None, categorie=SECURITE),
    ]
    statistiques = calculer_statistiques(entrees, aujourdhui=jour)

    _verifier(
        statistiques.nombre_de_cartes == 7 and statistiques.nombre_de_justes == 4,
        "les cartes justes et le total se comptent séparément",
    )
    _verifier(
        abs(statistiques.taux_de_reussite - 4 / 7) < 1e-9,
        "le taux général est la part de cartes justes",
    )
    _verifier(
        [(r.sujet, r.justes, r.total) for r in statistiques.notions]
        == [
            ("court-circuit", 0, 2),
            ("fermeture", 1, 2),
            ("décorateur", 2, 2),
        ],
        "le taux par notion se calcule juste et remonte la plus ratée en tête",
    )
    _verifier(
        all(r.sujet is not None for r in statistiques.notions)
        and len(statistiques.notions) == 3,
        "une carte sans notion n'invente pas de notion vide",
    )
    _verifier(
        [(r.sujet, r.justes, r.total) for r in statistiques.categories]
        == [(ROBUSTESSE, 0, 2), (LANGAGE, 3, 4), (SECURITE, 1, 1)],
        "le taux par catégorie regroupe toutes les notions d'une même famille",
    )

    urgence = calculer_statistiques(
        [_carte(1, False, notion="rare")]
        + [_carte(1, False, notion="fréquente") for _ in range(4)],
        aujourdhui=jour,
    )
    _verifier(
        [r.sujet for r in urgence.notions] == ["fréquente", "rare"],
        "à taux égal, la notion la plus souvent posée passe devant",
    )


def verifier_calendrier() -> None:
    """Contrôles sur le calendrier d'activité."""
    jour = date(2026, 8, 5)
    statistiques = calculer_statistiques(
        [_carte(5, True), _carte(5, False)], aujourdhui=jour
    )
    _verifier(
        len(statistiques.activite) == JOURS_ACTIVITE == 84,
        "le calendrier couvre douze semaines, jours vides compris",
    )
    _verifier(
        statistiques.activite[-1].jour == jour
        and statistiques.activite[-1].nombre == 2,
        "le dernier jour du calendrier est aujourd'hui, avec son compte",
    )
    _verifier(
        statistiques.activite[0].jour == date(2026, 5, 14),
        "le calendrier commence quatre-vingt-trois jours avant aujourd'hui",
    )


def verifier_historique_vide() -> None:
    """Contrôles sur le premier lancement, qui est le cas le plus fréquent."""
    vide = calculer_statistiques([], aujourdhui=date(2026, 8, 5))
    _verifier(
        vide.serie_en_cours == 0
        and vide.meilleure_serie == 0
        and not vide.faite_aujourdhui
        and vide.jours_actifs == 0
        and vide.nombre_de_cartes == 0
        and vide.nombre_de_justes == 0
        and vide.taux_de_reussite == 0.0
        and vide.notions == []
        and vide.categories == []
        and vide.derniere_carte is None
        and len(vide.activite) == 84,
        "un historique vide rend des valeurs neutres sans lever",
    )


def verifier_passages() -> None:
    """Contrôles sur ce qu'un extrait passé compte, et ne compte pas."""
    jour = date(2026, 8, 5)
    passage = EntreeHistorique(
        identifiant="fct-z",
        chemin_fichier="src/z.py",
        nom_fonction="passer",
        langage="python",
        date=datetime(2026, 8, 5, 10, tzinfo=timezone.utc),
        issue=PASSE,
    )
    statistiques = calculer_statistiques([passage], aujourdhui=jour)
    _verifier(
        statistiques.nombre_de_passages == 1 and statistiques.nombre_de_cartes == 0,
        "un extrait passé se compte à part des cartes",
    )
    _verifier(
        statistiques.serie_en_cours == 0 and not statistiques.faite_aujourdhui,
        "passer un extrait n'entretient pas la série",
    )
    _verifier(
        statistiques.fonctions_couvertes == 1,
        "un extrait passé compte quand même comme vu",
    )


def verifier_lecture_historique() -> None:
    """Contrôles sur la tolérance de la relecture aux lignes invalides.

    Le fichier sur disque peut porter les traces d'une écriture interrompue :
    une ligne pareille doit être écartée, pas faire tomber toute la lecture.
    """
    chemin = Path(DOSSIER_TEST) / "historique_corrompu.json"
    brut = {
        "version": 2,
        "entrees": [
            {
                "identifiant": "ok-1",
                "chemin_fichier": "a.py",
                "nom_fonction": "f",
                "langage": "python",
                "issue": "carte",
                "date": "2026-08-01T10:00:00+00:00",
                "forme": "QCM",
                "categorie": "langage",
                "notion": "fermeture",
                "ligne": 3,
                "juste": True,
            },
            {
                "identifiant": "ok-2",
                "chemin_fichier": "b.py",
                "nom_fonction": "g",
                "langage": "python",
                "issue": "passe",
                "date": "2026-08-02T10:00:00+00:00",
            },
            # Une écriture interrompue : les champs obligatoires manquent.
            {"identifiant": "corrompu", "chemin_fichier": "c.py"},
            # Un format plus ancien, avant le renommage des champs.
            {"identifiant": "ancien-format", "fonction": "h", "date": "2024-01-03T10:00:00+00:00"},
            # Une carte sans son verdict : elle ne dit pas si c'était juste.
            {
                "identifiant": "sans-verdict",
                "chemin_fichier": "d.py",
                "nom_fonction": "i",
                "langage": "python",
                "issue": "carte",
                "date": "2026-08-03T10:00:00+00:00",
                "forme": "QCM",
                "categorie": "langage",
            },
            # Une ligne qui n'est même pas un objet.
            "une chaîne au lieu d'une entrée",
        ],
    }
    with open(chemin, "w", encoding="utf-8") as fichier:
        json.dump(brut, fichier)

    lues = Historique(chemin=chemin).entrees()
    _verifier(
        {entree.identifiant for entree in lues} == {"ok-1", "ok-2"},
        "une entrée corrompue ou d'un ancien format est ignorée sans faire tomber la lecture",
    )
    carte = next(entree for entree in lues if entree.identifiant == "ok-1")
    _verifier(
        carte.issue == CARTE
        and carte.forme == "QCM"
        and carte.notion == "fermeture"
        and carte.ligne == 3
        and carte.juste is True,
        "une carte relue retrouve sa forme, sa notion, sa ligne et son verdict",
    )


def verifier_ancien_fichier() -> None:
    """Contrôles sur l'`historique.json` que l'utilisateur a déjà sur son disque.

    C'est le point sensible du changement d'exercice. Ce fichier est écrit au
    format des explications notées : il ne contient aucune carte, et aucune
    réécriture ne pourrait lui en inventer. La relecture doit malgré tout le
    traverser sans planter et sans perdre les jours travaillés.
    """
    chemin = Path(DOSSIER_TEST) / "historique_v1.json"
    entrees = [
        {
            "identifiant": f"fct-{rang}",
            "chemin_fichier": "src/a.py",
            "nom_fonction": "additionner",
            "langage": "python",
            "date": f"2026-08-0{jour}T10:00:00+00:00",
            "issue": issue,
            **(
                {
                    "score": 70,
                    "verdict": "correct",
                    "reponse": "une explication",
                    "points_oublies": ["la division par zéro"],
                }
                if issue == "repondu"
                else {}
            ),
        }
        for rang, (jour, issue) in enumerate(
            ((1, "repondu"), (2, "repondu"), (3, "repondu"), (4, "passe"))
        )
    ]
    with open(chemin, "w", encoding="utf-8") as fichier:
        json.dump({"version": 1, "entrees": entrees}, fichier)

    historique = Historique(chemin=chemin)
    lues = historique.entrees()
    _verifier(
        len(lues) == 4,
        "un historique à l'ancien format se relit sans planter et sans tout perdre",
    )
    _verifier(
        sum(1 for entree in lues if entree.issue == ANCIENNE) == 3,
        "les entrées de l'ancien exercice sont relues comme telles, pas comme des cartes",
    )
    _verifier(
        historique.identifiants_deja_vus() == {"fct-0", "fct-1", "fct-2", "fct-3"},
        "les extraits déjà vus à l'ancien format ne seront pas reproposés",
    )

    statistiques = calculer_statistiques(lues, aujourdhui=date(2026, 8, 3))
    _verifier(
        statistiques.serie_en_cours == 3,
        "les jours travaillés à l'ancien format gardent la série en vie",
    )
    _verifier(
        statistiques.nombre_de_cartes == 0 and statistiques.taux_de_reussite == 0.0,
        "faute de juste ou faux, l'ancien format ne pèse pas sur le taux de réussite",
    )
    _verifier(
        statistiques.notions == [],
        "l'ancien format n'invente pas de notion ratée",
    )

    # Le point qui compte pour la suite : on ajoute à la file sans réécrire ce
    # qui précède, donc les deux formats cohabitent dans un même fichier.
    historique.enregistrer_carte(
        Extrait(
            identifiant="fct-neuf",
            chemin_fichier="src/b.py",
            nom_fonction="filtrer",
            langage="python",
            code="def filtrer():\n    return []\n",
        ),
        Carte(
            forme=Forme.NOMMER,
            question="Comment s'appelle ce que fait cette ligne ?",
            explication="`filtrer` rend une liste.",
            ligne=2,
            notion="fermeture",
            categorie=LANGAGE,
        ),
        Correction(juste=True, bonne_reponse="fermeture", explication="…"),
    )

    relues = Historique(chemin=chemin).entrees()
    _verifier(
        len(relues) == 5 and relues[-1].issue == CARTE and relues[-1].juste,
        "une carte neuve s'ajoute à la suite des entrées de l'ancien format",
    )
    _verifier(
        sum(1 for entree in relues if entree.issue == ANCIENNE) == 3,
        "ajouter une carte ne réécrit ni ne perd les entrées d'avant",
    )


def verifier_ecriture() -> None:
    """Contrôles sur ce qui part réellement sur le disque."""
    chemin = Path(DOSSIER_TEST) / "historique_ecriture.json"
    extrait = Extrait(
        identifiant="fct-repere",
        chemin_fichier="src/c.py",
        nom_fonction="chercher",
        langage="python",
        code="def chercher(elements):\n    return [e for e in elements]\n",
    )
    historique = Historique(chemin=chemin)
    historique.enregistrer_carte(
        extrait,
        Carte(
            forme=Forme.REPERER,
            question="Quelle ligne construit la liste ?",
            explication="La compréhension de `elements`.",
            bonne=2,
            categorie=LANGAGE,
            notion="compréhension",
        ),
        Correction(juste=False, bonne_reponse="ligne 2", explication="…"),
    )
    historique.enregistrer_passage(extrait)

    lues = Historique(chemin=chemin).entrees()
    _verifier(
        len(lues) == 2 and lues[0].issue == CARTE and lues[1].issue == PASSE,
        "une carte et un passage s'écrivent puis se relisent dans l'ordre",
    )
    _verifier(
        lues[0].ligne == 2,
        "pour une carte « repérer », c'est la ligne à trouver qui est enregistrée",
    )
    _verifier(
        not lues[0].juste and lues[0].notion == "compréhension",
        "une carte ratée est enregistrée comme ratée, avec sa notion",
    )


def main() -> int:
    verifier_serie()
    verifier_reussite()
    verifier_calendrier()
    verifier_historique_vide()
    verifier_passages()
    verifier_lecture_historique()
    verifier_ancien_fichier()
    verifier_ecriture()

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
