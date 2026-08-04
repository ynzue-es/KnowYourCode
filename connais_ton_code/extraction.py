"""Repérage des fonctions dans un fichier source.

Deux stratégies, choisies pour leur coût : `ast` pour Python, qui donne un
résultat exact gratuitement, et un comptage d'accolades pour TypeScript, qui
évite d'embarquer un analyseur syntaxique complet pour un besoin qui se
contente d'à peu près.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass

LANGAGES = {".py": "python", ".ts": "typescript", ".tsx": "tsx"}


@dataclass(frozen=True)
class Fonction:
    """Une fonction repérée dans un fichier, avec son texte."""

    nom: str
    premiere_ligne: int
    code: str

    @property
    def nombre_de_lignes(self) -> int:
        return self.code.count("\n") + 1


# `function nom(`, avec ou sans export ni async.
_FONCTION_TS = re.compile(
    r"^[ \t]*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s*\*?\s*(\w+)"
)

# `const Nom = (...) =>`, la forme des composants et des hooks.
_FLECHE_TS = re.compile(
    r"^[ \t]*(?:export\s+)?(?:const|let)\s+(\w+)\s*(?::[^=]+?)?=\s*"
    r"(?:async\s*)?(?:\([^)]*\)|\w+)\s*(?::[^=]+?)?=>"
)


def fonctions(texte: str, langage: str) -> list[Fonction]:
    """Rend les fonctions du fichier, dans l'ordre où elles apparaissent."""
    if langage == "python":
        return _fonctions_python(texte)
    return _fonctions_typescript(texte)


def _fonctions_python(texte: str) -> list[Fonction]:
    try:
        arbre = ast.parse(texte)
    except (SyntaxError, ValueError, RecursionError):
        return []

    lignes = texte.splitlines()
    trouvees: list[Fonction] = []
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        fin = getattr(noeud, "end_lineno", None)
        if fin is None:
            continue
        trouvees.append(
            Fonction(
                nom=noeud.name,
                premiere_ligne=noeud.lineno,
                code="\n".join(lignes[noeud.lineno - 1 : fin]),
            )
        )
    trouvees.sort(key=lambda f: f.premiere_ligne)
    return trouvees


def _fonctions_typescript(texte: str) -> list[Fonction]:
    lignes = texte.splitlines()
    trouvees: list[Fonction] = []
    derniere_fin = -1

    for index, ligne in enumerate(lignes):
        # Une fonction imbriquée dans une autre est ignorée : elle sortirait
        # de son contexte et deviendrait incompréhensible.
        if index <= derniere_fin:
            continue

        correspondance = _FONCTION_TS.match(ligne) or _FLECHE_TS.match(ligne)
        if correspondance is None:
            continue

        fin = _fin_de_fonction(lignes, index)
        if fin is None:
            continue

        trouvees.append(
            Fonction(
                nom=correspondance.group(1),
                premiere_ligne=index + 1,
                code="\n".join(lignes[index : fin + 1]),
            )
        )
        derniere_fin = fin

    return trouvees


def _flux(lignes: list[str], depart: int):
    """Parcourt le code caractère par caractère, hors chaînes et commentaires.

    Sans ce filtrage, la moindre accolade dans un texte ou un commentaire
    ferait dérailler le comptage.
    """
    chaine: str | None = None
    commentaire = False

    for numero in range(depart, len(lignes)):
        ligne = lignes[numero]
        position = 0
        while position < len(ligne):
            caractere = ligne[position]
            suivant = ligne[position + 1] if position + 1 < len(ligne) else ""

            if commentaire:
                if caractere == "*" and suivant == "/":
                    commentaire = False
                    position += 1
            elif chaine is not None:
                if caractere == "\\":
                    position += 1
                elif caractere == chaine:
                    chaine = None
            elif caractere == "/" and suivant == "/":
                break
            elif caractere == "/" and suivant == "*":
                commentaire = True
                position += 1
            elif caractere in "\"'`":
                chaine = caractere
            else:
                yield numero, caractere

            position += 1


def _fin_de_fonction(lignes: list[str], depart: int) -> int | None:
    """Rend la ligne où se referme la fonction commencée à `depart`.

    La liste des paramètres est franchie avant de chercher le corps : sans
    ça, un paramètre déstructuré comme `function Composant({ enfants }: Props)`
    fait prendre l'accolade de la déstructuration pour celle du corps, et la
    fonction s'arrête avant d'avoir commencé.
    """
    flux = _flux(lignes, depart)

    profondeur = 0
    parentheses_vues = False
    precedent = ""
    fleche = False
    corps_commence = False

    for numero, caractere in flux:
        if caractere == "(":
            profondeur += 1
            parentheses_vues = True
        elif caractere == ")":
            profondeur -= 1
            if parentheses_vues and profondeur == 0:
                break
        elif caractere == ">" and precedent == "=":
            fleche = True
        elif caractere == "{" and not parentheses_vues and fleche:
            # `const f = x => { ... }` : un seul paramètre, sans parenthèses.
            corps_commence = True
            profondeur = 1
            break
        precedent = caractere

    if not corps_commence:
        profondeur = 0
        for numero, caractere in flux:
            if caractere == "{":
                profondeur = 1
                corps_commence = True
                break
            if caractere == ";":
                # Corps concis d'une fonction fléchée : il n'y a pas de bloc.
                return numero

    if not corps_commence:
        return None

    for numero, caractere in flux:
        if caractere == "{":
            profondeur += 1
        elif caractere == "}":
            profondeur -= 1
            if profondeur == 0:
                return numero

    return None
