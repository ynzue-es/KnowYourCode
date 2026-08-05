"""Fabrication des cartes, avant qu'on les pose.

Le modèle n'intervient plus après la réponse mais avant la question, et c'est
un renversement de fond. Ce qui était un jugement rendu en direct — lent,
incertain, à refaire à chaque manche — devient un texte écrit une fois,
vérifié, rangé, puis servi instantanément. La correction n'a plus besoin de
personne : elle est dans `cartes`, locale et sans réseau.

Le modèle ne choisit pas son sujet. `reperage` a déjà désigné les lignes et dit
ce qu'il y a à y voir ; il ne reste à rédiger que la question, les leurres et
l'explication. Sans repère, on ne demande rien : il n'y a pas de bonne carte à
poser sur du code qui n'a rien à apprendre, et une mauvaise carte coûte plus
cher qu'une manche sautée.

Rien de ce qui sort d'ici n'est cru sur parole. Chaque carte passe la douane de
`defauts` et une carte fautive est jetée, jamais rafistolée : trois bonnes
cartes valent mieux que quatre dont une ment.
"""

from __future__ import annotations

import hashlib
import json
import os
import ssl
import time
import urllib.request
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from .cartes import CARTES_PAR_SERIE, Carte, Forme, Serie, defauts

# Emprunté à la douane malgré son souligné : c'est elle qui décide ce qui
# compte comme un nom du code, et le générateur factice a besoin de la même
# définition, faute de quoi il écrirait des explications qu'elle refuserait.
from .cartes import _identifiants as _identifiants_du_code
from .modeles import Extrait
from .reperage import LANGAGE, ROBUSTESSE, SECURITE, Repere, reperer
from .stockage import dossier_donnees, ecrire_json, lire_json

URL_MISTRAL = "https://api.mistral.ai/v1/chat/completions"
MODELE_PAR_DEFAUT = "mistral-small-latest"
DELAI_RESEAU_S = 45.0

VARIABLE_CLE = "MISTRAL_API_KEY"
FICHIER_CLE = "cle_mistral"

FICHIER_CACHE = "cartes.json"

# Deux plafonds, parce qu'ils ne retiennent pas la même chose. Le nombre borne
# le fichier : deux cents séries de quatre cartes pèsent quelques centaines de
# kilo-octets, ce qui se relit d'un coup à chaque ouverture sans qu'on le
# sente. L'âge borne la dette : la consigne ci-dessous changera, et sans
# péremption les séries écrites sous l'ancienne continueraient d'être servies
# indéfiniment, sans que personne ne comprenne pourquoi certaines cartes sont
# moins bonnes que d'autres.
SERIES_GARDEES = 200
ANCIENNETE_MAXIMALE_S = 30 * 24 * 3600

_CONSIGNE = """Tu écris des cartes de révision sur un extrait de code que le \
développeur a écrit lui-même. Il répond en un geste — un clic sur une option, \
un clic sur une ligne, un mot tapé — puis il lit ton explication. Le partage \
est celui-là, et il est l'inverse de l'habitude : sa réponse est courte, ton \
explication est le morceau. N'écris jamais une question qui appelle un \
paragraphe.

Tu ne choisis pas tes sujets. On te donne des lignes, une par une, avec ce \
qu'il y a à y voir. Tu écris une carte par ligne donnée, et rien d'autre : \
aucune carte sur une ligne qu'on ne t'a pas désignée.

L'explication est de la prose suivie. Quatre phrases au plus, aucune liste, \
aucune puce, aucun titre de rubrique. Le pourquoi est dans les phrases, pas \
dans une section « pourquoi ». Elle dit ce que cette ligne-là empêche ou \
permet dans ce code-ci, et pour cela elle nomme au moins une variable ou une \
fonction du fichier. Une explication qui s'appliquerait aussi bien à n'importe \
quel autre code ne sert à rien : il s'en trouve mille meilleures en ligne.

Pour un « qcm », les trois mauvaises options sont des réponses que quelqu'un \
qui a mal lu le code donnerait vraiment. Une option absurde ne fait perdre que \
du temps. Elles font toutes à peu près la même longueur que la bonne : si la \
bonne est la plus détaillée, on la reconnaît sans lire le code et la carte \
n'apprend plus rien.

N'affirme rien que le code ne montre pas : pas de comportement supposé, pas de \
bibliothèque que tu n'y vois pas, pas de conseil général.

Écris en français, tutoie, ne félicite pas.

Réponds uniquement par un objet JSON de la forme {"cartes": [...]}, une entrée \
par ligne donnée, chacune avec :
- "forme" : "qcm", "reperer", "predire", "vrai_faux" ou "nommer" ;
- "ligne" : le numéro de la ligne donnée, recopié tel quel ;
- "question" : une seule phrase, 160 caractères au plus ;
- "options" : quatre propositions pour "qcm", exactement ["Vrai", "Faux"] pour \
"vrai_faux", une liste vide pour les autres formes ;
- "bonne" : le rang de la bonne option en comptant à partir de 0, sinon 0 ;
- "attendu" : pour "predire" et "nommer", les formulations acceptées de la \
réponse tapée, le mot juste et ses variantes courantes ; liste vide ailleurs ;
- "explication" : 480 caractères au plus.

La forme se déduit de la ligne. « reperer » quand la ligne se décrit sans se \
nommer : la question dit ce qui s'y passe et l'utilisateur la cherche dans le \
code, donc ne la cite pas et ne donne pas son numéro. « predire » quand la \
ligne produit une valeur qui se donne en un mot. « nommer » seulement si on \
t'a donné une notion pour cette ligne. « vrai_faux » pour une idée fausse \
répandue. « qcm » partout ailleurs."""


@runtime_checkable
class Generateur(Protocol):
    """Contrat : fabriquer les cartes d'un extrait avant qu'on les pose.

    `fabriquer` est appelé dans un fil secondaire, avant l'affichage de la
    première carte : il a le droit d'être lent et de faire du réseau, mais il
    ne doit toucher à aucun objet Qt. Il ne doit jamais lever — une panne
    réseau, un JSON illisible ou un modèle qui divague rendent `None`, et
    l'appelant se rabat sur autre chose plutôt que de rester bloqué sur
    l'indicateur d'attente.

    `None` est aussi la réponse normale quand il n'y a rien à fabriquer : un
    extrait sans repère ne mérite aucune question, et il vaut mieux ne rien
    proposer que de proposer une carte creuse.
    """

    def fabriquer(self, extrait: Extrait) -> Serie | None:
        """Rend les cartes à poser sur `extrait`, ou `None`."""
        ...


def _contexte_ssl() -> ssl.SSLContext:
    """Contexte TLS adossé aux certificats de `certifi`.

    Les Python installés depuis python.org sur macOS n'ont pas de magasin de
    certificats tant qu'on n'a pas lancé leur script d'installation à la main.
    Se reposer là-dessus condamnerait le projet à ne marcher que sur les
    machines déjà configurées.
    """
    try:
        import certifi
    except ImportError:
        return ssl.create_default_context()
    return ssl.create_default_context(cafile=certifi.where())


def cle_mistral() -> str | None:
    """Cherche la clé d'API, d'abord dans l'environnement puis sur le disque.

    Le fichier vit hors du dépôt, dans le dossier de données : une clé n'a
    rien à faire dans un projet public, fût-ce par accident.
    """
    depuis_environnement = os.environ.get(VARIABLE_CLE, "").strip()
    if depuis_environnement:
        return depuis_environnement

    fichier = dossier_donnees() / FICHIER_CLE
    try:
        contenu = fichier.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return contenu or None


# ---------------------------------------------------------------------------
# Le cache
# ---------------------------------------------------------------------------


def empreinte(code: str) -> str:
    """Une empreinte courte du code, pour la clé de cache.

    Tronquée, parce qu'elle ne protège rien : elle distingue deux versions
    d'une même fonction, elle n'authentifie personne. Douze caractères
    hexadécimaux rendent la collision assez improbable pour un cache local.
    """
    return hashlib.sha256(code.encode("utf-8")).hexdigest()[:12]


def cle_de_cache(extrait: Extrait) -> str:
    """La clé sous laquelle une série est rangée.

    L'identifiant seul ne suffirait pas : on servirait à une fonction retouchée
    les cartes de sa version d'avant, qui parleraient de lignes disparues.
    """
    return f"{extrait.identifiant}:{empreinte(extrait.code)}"


class CacheSeries:
    """Les séries déjà fabriquées, gardées sur disque.

    Une série coûte un appel réseau de plusieurs secondes ; la resservir ne
    coûte rien, et le texte est le même de toute façon puisque le code n'a pas
    bougé. C'est ce qui rend l'exercice supportable quand on repasse sur une
    fonction qu'on a déjà vue.
    """

    def __init__(
        self,
        chemin: Path | None = None,
        gardees: int = SERIES_GARDEES,
        anciennete: float = ANCIENNETE_MAXIMALE_S,
    ) -> None:
        self._chemin = chemin
        self._gardees = gardees
        self._anciennete = anciennete

    def lire(self, cle: str) -> tuple[Carte, ...] | None:
        """Rend la série rangée sous `cle`, ou `None` s'il faut la refaire."""
        entree = self._entrees().get(cle)
        if not isinstance(entree, dict):
            return None
        if time.time() - _flottant(entree.get("date")) > self._anciennete:
            return None
        return _depuis_json(entree.get("cartes")) or None

    def ecrire(self, cle: str, cartes: tuple[Carte, ...]) -> None:
        """Range une série, et fait le ménage au passage."""
        entrees = self._entrees()
        entrees[cle] = {
            "date": time.time(),
            "cartes": [_vers_json(carte) for carte in cartes],
        }
        try:
            ecrire_json(
                self._fichier(), {"version": 1, "series": self._elaguer(entrees)}
            )
        except OSError:
            # Un cache qu'on n'arrive pas à écrire n'est qu'un cache perdu. Le
            # contrat interdit de lever, et les cartes sont déjà fabriquées.
            pass

    def _fichier(self) -> Path:
        # Résolu à l'usage, pas à la construction : `dossier_donnees` crée le
        # dossier, et instancier un générateur ne doit rien écrire nulle part.
        if self._chemin is not None:
            return self._chemin
        return dossier_donnees() / FICHIER_CACHE

    def _entrees(self) -> dict[str, Any]:
        contenu = lire_json(self._fichier(), {})
        series = contenu.get("series") if isinstance(contenu, dict) else None
        return dict(series) if isinstance(series, dict) else {}

    def _elaguer(self, entrees: dict[str, Any]) -> dict[str, Any]:
        limite = time.time() - self._anciennete
        vivantes = {
            cle: entree
            for cle, entree in entrees.items()
            if isinstance(entree, dict) and _flottant(entree.get("date")) >= limite
        }
        if len(vivantes) <= self._gardees:
            return vivantes

        # On garde les plus récentes : une série qu'on vient de servir a toutes
        # les chances de resservir, celle d'il y a trois semaines beaucoup moins.
        par_date = sorted(
            vivantes.items(),
            key=lambda paire: _flottant(paire[1].get("date")),
            reverse=True,
        )
        return dict(par_date[: self._gardees])


# ---------------------------------------------------------------------------
# Le générateur réel
# ---------------------------------------------------------------------------


class GenerateurMistral:
    """Fait rédiger les cartes par un modèle Mistral.

    Un seul appel par série, pas un par carte : les cartes portent sur le même
    extrait et se répondent l'une l'autre, les fabriquer séparément produirait
    quatre fois la même question sous quatre formes.
    """

    def __init__(
        self,
        cle: str,
        modele: str = MODELE_PAR_DEFAUT,
        delai: float = DELAI_RESEAU_S,
        cache: CacheSeries | None = None,
    ) -> None:
        self._cle = cle
        self._modele = modele
        self._delai = delai
        self._cache = cache if cache is not None else CacheSeries()

    def fabriquer(self, extrait: Extrait) -> Serie | None:
        reperes = reperer(extrait.code, extrait.langage)
        if not reperes:
            return None

        # Les repères arrivent triés, le plus lourd en tête : prendre les
        # premiers, c'est poser les questions qui apprennent le plus.
        retenus = reperes[:CARTES_PAR_SERIE]

        cle = cle_de_cache(extrait)
        deja = self._cache.lire(cle)
        if deja is not None:
            return Serie(extrait=extrait, cartes=deja)

        try:
            contenu = self._interroger(self._message(extrait, retenus))
        except Exception:  # noqa: BLE001 - le contrat interdit de lever
            return None

        cartes = _lire_cartes(contenu, retenus, extrait.code)
        if not cartes:
            return None

        self._cache.ecrire(cle, cartes)
        return Serie(extrait=extrait, cartes=cartes)

    def _message(self, extrait: Extrait, reperes: list[Repere]) -> str:
        return (
            f"Fichier : {extrait.chemin_fichier}\n"
            f"Fonction : {extrait.nom_fonction}\n"
            f"Langage : {extrait.langage}\n\n"
            f"Code, chaque ligne précédée de son numéro :\n"
            f"```\n{_code_numerote(extrait.code)}\n```\n\n"
            f"Lignes à traiter, une carte chacune, dans cet ordre :\n"
            f"{_consignes(reperes)}"
        )

    def _interroger(self, message: str) -> str:
        corps = json.dumps(
            {
                "model": self._modele,
                "messages": [
                    {"role": "system", "content": _CONSIGNE},
                    {"role": "user", "content": message},
                ],
                "response_format": {"type": "json_object"},
                # Plus haut que pour un jugement : des leurres identiques d'une
                # série à l'autre finissent par se reconnaître sans lire.
                "temperature": 0.4,
                "max_tokens": 2000,
            }
        ).encode("utf-8")

        requete = urllib.request.Request(
            URL_MISTRAL,
            data=corps,
            headers={
                "Authorization": f"Bearer {self._cle}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )

        with urllib.request.urlopen(
            requete, timeout=self._delai, context=_contexte_ssl()
        ) as reponse:
            charge = json.loads(reponse.read().decode("utf-8"))

        return charge["choices"][0]["message"]["content"]


def _code_numerote(code: str) -> str:
    """Le code avec ses numéros de ligne.

    Sans eux, le modèle recompte à la main et se décale d'une ligne dès qu'il y
    a une ligne vide — et une carte qui vise la mauvaise ligne est fausse.
    """
    return "\n".join(
        f"{numero:>3} | {ligne}"
        for numero, ligne in enumerate(code.splitlines(), start=1)
    )


def _consignes(reperes: list[Repere]) -> str:
    morceaux: list[str] = []
    for repere in reperes:
        if repere.notion is not None:
            vocabulaire = (
                f" La notion à faire nommer est « {repere.notion} » : "
                'la forme "nommer" est permise sur cette ligne.'
            )
        else:
            vocabulaire = (
                " Aucune notion n'est attachée à cette ligne : "
                'la forme "nommer" y est interdite.'
            )
        morceaux.append(
            f"- ligne {repere.ligne} ({repere.categorie}) : "
            f"{repere.intitule}.{vocabulaire}"
        )
    return "\n".join(morceaux)


# ---------------------------------------------------------------------------
# Lecture de la réponse du modèle
# ---------------------------------------------------------------------------

_FORMES: dict[str, Forme] = {
    "qcm": Forme.QCM,
    "reperer": Forme.REPERER,
    "predire": Forme.PREDIRE,
    "vrai_faux": Forme.VRAI_FAUX,
    "nommer": Forme.NOMMER,
}


def _lire_cartes(
    contenu: str, reperes: list[Repere], code: str
) -> tuple[Carte, ...]:
    """Transforme la réponse du modèle en cartes, et n'en garde que de bonnes.

    Tout ce qui ne se lit pas rend une série vide plutôt qu'une exception :
    l'appelant traduira ça en `None` et passera à autre chose.
    """
    try:
        donnees = json.loads(contenu)
    except (json.JSONDecodeError, TypeError):
        return ()

    if isinstance(donnees, dict):
        brutes = donnees.get("cartes")
    elif isinstance(donnees, list):
        brutes = donnees
    else:
        brutes = None
    if not isinstance(brutes, list):
        return ()

    par_ligne = {repere.ligne: repere for repere in reperes}
    retenues: list[Carte] = []
    for brute in brutes:
        carte = _en_carte(brute, par_ligne)
        if carte is None or defauts(carte, code):
            continue
        retenues.append(carte)

    return tuple(retenues[:CARTES_PAR_SERIE])


def _en_carte(brute: Any, par_ligne: dict[int, Repere]) -> Carte | None:
    """Une entrée du JSON en `Carte`, ou `None` si elle n'en est pas une."""
    if not isinstance(brute, dict):
        return None

    forme = _FORMES.get(str(brute.get("forme", "")).strip().lower())
    if forme is None:
        return None

    # Le repère commande. Une carte posée sur une ligne qu'on n'a pas désignée
    # est une carte dont le modèle a choisi le sujet, c'est-à-dire exactement
    # ce que le repérage sert à empêcher.
    repere = par_ligne.get(_entier(brute.get("ligne")))
    if repere is None:
        return None

    return Carte(
        forme=forme,
        question=str(brute.get("question", "")).strip(),
        explication=str(brute.get("explication", "")).strip(),
        # Sur une carte « reperer », surligner la ligne donnerait la réponse :
        # elle passe du côté de ce qu'on demande de trouver.
        ligne=0 if forme is Forme.REPERER else repere.ligne,
        options=_textes(brute.get("options")),
        bonne=(
            repere.ligne if forme is Forme.REPERER else _entier(brute.get("bonne"))
        ),
        attendu=_textes(brute.get("attendu")),
        categorie=repere.categorie,
        notion=repere.notion,
    )


def _entier(valeur: Any) -> int:
    """Un entier, ou `-1` — que la douane rejettera comme hors bornes."""
    try:
        return int(valeur)
    except (TypeError, ValueError):
        return -1


def _flottant(valeur: Any) -> float:
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return 0.0


def _textes(valeur: Any) -> tuple[str, ...]:
    if not isinstance(valeur, list):
        return ()
    return tuple(str(element).strip() for element in valeur if str(element).strip())


def _vers_json(carte: Carte) -> dict[str, Any]:
    return {
        "forme": carte.forme.name.lower(),
        "question": carte.question,
        "explication": carte.explication,
        "ligne": carte.ligne,
        "options": list(carte.options),
        "bonne": carte.bonne,
        "attendu": list(carte.attendu),
        "categorie": carte.categorie,
        "notion": carte.notion,
    }


def _depuis_json(brutes: Any) -> tuple[Carte, ...]:
    """Relit une série mise de côté.

    La moindre anomalie rend une série vide, donc un défaut de cache : on
    refabrique. C'est le seul endroit où repayer un appel réseau est plus sûr
    que de deviner ce qu'une entrée abîmée voulait dire.
    """
    if not isinstance(brutes, list) or not brutes:
        return ()

    cartes: list[Carte] = []
    for brute in brutes:
        if not isinstance(brute, dict):
            return ()
        forme = _FORMES.get(str(brute.get("forme", "")))
        if forme is None:
            return ()
        notion = brute.get("notion")
        cartes.append(
            Carte(
                forme=forme,
                question=str(brute.get("question", "")),
                explication=str(brute.get("explication", "")),
                ligne=_entier(brute.get("ligne")),
                options=_textes(brute.get("options")),
                bonne=_entier(brute.get("bonne")),
                attendu=_textes(brute.get("attendu")),
                categorie=str(brute.get("categorie", LANGAGE)),
                notion=str(notion) if notion else None,
            )
        )
    return tuple(cartes)


# ---------------------------------------------------------------------------
# Le générateur sans réseau
# ---------------------------------------------------------------------------

# Les quatre réponses de la question de catégorie. Elles font toutes la même
# longueur, sinon la bonne se repère à l'œil et la douane le signale à juste
# titre.
_CATEGORIES = (
    (LANGAGE, "Une tournure du langage"),
    (ROBUSTESSE, "Un défaut de robustesse"),
    (SECURITE, "Un point de sécurité"),
    (None, "Rien de particulier"),
)


class GenerateurFactice:
    """Fabrique une série à partir des seuls repères, sans réseau ni clé.

    Elle ne remplace pas le modèle : les questions sont mécaniques et les
    explications se contentent de redire ce que le repérage sait déjà. Elle
    remplace son absence — sans clé, l'application doit rester utilisable, et
    les vérifications doivent pouvoir tourner sans dépendre d'un service.
    """

    def fabriquer(self, extrait: Extrait) -> Serie | None:
        reperes = reperer(extrait.code, extrait.langage)
        if not reperes:
            return None

        cartes: list[Carte] = []
        for rang, repere in enumerate(reperes[:CARTES_PAR_SERIE]):
            carte = _carte_factice(rang, repere, extrait.code)
            # Le factice passe la même douane que le modèle : une série
            # bouchonnée qui franchirait un contrôle que le réel ne franchit
            # pas ne vérifierait plus rien.
            if carte is not None and not defauts(carte, extrait.code):
                cartes.append(carte)

        return Serie(extrait=extrait, cartes=tuple(cartes)) if cartes else None


def _carte_factice(rang: int, repere: Repere, code: str) -> Carte | None:
    ancre = _ancre(repere, code)
    if ancre is None:
        return None
    explication = _explication_factice(repere, ancre)

    if rang == 0:
        return Carte(
            forme=Forme.QCM,
            question=f"Sur quoi porte la ligne {repere.ligne} de cet extrait ?",
            explication=explication,
            ligne=repere.ligne,
            options=tuple(libelle for _, libelle in _CATEGORIES),
            bonne=next(
                (
                    index
                    for index, (categorie, _) in enumerate(_CATEGORIES)
                    if categorie == repere.categorie
                ),
                len(_CATEGORIES) - 1,
            ),
            categorie=repere.categorie,
            notion=repere.notion,
        )

    if rang == 1:
        return Carte(
            forme=Forme.REPERER,
            question=(
                "Sur quelle ligne trouve-t-on ceci : "
                f"{_ecourter(repere.intitule, 120)} ?"
            ),
            explication=explication,
            bonne=repere.ligne,
            categorie=repere.categorie,
            notion=repere.notion,
        )

    if repere.notion is not None:
        return Carte(
            forme=Forme.NOMMER,
            question=f"Comment s'appelle ce que fait la ligne {repere.ligne} ?",
            explication=explication,
            ligne=repere.ligne,
            attendu=(repere.notion,),
            categorie=repere.categorie,
            notion=repere.notion,
        )

    return Carte(
        forme=Forme.VRAI_FAUX,
        # Toujours vrai : le factice sert à faire tourner l'interface, pas à
        # piéger qui que ce soit, et fabriquer une négation correcte à partir
        # d'un intitulé demanderait de le comprendre.
        question=f"Vrai ou faux : {_ecourter(repere.intitule, 140)}",
        explication=explication,
        ligne=repere.ligne,
        options=("Vrai", "Faux"),
        bonne=0,
        categorie=repere.categorie,
        notion=repere.notion,
    )


def _explication_factice(repere: Repere, ancre: str) -> str:
    return (
        f"{_capitale(_ecourter(repere.intitule, 220))}. On le lit directement "
        f"sur cette ligne, autour de `{ancre}`. Cette carte sort du générateur "
        f"factice : sans clé Mistral, elle n'en dira pas plus que ce que le "
        f"repérage a vu."
    )


def _ancre(repere: Repere, code: str) -> str | None:
    """Un nom du code à citer dans l'explication.

    La douane exige que l'explication nomme quelque chose du fichier ; on lui
    emprunte sa propre définition de ce qui compte, parce qu'un factice qui la
    devinerait autrement se ferait recaler par elle et ne servirait à rien.
    """
    lignes = code.splitlines()
    candidats: set[str] = set()
    if 1 <= repere.ligne <= len(lignes):
        candidats = _identifiants_du_code(lignes[repere.ligne - 1])
    if not candidats:
        candidats = _identifiants_du_code(code)
    if not candidats:
        return None
    # Le plus long d'abord : c'est presque toujours le nom métier plutôt qu'un
    # `i` ou un `os`. À longueur égale, l'ordre alphabétique, pour que deux
    # lancements donnent la même carte.
    return sorted(candidats, key=lambda mot: (-len(mot), mot))[0]


def _ecourter(texte: str, limite: int) -> str:
    """Coupe au dernier mot entier qui tienne.

    Les intitulés du repérage sont écrits pour un modèle qui les reformulera.
    Le factice, lui, les recopie tels quels : c'est à lui de les tailler pour
    qu'ils tiennent dans une question.
    """
    texte = texte.strip()
    if len(texte) <= limite:
        return texte
    return f"{texte[: limite - 1].rsplit(' ', 1)[0]}…"


def _capitale(texte: str) -> str:
    return texte[:1].upper() + texte[1:] if texte else texte
