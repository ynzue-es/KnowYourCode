"""Les cartes, et leur correction.

Une carte est une question qui tient en un geste : quatre options, un clic sur
une ligne, un mot. Une série en compte trois ou quatre, toutes sur le même
extrait — on atterrit dans une fonction, on la creuse, on repart.

Le renversement par rapport à l'ancien exercice tient en une phrase :
l'utilisateur répond court, et c'est l'application qui explique long. Il n'y a
donc plus rien à faire juger par un modèle après coup. La correction est ici,
locale et instantanée ; le modèle n'intervient qu'avant, pour fabriquer les
cartes, et son texte est déjà écrit quand la question s'affiche.

`defauts` est la douane. Ce qui sort d'un modèle n'est pas de confiance :
un QCM à trois options, une explication qui ne parle d'aucune variable du
code, une bonne réponse hors bornes — tout cela arrive, et rien de tout cela
ne doit atteindre l'écran.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum, auto

from .modeles import Extrait
from .reperage import LANGAGE, notion_reconnue

# Trois ou quatre : assez pour creuser un extrait, assez peu pour qu'on
# recommence demain. Le générateur vise ce nombre, l'affichage se contente de
# ce qu'il reçoit.
CARTES_PAR_SERIE = 4

# Les garde-fous du texte. Le modèle, laissé libre, paraphrase la ligne et
# s'étale ; ces deux bornes suffisent à l'en empêcher.
LONGUEUR_QUESTION = 160
LONGUEUR_EXPLICATION = 480


class Forme(Enum):
    """Les cinq façons de poser une question, toutes en un geste."""

    QCM = auto()
    """Quatre options, une seule bonne."""

    REPERER = auto()
    """« Quelle ligne fait ceci ? » — on clique la ligne, sans rien taper."""

    PREDIRE = auto()
    """« Ça vaut quoi ? » — un mot, une valeur."""

    VRAI_FAUX = auto()
    """Deux options, deux secondes."""

    NOMMER = auto()
    """« Comment s'appelle ce que fait cette ligne ? » — le vocabulaire, seul
    bagage qui se transporte hors du projet."""


# Les formes où la réponse est le rang d'une option, par opposition à celles
# où l'on rend une ligne ou un mot.
FORMES_A_OPTIONS = frozenset({Forme.QCM, Forme.VRAI_FAUX})


@dataclass(frozen=True)
class Carte:
    """Une question, sa réponse, et ce qu'on en apprend.

    `ligne` désigne la ligne visée dans l'extrait, numérotée à partir de 1.
    Elle sert à surligner le code pendant la question — sauf pour `REPERER`,
    où la montrer donnerait la réponse : c'est justement ce qu'on demande de
    trouver.

    `attendu` liste les formes acceptées pour les réponses tapées. Elles sont
    fixées à la fabrication, ce qui permet de corriger sans modèle ; la
    comparaison est indulgente sur les accents, la casse et le pluriel.

    `explication` est le cœur. Un seul bloc de prose, montré que la réponse
    soit juste ou fausse, parce que c'est le cours et qu'il ne se donne pas
    seulement en cas d'erreur. Le pourquoi est dedans, pas dans une rubrique
    à part.
    """

    forme: Forme
    question: str
    explication: str
    ligne: int = 0
    options: tuple[str, ...] = ()
    bonne: int = 0
    """Rang de la bonne option, ou numéro de ligne attendu pour `REPERER`."""
    attendu: tuple[str, ...] = field(default_factory=tuple)
    categorie: str = LANGAGE
    notion: str | None = None


@dataclass(frozen=True)
class Serie:
    """Les cartes d'une même ouverture, toutes sur le même extrait."""

    extrait: Extrait
    cartes: tuple[Carte, ...]


@dataclass(frozen=True)
class Correction:
    """Ce qu'on affiche une fois la carte répondue."""

    juste: bool
    bonne_reponse: str
    """La bonne réponse en clair, à montrer quand on s'est trompé."""
    explication: str


def corriger(carte: Carte, reponse: str | int) -> Correction:
    """Corrige une réponse, sans réseau ni modèle.

    Une réponse illisible — un rang hors bornes, un mot vide — vaut une
    erreur et non une exception : on est dans une boucle d'apprentissage, pas
    dans un formulaire.
    """
    if carte.forme in FORMES_A_OPTIONS:
        juste = _rang(reponse) == carte.bonne
    elif carte.forme is Forme.REPERER:
        juste = _rang(reponse) == carte.bonne
    elif carte.forme is Forme.NOMMER and carte.notion is not None:
        # La notion connaît ses propres synonymes : `reperage` sait déjà que
        # « closure » vaut « fermeture », inutile de les recopier ici.
        juste = notion_reconnue(str(reponse), carte.notion) or _parmi(
            reponse, carte.attendu
        )
    else:
        juste = _parmi(reponse, carte.attendu)

    return Correction(
        juste=juste,
        bonne_reponse=bonne_reponse(carte),
        explication=carte.explication,
    )


def bonne_reponse(carte: Carte) -> str:
    """La bonne réponse en toutes lettres, pour l'afficher après coup."""
    if carte.forme in FORMES_A_OPTIONS:
        if 0 <= carte.bonne < len(carte.options):
            return carte.options[carte.bonne]
        return ""
    if carte.forme is Forme.REPERER:
        return f"ligne {carte.bonne}"
    if carte.notion is not None:
        return carte.notion
    return carte.attendu[0] if carte.attendu else ""


def _rang(reponse: str | int) -> int:
    try:
        return int(reponse)
    except (TypeError, ValueError):
        return -1


def _normaliser(texte: str) -> str:
    return re.sub(r"\s+", " ", str(texte).strip().lower())


def _parmi(reponse: str | int, acceptees: tuple[str, ...]) -> bool:
    if not acceptees:
        return False
    donnee = _normaliser(reponse)
    return bool(donnee) and donnee in {_normaliser(a) for a in acceptees}


# ---------------------------------------------------------------------------
# La douane
# ---------------------------------------------------------------------------

_IDENTIFIANT = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")

# Ces mots-là se retrouvent dans n'importe quel code : les compter comme un
# ancrage laisserait passer une explication générique.
_MOTS_PARTOUT = frozenset(
    {
        "and", "as", "async", "await", "break", "class", "const", "continue",
        "def", "default", "elif", "else", "except", "export", "false", "finally",
        "for", "from", "function", "global", "if", "import", "in", "is", "lambda",
        "let", "new", "none", "not", "null", "or", "pass", "raise", "return",
        "self", "true", "try", "typeof", "undefined", "var", "while", "with",
        "yield", "int", "str", "list", "dict", "set", "bool", "float", "this",
    }
)


def _identifiants(code: str) -> set[str]:
    return {
        mot for mot in _IDENTIFIANT.findall(code) if mot.lower() not in _MOTS_PARTOUT
    }


def defauts(carte: Carte, code: str) -> list[str]:
    """Rend ce qui empêche d'afficher cette carte. Vide, elle est bonne.

    Appelée sur tout ce qui sort du générateur, avant la mise en cache. Une
    carte fautive est jetée, pas rafistolée : on en refabrique une, ça coûte
    moins cher qu'une question fausse.
    """
    ennuis: list[str] = []
    lignes = code.splitlines()

    if not carte.question.strip():
        ennuis.append("question vide")
    elif len(carte.question) > LONGUEUR_QUESTION:
        ennuis.append("question trop longue")

    if not carte.explication.strip():
        ennuis.append("explication vide")
    elif len(carte.explication) > LONGUEUR_EXPLICATION:
        ennuis.append("explication trop longue")
    elif not _identifiants(carte.explication) & _identifiants(code):
        # La règle qui distingue ce produit d'un tutoriel : l'explication doit
        # parler de *ce* code. Si elle ne nomme aucune variable ni aucune
        # fonction du fichier, c'est du remplissage, et il s'en trouve mille
        # meilleurs en ligne.
        ennuis.append("explication qui ne cite rien du code")

    if carte.forme in FORMES_A_OPTIONS:
        attendues = 2 if carte.forme is Forme.VRAI_FAUX else 4
        if len(carte.options) != attendues:
            ennuis.append(f"{len(carte.options)} options au lieu de {attendues}")
        elif len({_normaliser(o) for o in carte.options}) != attendues:
            ennuis.append("deux options identiques")
        if not 0 <= carte.bonne < len(carte.options):
            ennuis.append("bonne réponse hors bornes")
        elif carte.forme is Forme.QCM and _trop_longue(carte):
            # Un distracteur bâclé est court, la bonne réponse est soignée et
            # longue : on répond juste sans lire le code. Le défaut est réel
            # et se mesure.
            ennuis.append("bonne réponse repérable à sa longueur")

    elif carte.forme is Forme.REPERER:
        if not 1 <= carte.bonne <= len(lignes):
            ennuis.append("ligne à trouver hors de l'extrait")
        if carte.ligne:
            ennuis.append("la ligne visée est montrée alors qu'il faut la trouver")

    else:
        if not carte.attendu and carte.notion is None:
            ennuis.append("aucune réponse acceptée")
        if not 1 <= carte.ligne <= len(lignes):
            ennuis.append("ligne visée hors de l'extrait")

    if carte.forme is Forme.NOMMER and carte.notion is None:
        ennuis.append("carte « nommer » sans notion à nommer")

    return ennuis


def _trop_longue(carte: Carte) -> bool:
    """Dit si la bonne option se repère à sa seule longueur."""
    bonne = len(carte.options[carte.bonne])
    autres = [len(o) for i, o in enumerate(carte.options) if i != carte.bonne]
    return bool(autres) and bonne > 2 * max(autres)
