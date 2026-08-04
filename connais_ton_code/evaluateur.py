"""Évaluation de la réponse de l'utilisateur."""

from __future__ import annotations

import json
import os
import ssl
import time
import urllib.error
import urllib.request
from typing import Protocol, runtime_checkable

from .modeles import Evaluation, Extrait
from .stockage import dossier_donnees

URL_MISTRAL = "https://api.mistral.ai/v1/chat/completions"
MODELE_PAR_DEFAUT = "mistral-small-latest"
DELAI_RESEAU_S = 45.0

VARIABLE_CLE = "MISTRAL_API_KEY"
FICHIER_CLE = "cle_mistral"

_CONSIGNE = """Tu évalues l'explication qu'un développeur donne d'une fonction \
qu'il a lui-même écrite. Le but n'est pas de le juger mais de lui montrer ce \
qu'il n'a pas vu.

Réponds en français, en tutoyant, et uniquement par un objet JSON avec :
- "verdict" : une ou deux phrases de synthèse, directes, sans flatterie ;
- "score" : un entier de 0 à 100 mesurant la fidélité de l'explication au code ;
- "points_oublies" : une liste de 0 à 4 phrases courtes, chacune désignant \
quelque chose d'important dans le code que l'explication ne mentionne pas. \
Vise ce qui n'est pas évident : cas limite, raison d'un choix, effet de bord. \
Si l'explication est complète, rends une liste vide.

N'invente rien qui ne soit pas dans le code."""


@runtime_checkable
class Evaluateur(Protocol):
    """Contrat : comparer une explication au code qu'elle prétend décrire.

    `evaluer` est appelé dans un fil secondaire et a le droit d'être lent ou
    de faire du réseau, mais il ne doit toucher à aucun objet Qt. Il doit
    toujours rendre une `Evaluation` : une panne réseau se traduit par un
    verdict expliquant l'échec, pas par une exception qui laisserait
    l'interface bloquée sur l'indicateur d'attente.
    """

    def evaluer(self, extrait: Extrait, reponse: str) -> Evaluation:
        """Rend le verdict sur `reponse` au regard de `extrait`."""
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


class EvaluateurMistral:
    """Fait juger la réponse par un modèle Mistral.

    Un modèle tiers plutôt que celui qui a écrit le code : on ne demande pas
    à quelqu'un de corriger la copie qu'il a dictée.
    """

    def __init__(
        self,
        cle: str,
        modele: str = MODELE_PAR_DEFAUT,
        delai: float = DELAI_RESEAU_S,
    ) -> None:
        self._cle = cle
        self._modele = modele
        self._delai = delai

    def evaluer(self, extrait: Extrait, reponse: str) -> Evaluation:
        if not reponse.strip():
            return Evaluation(
                verdict="Réponse vide : il n'y a rien à évaluer.",
                score=0,
                points_oublies=[],
            )

        try:
            contenu = self._interroger(self._message(extrait, reponse))
        except urllib.error.HTTPError as erreur:
            return Evaluation(
                verdict=f"Mistral a refusé la requête ({erreur.code}). "
                f"{_detail_erreur(erreur)}",
                score=0,
                points_oublies=[],
            )
        except Exception as erreur:  # noqa: BLE001 - le contrat interdit de lever
            return Evaluation(
                verdict=f"L'évaluation n'a pas abouti : {erreur}",
                score=0,
                points_oublies=[],
            )

        return _lire_evaluation(contenu)

    def _message(self, extrait: Extrait, reponse: str) -> str:
        return (
            f"Fichier : {extrait.chemin_fichier}\n"
            f"Fonction : {extrait.nom_fonction}\n\n"
            f"Code :\n```{extrait.langage}\n{extrait.code}\n```\n\n"
            f"Explication donnée par le développeur :\n{reponse.strip()}"
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
                "temperature": 0.2,
                "max_tokens": 700,
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


def _detail_erreur(erreur: urllib.error.HTTPError) -> str:
    """Extrait le message d'erreur de l'API, s'il y en a un de lisible."""
    try:
        charge = json.loads(erreur.read().decode("utf-8"))
    except Exception:  # noqa: BLE001
        return ""
    message = charge.get("message") or charge.get("error")
    if isinstance(message, dict):
        message = message.get("message")
    return str(message) if message else ""


def _lire_evaluation(contenu: str) -> Evaluation:
    """Transforme la réponse du modèle en `Evaluation`.

    Le modèle est prié de rendre du JSON, mais rien ne le garantit : plutôt
    que d'échouer, on affiche le texte brut comme verdict.
    """
    try:
        donnees = json.loads(contenu)
    except json.JSONDecodeError:
        return Evaluation(verdict=contenu.strip(), score=0, points_oublies=[])

    if not isinstance(donnees, dict):
        return Evaluation(verdict=str(donnees), score=0, points_oublies=[])

    try:
        score = max(0, min(100, int(donnees.get("score", 0))))
    except (TypeError, ValueError):
        score = 0

    oublis = donnees.get("points_oublies") or []
    if not isinstance(oublis, list):
        oublis = [str(oublis)]

    return Evaluation(
        verdict=str(donnees.get("verdict", "")).strip() or "Pas de verdict rendu.",
        score=score,
        points_oublies=[str(point).strip() for point in oublis if str(point).strip()],
    )


class EvaluateurFactice:
    """Retour en dur, après une seconde, quand aucune clé n'est disponible.

    Le délai est volontaire : il rend visible l'état d'évaluation et permet de
    vérifier que la fenêtre reste utilisable pendant l'attente.
    """

    def __init__(self, delai_secondes: float = 1.0) -> None:
        self._delai_secondes = delai_secondes

    def evaluer(self, extrait: Extrait, reponse: str) -> Evaluation:
        time.sleep(self._delai_secondes)

        if not reponse.strip():
            return Evaluation(
                verdict="Réponse vide : impossible de juger quoi que ce soit.",
                score=0,
                points_oublies=["Tout le raisonnement de la fonction."],
            )

        return Evaluation(
            verdict=(
                f"Évaluation factice de {len(reponse.split())} mots sur "
                f"{extrait.nom_fonction}. Renseigne une clé Mistral pour un "
                f"vrai verdict."
            ),
            score=72,
            points_oublies=[
                "Le cas limite quand l'entrée est vide.",
                "La raison du tri avant le regroupement.",
                "Ce que la fonction fait en cas d'erreur réseau.",
            ],
        )
