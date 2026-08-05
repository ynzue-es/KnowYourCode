"""Mémoire des cartes déjà posées et des réponses données.

Deux usages : ne pas reproposer un extrait déjà creusé, et pouvoir relire sa
régularité dans le temps. C'est ce second usage qui compte le plus depuis que
l'exercice tient en quelques cartes par jour — la série de jours d'affilée se
lit ici, et nulle part ailleurs.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .cartes import Carte, Correction
from .modeles import ANCIENNE, CARTE, PASSE, EntreeHistorique, Extrait
from .stockage import dossier_donnees, ecrire_json, lire_json

NOM_FICHIER = "historique.json"

# Version 1 : une explication tapée, notée sur 100 par un modèle. Version 2 :
# une carte, juste ou fausse. Le numéro est écrit à chaque ajout mais n'est
# jamais relu : c'est la forme de chaque ligne qui décide, pas l'en-tête. Un
# fichier écrit par deux versions différentes de l'application se lit donc
# quand même, ce qu'un aiguillage sur l'en-tête ne permettrait pas.
VERSION_FORMAT = 2


def _maintenant_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _entree_depuis_brut(brut: object) -> EntreeHistorique | None:
    """Valide et convertit une entrée lue du JSON, ou `None` si elle ne l'est pas.

    Lecture tolérante plutôt que migration, et c'est un choix, pas une
    facilité. Une entrée de la version 1 ne contient ni forme, ni notion, ni
    juste ou faux : aucune réécriture ne peut les retrouver. Migrer
    reviendrait donc à inventer ces champs ou à jeter les lignes, et jeter des
    mois d'historique pour un changement d'exercice serait le pire accueil
    possible. On lit chaque ligne pour ce qu'elle est, on n'en réécrit aucune,
    et les nouvelles cartes s'ajoutent à la suite des anciennes.

    Le fichier peut aussi porter les traces d'une écriture interrompue : mieux
    vaut écarter la ligne que faire tomber l'application au démarrage.
    """
    if not isinstance(brut, dict):
        return None
    try:
        identifiant = brut["identifiant"]
        chemin_fichier = brut["chemin_fichier"]
        nom_fonction = brut["nom_fonction"]
        langage = brut["langage"]
        issue = brut["issue"]
        date = datetime.fromisoformat(brut["date"])
    except (KeyError, TypeError, ValueError):
        return None
    champs_texte = (identifiant, chemin_fichier, nom_fonction, langage, issue)
    if not all(isinstance(champ, str) for champ in champs_texte):
        return None

    commun = {
        "identifiant": identifiant,
        "chemin_fichier": chemin_fichier,
        "nom_fonction": nom_fonction,
        "langage": langage,
        "date": date,
    }

    # « repondu » était le nom de l'issue à l'époque des explications notées.
    # Elle devient une entrée sans carte : on ne saura jamais quelle notion
    # était en jeu ni si la réponse était juste, mais on sait que ce jour-là
    # l'utilisateur a travaillé, et sa série mérite d'en tenir compte.
    if issue == "repondu":
        return EntreeHistorique(**commun, issue=ANCIENNE)

    # Un passage n'a jamais rien porté d'autre que sa date : les deux formats
    # l'écrivent pareil, il n'y a rien à convertir.
    if issue == PASSE:
        return EntreeHistorique(**commun, issue=PASSE)

    if issue != CARTE:
        return None

    forme = brut.get("forme")
    categorie = brut.get("categorie")
    juste = brut.get("juste")
    notion = brut.get("notion")
    ligne = brut.get("ligne", 0)
    if not isinstance(forme, str) or not isinstance(categorie, str):
        return None
    # `isinstance(True, int)` étant vrai en Python, l'ordre compte : on exige
    # un vrai booléen avant de laisser passer un entier pour la ligne.
    if not isinstance(juste, bool) or isinstance(ligne, bool):
        return None
    if not isinstance(ligne, int) or ligne < 0:
        return None
    if notion is not None and not isinstance(notion, str):
        return None

    return EntreeHistorique(
        **commun,
        issue=CARTE,
        forme=forme,
        categorie=categorie,
        notion=notion,
        ligne=ligne,
        juste=juste,
    )


class Historique:
    """Journal append-only des cartes posées, adossé à un fichier JSON.

    Le fichier entier est relu au démarrage et réécrit à chaque ajout : à
    quelques cartes par jour, la simplicité vaut mieux qu'un format
    incrémental.
    """

    def __init__(self, chemin: Path | None = None) -> None:
        self.chemin = chemin or (dossier_donnees() / NOM_FICHIER)
        contenu = lire_json(self.chemin, {"version": VERSION_FORMAT, "entrees": []})
        entrees = contenu.get("entrees") if isinstance(contenu, dict) else None
        self._entrees: list[dict] = entrees if isinstance(entrees, list) else []

    def identifiants_deja_vus(self) -> set[str]:
        """Les extraits déjà proposés, creusés ou passés."""
        return {
            entree["identifiant"]
            for entree in self._entrees
            if isinstance(entree, dict) and "identifiant" in entree
        }

    def entrees(self) -> list[EntreeHistorique]:
        """Les entrées valides, la plus ancienne d'abord.

        Le fichier n'étant qu'allongé par ajout, l'ordre sur disque est déjà
        chronologique ; les entrées illisibles sont simplement écartées.
        """
        entrees = (_entree_depuis_brut(brute) for brute in self._entrees)
        return [entree for entree in entrees if entree is not None]

    def enregistrer_carte(
        self, extrait: Extrait, carte: Carte, correction: Correction
    ) -> None:
        """Note une carte répondue, juste ou fausse.

        Appelée carte par carte et non série par série : une série
        interrompue en chemin doit compter pour la journée, sinon quelqu'un
        qui referme le panneau au bout de deux cartes perdrait sa série.
        """
        self._ajouter(
            extrait,
            {
                "issue": CARTE,
                "forme": carte.forme.name,
                "categorie": carte.categorie,
                "notion": carte.notion,
                "ligne": carte.ligne,
                "juste": correction.juste,
            },
        )

    def enregistrer_passage(self, extrait: Extrait) -> None:
        """Note qu'un extrait a été passé, pour ne pas le reproposer aussitôt."""
        self._ajouter(extrait, {"issue": PASSE})

    def _ajouter(self, extrait: Extrait, details: dict) -> None:
        self._entrees.append(
            {
                "identifiant": extrait.identifiant,
                "chemin_fichier": extrait.chemin_fichier,
                "nom_fonction": extrait.nom_fonction,
                "langage": extrait.langage,
                "date": _maintenant_iso(),
                **details,
            }
        )
        ecrire_json(
            self.chemin, {"version": VERSION_FORMAT, "entrees": self._entrees}
        )
