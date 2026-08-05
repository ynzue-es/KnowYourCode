"""Repérage des lignes qui méritent une question.

Tout le reste en dépend. Une carte posée sur `zone = ZoneInfo(fuseau)`
n'apprend rien à personne ; la même carte posée sur une valeur par défaut
mutable ou sur un tableau de dépendances vaut une leçon. Le modèle qui
rédigera les cartes ne choisit donc pas son sujet : il reçoit une ligne déjà
désignée ici, et se contente d'écrire autour.

Le repérage est entièrement local — `ast` pour Python, des motifs ligne à
ligne pour TypeScript. C'est délibéré : il tourne à chaque ouverture, il doit
être gratuit et instantané, et surtout il ne doit rien inventer. Une notion
signalée ici est présente dans le code, sans discussion possible.

C'est aussi ce qui rend le point sécurité honnête. Il n'est pas réclamé au
modèle à chaque manche — auquel cas il en fabriquerait — il n'apparaît que
lorsqu'un motif dangereux est réellement là.
"""

from __future__ import annotations

import ast
import re
import textwrap
import unicodedata
from dataclasses import dataclass

# Les trois familles de repères. La catégorie ne sert pas qu'à ranger : elle
# décide du ton de la carte, et « sécurité » est la seule qui ait le droit
# d'affirmer que quelque chose est dangereux.
LANGAGE = "langage"
ROBUSTESSE = "robustesse"
SECURITE = "securite"

# Les poids ordonnent le tirage. Un piège l'emporte sur une notion, une notion
# sur une tournure courante : à extrait égal, on pose la question qui apprend
# le plus. La sécurité passe devant tout le monde, parce qu'elle est rare et
# qu'on ne peut pas se permettre de la manquer quand elle se présente.
POIDS_SECURITE = 90
POIDS_PIEGE = 75
POIDS_NOTION = 55
POIDS_COURANT = 30


@dataclass(frozen=True)
class Repere:
    """Une ligne intéressante, et ce qui la rend intéressante.

    `ligne` est numérotée à partir de 1 dans l'extrait affiché, pas dans le
    fichier d'origine : c'est ce que l'utilisateur a sous les yeux.

    `notion` est le mot à faire deviner — « fermeture », « décorateur ». Il
    vaut `None` quand la ligne mérite une question sans porter de nom
    enseignable : `functools.wraps` s'explique très bien, mais ne se devine
    pas en un mot, et une carte « nommez la notion » y serait injuste.

    `intitule` n'est pas montré à l'utilisateur. C'est la consigne donnée au
    générateur : ce qu'il y a à voir sur cette ligne, en une phrase, pour
    qu'il rédige la carte sans avoir à deviner de quoi on parle.
    """

    ligne: int
    intitule: str
    categorie: str
    poids: int
    notion: str | None = None


# ---------------------------------------------------------------------------
# Le vocabulaire
# ---------------------------------------------------------------------------

# Les formes acceptées quand on demande de nommer une notion. L'anglais y
# figure parce que c'est le mot que tout le monde a en tête — refuser
# « closure » à quelqu'un qui a compris la fermeture serait une brimade, pas
# une correction. La comparaison se fait sans accents ni casse : ces formes
# n'ont pas besoin d'être écrites deux fois.
NOTIONS: dict[str, tuple[str, ...]] = {
    "fermeture": ("closure", "cloture"),
    "décorateur": ("decorator",),
    "compréhension": ("comprehension de liste", "list comprehension"),
    "générateur": ("generator", "iterateur paresseux"),
    "gestionnaire de contexte": ("context manager", "with"),
    "déballage": ("unpacking", "desempaquetage", "splat"),
    "destructuration": ("destructuring", "deconstruction"),
    "court-circuit": ("evaluation paresseuse", "short circuit"),
    "coercition": ("conversion implicite", "coercion"),
    "mémoïsation": ("memoization", "mise en cache", "cache"),
    "effet de bord": ("side effect",),
    "récursion": ("recursion", "appel recursif"),
    "tranche": ("slice", "slicing", "decoupage"),
    "expression ternaire": ("ternaire", "operateur ternaire"),
    "morse": ("walrus", "operateur morse", "affectation dans l'expression"),
    "chaînage optionnel": ("optional chaining", "chainage sur"),
    "fusion nulle": ("nullish coalescing", "coalescence nulle"),
    "diffusion": ("spread", "operateur de diffusion", "etalement"),
    "portée tardive": ("late binding", "capture tardive", "liaison tardive"),
    "identité": ("comparaison d'identite", "identity"),
    "propagation": ("propagation d'exception", "remontee", "bubbling"),
}


def _normaliser(mot: str) -> str:
    """Réduit un mot à ce qui compte pour le comparer.

    Sans accents, sans casse, sans ponctuation, sans pluriel : quelqu'un qui
    tape « Closures » a la bonne réponse et ne doit pas être recalé pour un
    « s ». On ne cherche pas à noter l'orthographe.
    """
    sans_accent = unicodedata.normalize("NFD", mot.strip().lower())
    sans_accent = "".join(c for c in sans_accent if unicodedata.category(c) != "Mn")
    nettoye = re.sub(r"[^a-z0-9 ]+", " ", sans_accent)
    nettoye = re.sub(r"\s+", " ", nettoye).strip()
    return nettoye[:-1] if nettoye.endswith("s") and len(nettoye) > 3 else nettoye


def notion_reconnue(saisie: str, notion: str) -> bool:
    """Dit si la saisie désigne bien la notion attendue."""
    if not saisie.strip():
        return False
    attendues = {_normaliser(notion)}
    attendues.update(_normaliser(forme) for forme in NOTIONS.get(notion, ()))
    return _normaliser(saisie) in attendues


# ---------------------------------------------------------------------------
# Entrée
# ---------------------------------------------------------------------------


def reperer(code: str, langage: str) -> list[Repere]:
    """Rend les lignes dignes d'une question, la plus prometteuse en tête.

    Une ligne au plus par repère : deux notions sur la même ligne rendraient
    la question ambiguë — « que fait cette ligne ? » n'a pas de bonne réponse
    quand il s'y passe deux choses. On garde la plus lourde et on laisse
    l'autre.
    """
    trouves = (
        _reperer_python(code) if langage == "python" else _reperer_typescript(code)
    )

    meilleurs: dict[int, Repere] = {}
    for repere in trouves:
        if repere.ligne < 1:
            continue
        ancien = meilleurs.get(repere.ligne)
        if ancien is None or repere.poids > ancien.poids:
            meilleurs[repere.ligne] = repere

    return sorted(meilleurs.values(), key=lambda r: (-r.poids, r.ligne))


# ---------------------------------------------------------------------------
# Python
# ---------------------------------------------------------------------------


def _arbre(code: str) -> ast.AST | None:
    """Analyse l'extrait, indenté ou non.

    Une méthode arrachée à sa classe arrive décalée de quatre espaces et
    `ast.parse` la refuse. On retente donc désindenté, ce qui ne change aucun
    numéro de ligne — `dedent` rogne les colonnes, jamais les lignes.
    """
    for source in (code, textwrap.dedent(code)):
        try:
            return ast.parse(source)
        except (SyntaxError, ValueError, RecursionError):
            continue
    return None


_FONCTIONS = (ast.FunctionDef, ast.AsyncFunctionDef)


def _parcourir(racine: ast.AST):
    """Comme `ast.walk`, mais sans entrer dans les fonctions imbriquées.

    Ce qui se passe dans une fonction interne appartient à cette fonction :
    l'y laisser évite de reprocher à l'enveloppe les variables de l'enveloppée.
    """
    for enfant in ast.iter_child_nodes(racine):
        yield enfant
        if not isinstance(enfant, (*_FONCTIONS, ast.Lambda)):
            yield from _parcourir(enfant)


def _noms_lies(fonction: ast.AST) -> set[str]:
    """Les noms que cette fonction crée elle-même : paramètres et affectations."""
    lies: set[str] = set()

    arguments = getattr(fonction, "args", None)
    if arguments is not None:
        for groupe in (
            arguments.posonlyargs,
            arguments.args,
            arguments.kwonlyargs,
        ):
            lies.update(a.arg for a in groupe)
        for special in (arguments.vararg, arguments.kwarg):
            if special is not None:
                lies.add(special.arg)

    for noeud in _parcourir(fonction):
        if isinstance(noeud, ast.Name) and isinstance(noeud.ctx, ast.Store):
            lies.add(noeud.id)
        elif isinstance(noeud, (*_FONCTIONS, ast.ClassDef)):
            lies.add(noeud.name)
    return lies


def _noms_charges(noeud: ast.AST) -> set[str]:
    """Les noms que ce sous-arbre lit, sans distinguer d'où ils viennent."""
    return {
        enfant.id
        for enfant in ast.walk(noeud)
        if isinstance(enfant, ast.Name) and isinstance(enfant.ctx, ast.Load)
    }


def _appele(noeud: ast.Call) -> str:
    """Le nom de ce qui est appelé, pointé si c'est un attribut."""
    cible = noeud.func
    morceaux: list[str] = []
    while isinstance(cible, ast.Attribute):
        morceaux.append(cible.attr)
        cible = cible.value
    if isinstance(cible, ast.Name):
        morceaux.append(cible.id)
    return ".".join(reversed(morceaux))


def _mot_cle(noeud: ast.Call, nom: str) -> ast.expr | None:
    for argument in noeud.keywords:
        if argument.arg == nom:
            return argument.value
    return None


def _est_vrai(noeud: ast.expr | None) -> bool:
    return isinstance(noeud, ast.Constant) and noeud.value is True


def _vaut_faux(noeud: ast.expr | None) -> bool:
    return isinstance(noeud, ast.Constant) and noeud.value is False


def _reperer_python(code: str) -> list[Repere]:
    racine = _arbre(code)
    if racine is None:
        return []

    lignes = code.splitlines()
    trouves: list[Repere] = []
    trouves += _python_signature(racine)
    trouves += _python_flux(racine, lignes)
    trouves += _python_expressions(racine)
    trouves += _python_repli(racine)
    trouves += _python_fermetures(racine)
    trouves += _python_securite(racine)
    return trouves


def _python_signature(racine: ast.AST) -> list[Repere]:
    trouves: list[Repere] = []

    for noeud in ast.walk(racine):
        if not isinstance(noeud, _FONCTIONS):
            continue

        for decorateur in noeud.decorator_list:
            cible = decorateur.func if isinstance(decorateur, ast.Call) else decorateur
            nom = (
                _appele(decorateur)
                if isinstance(decorateur, ast.Call)
                else getattr(cible, "id", getattr(cible, "attr", ""))
            )
            if nom.endswith("wraps"):
                trouves.append(
                    Repere(
                        ligne=decorateur.lineno,
                        intitule=(
                            "`wraps` recopie le nom, la docstring et le module de "
                            "la fonction d'origine sur l'enveloppe ; sans lui "
                            "l'enveloppe se présente sous son propre nom"
                        ),
                        categorie=LANGAGE,
                        poids=POIDS_NOTION,
                    )
                )
                continue
            trouves.append(
                Repere(
                    ligne=decorateur.lineno,
                    intitule=(
                        f"la fonction est enveloppée par `{nom}` avant même "
                        "d'être appelée"
                    ),
                    categorie=LANGAGE,
                    poids=POIDS_NOTION,
                    notion="décorateur",
                )
            )

        # Une valeur par défaut mutable est construite une fois, à la
        # définition, et survit d'un appel à l'autre. C'est le piège le plus
        # cher de Python et il tient sur une ligne.
        for defaut in [*noeud.args.defaults, *noeud.args.kw_defaults]:
            if isinstance(defaut, (ast.List, ast.Dict, ast.Set)):
                trouves.append(
                    Repere(
                        ligne=defaut.lineno,
                        intitule=(
                            "la valeur par défaut est mutable : elle est créée "
                            "une seule fois et partagée par tous les appels"
                        ),
                        categorie=ROBUSTESSE,
                        poids=POIDS_PIEGE,
                    )
                )
            elif isinstance(defaut, ast.Call) and _appele(defaut) in {
                "list",
                "dict",
                "set",
            }:
                trouves.append(
                    Repere(
                        ligne=defaut.lineno,
                        intitule=(
                            "la valeur par défaut est construite à la définition, "
                            "pas à chaque appel"
                        ),
                        categorie=ROBUSTESSE,
                        poids=POIDS_PIEGE,
                    )
                )

        if noeud.args.vararg is not None or noeud.args.kwarg is not None:
            trouves.append(
                Repere(
                    ligne=noeud.lineno,
                    intitule=(
                        "la signature ramasse un nombre libre d'arguments et les "
                        "range dans un tuple ou un dictionnaire"
                    ),
                    categorie=LANGAGE,
                    poids=POIDS_COURANT,
                    notion="déballage",
                )
            )

    for noeud in ast.walk(racine):
        if isinstance(noeud, (ast.Yield, ast.YieldFrom)):
            trouves.append(
                Repere(
                    ligne=noeud.lineno,
                    intitule=(
                        "la fonction ne rend pas une valeur mais se suspend : "
                        "rien ne s'exécute avant qu'on itère dessus"
                    ),
                    categorie=LANGAGE,
                    poids=POIDS_NOTION,
                    notion="générateur",
                )
            )

    return trouves


def _mot_clef_avant(lignes: list[str], premier_du_bloc: int, mot: str) -> int:
    """Remonte du premier énoncé d'un bloc jusqu'au mot-clé qui l'introduit.

    `ast` ne donne aucune position pour `finally` ni pour le `else` d'une
    boucle : ces mots ne sont pas des nœuds. On ne peut pas non plus se
    contenter de la ligne juste au-dessus, qu'un commentaire ou une ligne vide
    suffit à occuper. Faute de trouver, on montre le premier énoncé du bloc —
    ce n'est pas la ligne visée, mais elle existe.
    """
    for numero in range(min(premier_du_bloc, len(lignes)), 0, -1):
        if lignes[numero - 1].strip().startswith(mot):
            return numero
    return premier_du_bloc


def _python_flux(racine: ast.AST, lignes: list[str]) -> list[Repere]:
    trouves: list[Repere] = []

    for noeud in ast.walk(racine):
        if isinstance(noeud, ast.ExceptHandler):
            avale = all(isinstance(e, ast.Pass) for e in noeud.body)
            if noeud.type is None:
                trouves.append(
                    Repere(
                        ligne=noeud.lineno,
                        intitule=(
                            "la clause n'écrit aucun type : elle attrape tout, "
                            "y compris le Ctrl-C et les erreurs de programmation"
                        ),
                        categorie=ROBUSTESSE,
                        poids=POIDS_PIEGE,
                    )
                )
            elif avale:
                trouves.append(
                    Repere(
                        ligne=noeud.lineno,
                        intitule=(
                            "l'exception est attrapée puis ignorée : l'erreur "
                            "disparaît sans laisser de trace"
                        ),
                        categorie=ROBUSTESSE,
                        poids=POIDS_PIEGE,
                    )
                )
            else:
                trouves.append(
                    Repere(
                        ligne=noeud.lineno,
                        intitule=(
                            "cette clause décide de ce qui est rattrapé et de ce "
                            "qui continue de remonter à l'appelant"
                        ),
                        categorie=ROBUSTESSE,
                        poids=POIDS_COURANT,
                        notion="propagation",
                    )
                )

        elif isinstance(noeud, (ast.With, ast.AsyncWith)):
            trouves.append(
                Repere(
                    ligne=noeud.lineno,
                    intitule=(
                        "la ressource est libérée à la sortie du bloc, y compris "
                        "si une exception le traverse"
                    ),
                    categorie=LANGAGE,
                    poids=POIDS_NOTION,
                    notion="gestionnaire de contexte",
                )
            )

        elif isinstance(noeud, ast.Try) and noeud.finalbody:
            trouves.append(
                Repere(
                    ligne=_mot_clef_avant(
                        lignes, noeud.finalbody[0].lineno, "finally"
                    ),
                    intitule=(
                        "ce bloc s'exécute quoi qu'il arrive, y compris après un "
                        "`return` ou une exception non rattrapée"
                    ),
                    categorie=ROBUSTESSE,
                    poids=POIDS_NOTION,
                )
            )

        elif isinstance(noeud, (ast.For, ast.While)) and noeud.orelse:
            trouves.append(
                Repere(
                    ligne=_mot_clef_avant(lignes, noeud.orelse[0].lineno, "else"),
                    intitule=(
                        "le `else` d'une boucle ne s'exécute que si elle s'est "
                        "terminée sans `break` — presque personne ne le sait"
                    ),
                    categorie=LANGAGE,
                    poids=POIDS_PIEGE,
                )
            )

        elif isinstance(noeud, ast.Raise) and noeud.cause is not None:
            trouves.append(
                Repere(
                    ligne=noeud.lineno,
                    intitule=(
                        "`from` accroche la cause d'origine à la nouvelle "
                        "exception : la trace garde les deux"
                    ),
                    categorie=ROBUSTESSE,
                    poids=POIDS_NOTION,
                )
            )

        elif isinstance(noeud, (ast.Global, ast.Nonlocal)):
            trouves.append(
                Repere(
                    ligne=noeud.lineno,
                    intitule=(
                        "sans cette déclaration, l'affectation qui suit créerait "
                        "une variable locale au lieu de modifier celle du dessus"
                    ),
                    categorie=LANGAGE,
                    poids=POIDS_NOTION,
                )
            )

    return trouves


def _python_expressions(racine: ast.AST) -> list[Repere]:
    trouves: list[Repere] = []

    for noeud in ast.walk(racine):
        if isinstance(noeud, (ast.ListComp, ast.SetComp, ast.DictComp)):
            filtree = any(g.ifs for g in noeud.generators)
            trouves.append(
                Repere(
                    ligne=noeud.lineno,
                    intitule=(
                        "la boucle et le filtre tiennent dans l'expression qui "
                        "construit la collection"
                        if filtree
                        else "la collection est construite en une expression"
                    ),
                    categorie=LANGAGE,
                    poids=POIDS_NOTION if filtree else POIDS_COURANT,
                    notion="compréhension",
                )
            )

        elif isinstance(noeud, ast.GeneratorExp):
            trouves.append(
                Repere(
                    ligne=noeud.lineno,
                    intitule=(
                        "rien n'est construit en mémoire : les valeurs sont "
                        "produites au fur et à mesure de la consommation"
                    ),
                    categorie=LANGAGE,
                    poids=POIDS_NOTION,
                    notion="générateur",
                )
            )

        elif isinstance(noeud, ast.NamedExpr):
            trouves.append(
                Repere(
                    ligne=noeud.lineno,
                    intitule=(
                        "l'affectation a lieu à l'intérieur de la condition, et "
                        "la valeur affectée sert aussitôt"
                    ),
                    categorie=LANGAGE,
                    poids=POIDS_NOTION,
                    notion="morse",
                )
            )

        elif isinstance(noeud, ast.IfExp):
            trouves.append(
                Repere(
                    ligne=noeud.lineno,
                    intitule="la condition est écrite dans l'expression elle-même",
                    categorie=LANGAGE,
                    poids=POIDS_COURANT,
                    notion="expression ternaire",
                )
            )

        elif isinstance(noeud, ast.Subscript) and isinstance(noeud.slice, ast.Slice):
            tranche = noeud.slice
            interessante = tranche.step is not None or any(
                isinstance(b, ast.UnaryOp) and isinstance(b.op, ast.USub)
                for b in (tranche.lower, tranche.upper)
                if b is not None
            )
            trouves.append(
                Repere(
                    ligne=noeud.lineno,
                    intitule=(
                        "les bornes de la tranche ne se lisent pas de gauche à "
                        "droite : un pas ou un indice négatif change tout"
                        if interessante
                        else "la tranche produit une copie, pas une vue"
                    ),
                    categorie=LANGAGE,
                    poids=POIDS_NOTION if interessante else POIDS_COURANT,
                    notion="tranche",
                )
            )

        elif isinstance(noeud, ast.Compare):
            for operateur, droite in zip(noeud.ops, noeud.comparators):
                # `x is None` est la façon normale d'écrire le test : il n'y a
                # rien à y apprendre, et le signaler noierait tout le reste.
                # Sur un littéral, en revanche, `is` ne marche que par
                # accident — c'est là qu'il y a une leçon.
                if isinstance(operateur, (ast.Is, ast.IsNot)):
                    if isinstance(droite, ast.Constant) and droite.value is not None:
                        trouves.append(
                            Repere(
                                ligne=noeud.lineno,
                                intitule=(
                                    "`is` compare l'emplacement en mémoire, pas la "
                                    "valeur : sur un littéral, ça marche par accident"
                                ),
                                categorie=ROBUSTESSE,
                                poids=POIDS_PIEGE,
                                notion="identité",
                            )
                        )
                elif (
                    isinstance(operateur, (ast.Eq, ast.NotEq))
                    and isinstance(droite, ast.Constant)
                    and droite.value is None
                ):
                    trouves.append(
                        Repere(
                            ligne=noeud.lineno,
                            intitule=(
                                "`== None` passe par la méthode de comparaison de "
                                "l'objet, que celui-ci peut redéfinir"
                            ),
                            categorie=ROBUSTESSE,
                            poids=POIDS_PIEGE,
                            notion="identité",
                        )
                    )

        elif isinstance(noeud, ast.Call):
            nom = _appele(noeud)
            if nom.endswith("sort") and _mot_cle(noeud, "key") is not None:
                trouves.append(
                    Repere(
                        ligne=noeud.lineno,
                        intitule=(
                            "`key` est appelée une fois par élément et c'est son "
                            "résultat qu'on compare, pas l'élément"
                        ),
                        categorie=LANGAGE,
                        poids=POIDS_NOTION,
                    )
                )
            elif nom in {"defaultdict", "collections.defaultdict"}:
                trouves.append(
                    Repere(
                        ligne=noeud.lineno,
                        intitule=(
                            "la fabrique est appelée à la première lecture d'une "
                            "clé absente, ce qui crée l'entrée au passage"
                        ),
                        categorie=LANGAGE,
                        poids=POIDS_NOTION,
                    )
                )

    return trouves


def _python_repli(racine: ast.AST) -> list[Repere]:
    """Le `or` employé comme valeur de repli, et lui seul.

    Distinction qui n'est pas cosmétique : dans `if a or b:` il n'y a aucune
    leçon, c'est une condition ordinaire. Dans `nom = saisie or "anonyme"`, il
    y en a une — le repli se déclenche sur la chaîne vide, sur `0` et sur la
    liste vide, pas seulement sur `None`. Signaler les deux reviendrait à
    expliquer un piège là où il n'y en a pas, et le repérage perdrait le seul
    avantage qu'il ait sur un modèle : ne dire que des choses vraies.
    """
    trouves: list[Repere] = []

    def examiner(valeur: ast.expr | None) -> None:
        if isinstance(valeur, ast.BoolOp) and isinstance(valeur.op, ast.Or):
            trouves.append(
                Repere(
                    ligne=valeur.lineno,
                    intitule=(
                        "le `or` sert de valeur de repli, et il se déclenche sur "
                        "tout ce qui est faux — pas seulement sur `None`"
                    ),
                    categorie=ROBUSTESSE,
                    poids=POIDS_PIEGE,
                    notion="court-circuit",
                )
            )

    for noeud in ast.walk(racine):
        if isinstance(noeud, (ast.Assign, ast.AnnAssign, ast.Return)):
            examiner(noeud.value)
        elif isinstance(noeud, _FONCTIONS):
            for defaut in [*noeud.args.defaults, *noeud.args.kw_defaults]:
                examiner(defaut)

    return trouves


def _python_fermetures(racine: ast.AST) -> list[Repere]:
    """Fermetures et capture tardive.

    Les deux notions se tiennent : la fermeture capture la variable, pas sa
    valeur, et c'est précisément ce qui rend la capture dans une boucle
    surprenante. Autant les repérer au même endroit.
    """
    trouves: list[Repere] = []

    for exterieure in ast.walk(racine):
        if not isinstance(exterieure, _FONCTIONS):
            continue

        disponibles = _noms_lies(exterieure)
        for interieure in _parcourir(exterieure):
            if not isinstance(interieure, (*_FONCTIONS, ast.Lambda)):
                continue
            empruntes = (
                _noms_charges(interieure) - _noms_lies(interieure)
            ) & disponibles
            if empruntes:
                trouves.append(
                    Repere(
                        ligne=interieure.lineno,
                        intitule=(
                            "la fonction interne garde l'accès à "
                            f"`{sorted(empruntes)[0]}` après le retour de celle "
                            "qui l'entoure"
                        ),
                        categorie=LANGAGE,
                        poids=POIDS_NOTION,
                        notion="fermeture",
                    )
                )

    for boucle in ast.walk(racine):
        if not isinstance(boucle, (ast.For, ast.AsyncFor)):
            continue
        cible = {
            n.id
            for n in ast.walk(boucle.target)
            if isinstance(n, ast.Name)
        }
        for corps in boucle.body:
            for noeud in ast.walk(corps):
                if not isinstance(noeud, (*_FONCTIONS, ast.Lambda)):
                    continue
                if _noms_charges(noeud) & cible:
                    trouves.append(
                        Repere(
                            ligne=noeud.lineno,
                            intitule=(
                                "la variable de boucle est capturée, pas sa "
                                "valeur : toutes les fonctions créées ici "
                                "verront la dernière"
                            ),
                            categorie=ROBUSTESSE,
                            poids=POIDS_PIEGE,
                            notion="portée tardive",
                        )
                    )

    return trouves


# Ce qui est réellement dangereux, et ce qu'il faut en dire. La liste est
# courte exprès : chaque entrée doit tenir devant un développeur qui demande
# « et alors ? ». Un motif qui ne mène qu'à « c'est une mauvaise pratique »
# n'a rien à faire ici.
_APPELS_SENSIBLES: dict[str, str] = {
    "eval": "le contenu de la chaîne est exécuté comme du code",
    "exec": "le contenu de la chaîne est exécuté comme du code",
    "os.system": "la commande passe par un shell, qui interprète `;` et `|`",
    "pickle.load": "désérialiser du pickle exécute du code arbitraire",
    "pickle.loads": "désérialiser du pickle exécute du code arbitraire",
    "yaml.load": "sans `Loader=SafeLoader`, le YAML peut instancier des objets",
    "hashlib.md5": "MD5 est cassé : il ne protège plus rien",
    "hashlib.sha1": "SHA-1 est cassé : il ne protège plus rien",
}


def _python_securite(racine: ast.AST) -> list[Repere]:
    trouves: list[Repere] = []

    for noeud in ast.walk(racine):
        if not isinstance(noeud, ast.Call):
            continue
        nom = _appele(noeud)

        raison = _APPELS_SENSIBLES.get(nom)
        if raison is not None:
            trouves.append(
                Repere(
                    ligne=noeud.lineno,
                    intitule=raison,
                    categorie=SECURITE,
                    poids=POIDS_SECURITE,
                )
            )
            continue

        if nom.startswith("subprocess.") and _est_vrai(_mot_cle(noeud, "shell")):
            trouves.append(
                Repere(
                    ligne=noeud.lineno,
                    intitule=(
                        "`shell=True` fait passer la commande par un shell : tout "
                        "ce qui vient d'ailleurs peut y glisser une autre commande"
                    ),
                    categorie=SECURITE,
                    poids=POIDS_SECURITE,
                )
            )

        elif _vaut_faux(_mot_cle(noeud, "verify")):
            trouves.append(
                Repere(
                    ligne=noeud.lineno,
                    intitule=(
                        "le certificat du serveur n'est plus vérifié : n'importe "
                        "qui sur le trajet peut se faire passer pour lui"
                    ),
                    categorie=SECURITE,
                    poids=POIDS_SECURITE,
                )
            )

        # Une requête sans délai peut attendre indéfiniment. Ce n'est pas une
        # faille, c'est un blocage — mais c'est de la même famille : ce qui
        # vient du réseau n'est pas de confiance, pas même sa lenteur.
        elif nom in {
            "urlopen",
            "urllib.request.urlopen",
            "requests.get",
            "requests.post",
            "socket.create_connection",
        } and _mot_cle(noeud, "timeout") is None:
            trouves.append(
                Repere(
                    ligne=noeud.lineno,
                    intitule=(
                        "sans `timeout`, l'appel peut attendre sans fin et geler "
                        "le fil qui l'exécute"
                    ),
                    categorie=ROBUSTESSE,
                    poids=POIDS_PIEGE,
                )
            )

        # Du SQL assemblé à la main : le seul motif où la f-string est un
        # danger et pas une commodité.
        elif nom.endswith(("execute", "executemany")) and noeud.args:
            requete = noeud.args[0]
            assemblee = isinstance(requete, ast.JoinedStr) or (
                isinstance(requete, ast.BinOp)
                and isinstance(requete.op, (ast.Add, ast.Mod))
            )
            if assemblee:
                trouves.append(
                    Repere(
                        ligne=noeud.lineno,
                        intitule=(
                            "la requête est assemblée par concaténation : la "
                            "valeur insérée peut refermer la chaîne et écrire "
                            "son propre SQL"
                        ),
                        categorie=SECURITE,
                        poids=POIDS_SECURITE,
                    )
                )

    for noeud in ast.walk(racine):
        if isinstance(noeud, ast.Assert):
            trouves.append(
                Repere(
                    ligne=noeud.lineno,
                    intitule=(
                        "les `assert` disparaissent quand Python tourne avec "
                        "`-O` : une vérification qui compte ne peut pas reposer "
                        "dessus"
                    ),
                    categorie=SECURITE,
                    poids=POIDS_SECURITE,
                )
            )

    return trouves


# ---------------------------------------------------------------------------
# TypeScript
# ---------------------------------------------------------------------------

# Faute d'analyseur syntaxique, on lit ligne à ligne. C'est le même parti pris
# que dans `extraction` : embarquer un vrai analyseur TypeScript coûterait
# infiniment plus cher que ce que la précision gagnée rapporterait. Un motif
# qui rate de temps en temps ne fait perdre qu'une carte.
_MOTIFS_TS: tuple[tuple[re.Pattern[str], str, str, int, str | None], ...] = (
    (
        re.compile(r"dangerouslySetInnerHTML"),
        "le HTML est injecté sans être échappé : ce qui vient d'ailleurs "
        "s'exécute dans la page",
        SECURITE,
        POIDS_SECURITE,
        None,
    ),
    (
        re.compile(r"\.innerHTML\s*="),
        "affecter `innerHTML` interprète le texte comme du balisage",
        SECURITE,
        POIDS_SECURITE,
        None,
    ),
    (
        re.compile(r"\beval\s*\(|new\s+Function\s*\("),
        "la chaîne est exécutée comme du code",
        SECURITE,
        POIDS_SECURITE,
        None,
    ),
    (
        re.compile(r'target\s*=\s*[{"\']?_blank'),
        "sans `rel=\"noreferrer\"`, la page ouverte garde une poignée sur "
        "celle qui l'a ouverte",
        SECURITE,
        POIDS_SECURITE,
        None,
    ),
    (
        re.compile(
            r"localStorage\.setItem\s*\(\s*['\"][^'\"]*"
            r"(token|jwt|secret|password|mot_de_passe)",
            re.IGNORECASE,
        ),
        "un secret dans `localStorage` est lisible par n'importe quel script "
        "de la page",
        SECURITE,
        POIDS_SECURITE,
        None,
    ),
    (
        re.compile(r"key\s*=\s*\{\s*(index|i|idx)\s*\}"),
        "la clé est la position dans la liste : si l'ordre change, React "
        "recycle le mauvais élément et son état suit",
        ROBUSTESSE,
        POIDS_PIEGE,
        None,
    ),
    (
        re.compile(r"^\s*\}?\s*,\s*\[[^\]]*\]\s*\)\s*;?\s*$"),
        "le tableau liste ce que l'effet lit à l'extérieur ; React compare "
        "ces valeurs d'un rendu au suivant pour décider de le rejouer",
        LANGAGE,
        POIDS_PIEGE,
        None,
    ),
    (
        re.compile(r"^\s*return\s*\(\s*\)\s*=>"),
        "ce retour est la fonction de nettoyage : React l'appelle avant de "
        "rejouer l'effet et au démontage",
        ROBUSTESSE,
        POIDS_PIEGE,
        None,
    ),
    (
        re.compile(r"\bset[A-Z]\w*\(\s*\(?\s*\w+\s*\)?\s*=>"),
        "la mise à jour part de l'état précédent au lieu de la valeur "
        "capturée au rendu",
        ROBUSTESSE,
        POIDS_PIEGE,
        None,
    ),
    (
        re.compile(r"\buseRef\s*\("),
        "la valeur survit aux rendus sans en déclencher un seul quand elle "
        "change",
        LANGAGE,
        POIDS_NOTION,
        None,
    ),
    (
        re.compile(r"\buseMemo\s*\(|\buseCallback\s*\("),
        "le résultat est conservé tant que les dépendances ne bougent pas",
        LANGAGE,
        POIDS_NOTION,
        "mémoïsation",
    ),
    (
        re.compile(r"\{\s*[\w.]+\s*&&\s*[<(]"),
        "un `&&` dans le JSX affiche `0` au lieu de rien quand la valeur de "
        "gauche est le nombre zéro",
        ROBUSTESSE,
        POIDS_PIEGE,
        "court-circuit",
    ),
    (
        re.compile(r"[^=!<>]==[^=]"),
        "le double égal convertit avant de comparer, là où le triple égal "
        "refuse les types différents",
        ROBUSTESSE,
        POIDS_PIEGE,
        "coercition",
    ),
    (
        re.compile(r"\?\?"),
        "le repli ne se déclenche que sur `null` et `undefined`, pas sur `0` "
        "ni sur la chaîne vide",
        LANGAGE,
        POIDS_NOTION,
        "fusion nulle",
    ),
    (
        re.compile(r"\w\?\.\w"),
        "la chaîne s'interrompt et rend `undefined` au lieu de lever",
        LANGAGE,
        POIDS_COURANT,
        "chaînage optionnel",
    ),
    (
        re.compile(r"^\s*(const|let)\s*[\{\[]"),
        "les valeurs sont extraites par leur nom au moment de la déclaration",
        LANGAGE,
        POIDS_COURANT,
        "destructuration",
    ),
    (
        re.compile(r"\.\.\.\w"),
        "le contenu est recopié dans une nouvelle structure, en surface "
        "seulement",
        LANGAGE,
        POIDS_NOTION,
        "diffusion",
    ),
    (
        re.compile(r"\bas\s+(?!const\b)[A-Z]\w*"),
        "l'assertion de type ne vérifie rien à l'exécution : elle demande "
        "seulement au compilateur de se taire",
        ROBUSTESSE,
        POIDS_PIEGE,
        None,
    ),
    (
        re.compile(r"\.reduce\s*\("),
        "l'accumulateur traverse toute la liste, et sa valeur de départ "
        "décide du type du résultat",
        LANGAGE,
        POIDS_NOTION,
        None,
    ),
    (
        re.compile(r"Promise\.all\s*\("),
        "les promesses avancent ensemble, et la première qui échoue fait "
        "échouer l'ensemble",
        LANGAGE,
        POIDS_NOTION,
        None,
    ),
)

_OUVRE_BOUCLE = re.compile(r"^\s*(for|while)\b|\.(forEach|map)\s*\(")


def _reperer_typescript(code: str) -> list[Repere]:
    trouves: list[Repere] = []
    lignes = code.splitlines()

    for index, ligne in enumerate(lignes):
        numero = index + 1
        nue = ligne.split("//")[0]
        if not nue.strip():
            continue

        for motif, intitule, categorie, poids, notion in _MOTIFS_TS:
            if motif.search(nue):
                trouves.append(
                    Repere(
                        ligne=numero,
                        intitule=intitule,
                        categorie=categorie,
                        poids=poids,
                        notion=notion,
                    )
                )

    trouves += _await_en_boucle(lignes)
    return trouves


def _indentation(ligne: str) -> int:
    return len(ligne) - len(ligne.lstrip())


def _await_en_boucle(lignes: list[str]) -> list[Repere]:
    """Repère un `await` exécuté un tour de boucle après l'autre.

    On suit l'indentation plutôt que les accolades : c'est faux sur du code
    mal formaté, mais du code mal formaté ne vient pas jusqu'ici — il sort
    d'un projet où un formateur tourne. Et l'erreur, quand elle arrive, ne
    coûte qu'une carte de moins.
    """
    trouves: list[Repere] = []
    boucle: int | None = None

    for index, ligne in enumerate(lignes):
        nue = ligne.split("//")[0]
        if not nue.strip():
            continue
        marge = _indentation(nue)

        if boucle is not None and marge <= boucle:
            boucle = None
        if _OUVRE_BOUCLE.search(nue):
            boucle = marge
            continue

        if boucle is not None and re.search(r"\bawait\b", nue):
            trouves.append(
                Repere(
                    ligne=index + 1,
                    intitule=(
                        "l'attente a lieu à chaque tour : les appels se font à "
                        "la file au lieu de partir ensemble"
                    ),
                    categorie=ROBUSTESSE,
                    poids=POIDS_PIEGE,
                )
            )
            boucle = None

    return trouves
