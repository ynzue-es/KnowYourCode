"""Les cartes, et leur correction.

Une carte est une question qui tient en un clic : quatre options, ou vrai et
faux. Une série en compte trois ou quatre, toutes sur le même extrait — on
atterrit dans une fonction, on la creuse, on repart.

Rien ne se tape. On a essayé : faire écrire le nom d'une notion butait sur
« la diffusion » contre « diffusion », et une réponse juste comptée fausse
pour un article coûte plus de confiance qu'un mot deviné n'en rapporte. Une
question qu'on lit vraiment et qu'on tranche d'un clic apprend autant, et ne
punit personne pour sa frappe.

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
from dataclasses import dataclass
from enum import Enum, auto

from .modeles import Extrait
from .reperage import LANGAGE

# Trois ou quatre : assez pour creuser un extrait, assez peu pour qu'on
# recommence demain. Le générateur vise ce nombre, l'affichage se contente de
# ce qu'il reçoit.
CARTES_PAR_SERIE = 4

# Les garde-fous du texte. Le modèle, laissé libre, paraphrase la ligne et
# s'étale ; ces deux bornes suffisent à l'en empêcher.
LONGUEUR_QUESTION = 160
LONGUEUR_EXPLICATION = 480


class Forme(Enum):
    """Les deux façons de poser une question, toutes deux en un clic."""

    QCM = auto()
    """Quatre options, une seule bonne."""

    VRAI_FAUX = auto()
    """Deux options, deux secondes."""


@dataclass(frozen=True)
class Carte:
    """Une question, sa réponse, et ce qu'on en apprend.

    `ligne` désigne la ligne visée dans l'extrait, numérotée à partir de 1.
    Elle est surlignée pendant la question : c'est elle qu'on interroge, la
    cacher ne ferait qu'ajouter une devinette à une question qui n'en demande
    pas.

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
    """Rang de la bonne option dans `options`."""
    categorie: str = LANGAGE
    notion: str | None = None
    """Le sujet de la carte, quand il en porte un nom. Ne se tape plus, mais
    sert encore à mesurer sur quoi l'on bute d'une série à l'autre."""


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
    reponse_donnee: str = ""
    """Ce qui a été répondu. L'historique le garde : savoir *ce qu'on a cru*
    vaut mieux, pour réviser, que de savoir seulement qu'on s'est trompé."""


def corriger(carte: Carte, reponse: str | int) -> Correction:
    """Corrige une réponse, sans réseau ni modèle.

    Une réponse illisible — un rang hors bornes — vaut une erreur et non une
    exception : on est dans une boucle d'apprentissage, pas dans un formulaire.
    """
    # Le rang ou le libellé, indifféremment. Le panneau tient le texte du
    # bouton cliqué ; l'obliger à retrouver son rang pour le repasser ici
    # n'ajouterait qu'un endroit de plus où les deux peuvent se désaccorder.
    juste = _rang(reponse) == carte.bonne or _parmi(
        reponse, carte.options[carte.bonne : carte.bonne + 1]
    )

    return Correction(
        juste=juste,
        bonne_reponse=bonne_reponse(carte),
        explication=carte.explication,
        reponse_donnee=str(reponse),
    )


def bonne_reponse(carte: Carte) -> str:
    """La bonne réponse en toutes lettres, pour l'afficher après coup."""
    if 0 <= carte.bonne < len(carte.options):
        return carte.options[carte.bonne]
    return ""


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

    if not 1 <= carte.ligne <= len(lignes):
        ennuis.append("ligne visée hors de l'extrait")

    return ennuis


def _trop_longue(carte: Carte) -> bool:
    """Dit si la bonne option se repère à sa seule longueur."""
    bonne = len(carte.options[carte.bonne])
    autres = [len(o) for i, o in enumerate(carte.options) if i != carte.bonne]
    return bool(autres) and bonne > 2 * max(autres)
