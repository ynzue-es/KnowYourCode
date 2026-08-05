"""Repérer l'instant où un prompt part vers Claude Code.

La règle de la maison est que rien ne s'ouvre tout seul. Ce module n'y
contrevient pas : ce qu'elle interdit, c'est d'interrompre quelqu'un qui
travaille. Or l'instant où l'on envoie un prompt est précisément celui où l'on
*cesse* de travailler, pour attendre. C'est le moment que le produit vise
depuis le début.

Reste à savoir qu'un prompt est parti. Trois voies, et une seule qui tienne.

Le hook `UserPromptSubmit`. Il faut l'écrire dans `~/.claude/settings.json`,
qui vaut pour toutes les sessions de la machine et contient les réglages
d'autres outils, et il ne prend effet qu'au redémarrage suivant de Claude
Code. Deux gestes pour un confort, dont un qu'on oublie. C'est ce que faisait
ce module, et il ne s'est jamais déclenché.

Les paquets sortants. Le trafic est chiffré : on verrait une connexion vers
Anthropic, jamais un POST. Claude Code parle d'ailleurs à ses serveurs sans
arrêt pendant qu'il travaille, pas seulement quand on l'interroge. Et lire les
paquets demande d'ouvrir un `/dev/bpf`, donc les droits administrateur à
chaque lancement — hors de proportion avec ce qu'on veut en tirer.

Le journal de session. Claude Code écrit chaque événement dans
`~/.claude/projects/<projet>/<session>.jsonl`, au fil de l'eau. Un prompt tapé
au clavier y laisse une ligne reconnaissable au moment même où il part. Rien à
installer, rien à redémarrer, aucun fichier qui appartienne à quelqu'un
d'autre : on ne fait que lire. C'est la voie retenue.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from .stockage import dossier_donnees, ecrire_json, lire_json

DOSSIER_SESSIONS = Path.home() / ".claude" / "projects"

NOM_REGLAGE = "reveil.json"

# Ce qu'on accepte de lire d'un seul journal en un tour. Un retour d'outil
# volumineux peut faire grossir une session de plusieurs mégaoctets d'un coup,
# et cette lecture se fait sur le fil de l'interface : mieux vaut manquer un
# prompt, qui ne coûte qu'un confort, que figer la fenêtre une seconde.
OCTETS_MAX = 400_000


# ----------------------------------------------------------------------
# Le réglage
# ----------------------------------------------------------------------


def _chemin_reglage() -> Path:
    return dossier_donnees() / NOM_REGLAGE


def est_actif() -> bool:
    """Dit si l'ouverture automatique est demandée. Éteinte par défaut."""
    contenu = lire_json(_chemin_reglage(), {})
    return bool(contenu.get("actif")) if isinstance(contenu, dict) else False


def definir_actif(actif: bool) -> None:
    """Retient le choix. Rien n'est posé nulle part, il n'y a rien à défaire."""
    ecrire_json(_chemin_reglage(), {"actif": bool(actif)})


# ----------------------------------------------------------------------
# La lecture du journal
# ----------------------------------------------------------------------


def _est_un_retour_d_outil(evenement: dict) -> bool:
    message = evenement.get("message")
    contenu = message.get("content") if isinstance(message, dict) else None
    if not isinstance(contenu, list):
        return False
    return any(
        isinstance(bloc, dict) and bloc.get("type") == "tool_result"
        for bloc in contenu
    )


def est_un_prompt(evenement: dict) -> bool:
    """Dit si cette ligne du journal est un prompt envoyé par la personne.

    Les lignes `user` sont très majoritairement des retours d'outils : dans une
    session ordinaire, une sur dix vient vraiment du clavier. `origin` les
    sépare proprement. On ne s'y fie pas seule pour autant — une version de
    Claude Code qui ne l'écrirait pas ferait taire le réveil sans prévenir.
    Sans elle, on retombe sur la forme du contenu, qui est le vrai
    discriminant : un retour d'outil est une liste de blocs `tool_result`.
    """
    if evenement.get("type") != "user":
        return False
    origine = evenement.get("origin")
    if isinstance(origine, dict):
        return origine.get("kind") == "human"
    return not _est_un_retour_d_outil(evenement)


class Guetteur:
    """Suit les journaux de session et dit quels prompts viennent de partir.

    Chaque journal est suivi par sa position : on ne relit jamais ce qu'on a
    déjà lu. Ceux qui existaient au moment où l'on démarre sont notés à leur
    taille du moment, sans rien signaler — sans cette amorce, lancer
    l'application ferait remonter d'un coup tous les prompts de la journée.

    Tous les journaux sont suivis, pas seulement le plus récent : deux projets
    peuvent tourner en parallèle, et celui où l'on tape n'est pas forcément
    celui qui écrit le plus.
    """

    def __init__(self, racine: Path | None = None) -> None:
        self._racine = Path(racine) if racine is not None else DOSSIER_SESSIONS
        # chemin -> (date de dernière écriture, position déjà lue)
        self._suivis: dict[Path, tuple[float, int]] = {
            chemin: (date, taille) for chemin, date, taille in self._journaux()
        }

    def prompts(self) -> list[str]:
        """Les dossiers de travail des prompts parus depuis le dernier appel.

        Rendre le dossier plutôt qu'un simple compte ne coûte rien et dit dans
        quel projet la personne vient d'appuyer sur Entrée.
        """
        parus: list[str] = []
        presents: set[Path] = set()

        for chemin, date, taille in self._journaux():
            presents.add(chemin)
            connu = self._suivis.get(chemin)

            if connu is None:
                # Une session ouverte après nous : tout son contenu est neuf.
                depart = 0
            elif connu == (date, taille):
                continue
            elif taille < connu[1]:
                # Le journal a rétréci, donc ce n'est plus le même : Claude
                # Code n'écrit qu'en ajoutant. On se replace à la fin plutôt
                # que de risquer de rejouer un passé qu'on ne sait pas dater.
                self._suivis[chemin] = (date, taille)
                continue
            else:
                depart = connu[1]

            lus, position = self._lire(chemin, depart, taille)
            self._suivis[chemin] = (date, position)
            parus.extend(lus)

        for disparu in set(self._suivis) - presents:
            del self._suivis[disparu]

        return parus

    def _lire(self, chemin: Path, depart: int, taille: int) -> tuple[list[str], int]:
        if taille - depart > OCTETS_MAX:
            depart = taille - OCTETS_MAX

        try:
            with chemin.open("rb") as fichier:
                fichier.seek(depart)
                brut = fichier.read(taille - depart)
        except OSError:
            return [], depart

        # La dernière ligne est peut-être en cours d'écriture : on s'arrête au
        # dernier passage à la ligne et on reprendra le reste au tour suivant.
        coupe = brut.rfind(b"\n")
        if coupe < 0:
            return [], depart

        parus: list[str] = []
        for ligne in brut[:coupe].split(b"\n"):
            # La quasi-totalité des lignes sont des réponses ou des outils.
            # Ce filtre grossier évite de les analyser une par une ; il ne peut
            # que garder trop, jamais trop peu.
            if b'"user"' not in ligne:
                continue
            try:
                evenement = json.loads(ligne)
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            if isinstance(evenement, dict) and est_un_prompt(evenement):
                parus.append(str(evenement.get("cwd") or ""))

        return parus, depart + coupe + 1

    def _journaux(self) -> list[tuple[Path, float, int]]:
        """Les journaux de session, avec leur date et leur taille.

        Un `scandir` plutôt qu'un `glob` : de chaque fichier on ne veut que ce
        que le dossier sait déjà de lui, et ce relevé passe toutes les deux
        secondes sur des sessions qui s'accumulent au fil des mois.
        """
        trouves: list[tuple[Path, float, int]] = []
        try:
            dossiers = list(os.scandir(self._racine))
        except OSError:
            return []

        for dossier in dossiers:
            try:
                if not dossier.is_dir():
                    continue
                entrees = list(os.scandir(dossier.path))
            except OSError:
                continue
            for entree in entrees:
                if not entree.name.endswith(".jsonl"):
                    continue
                try:
                    infos = entree.stat()
                except OSError:
                    continue
                trouves.append((Path(entree.path), infos.st_mtime, infos.st_size))

        return trouves
