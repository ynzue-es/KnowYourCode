#!/usr/bin/env python3
"""Vérification du réveil : reconnaître un prompt sans jamais rejouer le passé.

Le module lit les journaux de session de Claude Code. Deux fautes possibles, et
elles se valent : ne pas voir passer un prompt, ou en voir un qui n'existe pas
et ouvrir une fenêtre à quelqu'un en plein travail. Tout ce qui suit tourne sur
de faux journaux écrits pour l'occasion.

La dernière série, elle, se branche sur les vrais journaux de la machine, en
lecture seule. C'est la seule façon de savoir si la forme qu'on attend est
celle que Claude Code écrit vraiment ; sans elle, on ne vérifierait que sa
propre idée du format.

    python outils/verif_reveil.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Avant tout import du paquet : rien ne doit toucher au dossier de données réel.
DOSSIER_TEST = tempfile.mkdtemp(prefix="knowyourcode-reveil-")
os.environ["KNOWYOURCODE_DOSSIER"] = DOSSIER_TEST

from connais_ton_code import reveil  # noqa: E402

_constats: list[tuple[bool, str]] = []


def _verifier(condition: bool, description: str) -> None:
    _constats.append((bool(condition), description))


# ----------------------------------------------------------------------
# De quoi fabriquer un faux journal
# ----------------------------------------------------------------------

DOSSIER_TRAVAIL = "/Users/quelquun/projet"


def _prompt(texte: str = "bonjour", cwd: str = DOSSIER_TRAVAIL) -> dict:
    return {
        "type": "user",
        "origin": {"kind": "human"},
        "promptSource": "typed",
        "cwd": cwd,
        "message": {"role": "user", "content": texte},
    }


def _retour_d_outil() -> dict:
    return {
        "type": "user",
        "origin": {"kind": "tool"},
        "cwd": DOSSIER_TRAVAIL,
        "message": {
            "role": "user",
            "content": [{"type": "tool_result", "content": "ok"}],
        },
    }


def _reponse() -> dict:
    return {
        "type": "assistant",
        "message": {"role": "assistant", "content": [{"type": "text", "text": "ok"}]},
    }


class FauxJournal:
    """Un dossier de sessions qu'on remplit ligne à ligne."""

    def __init__(self) -> None:
        self.racine = Path(tempfile.mkdtemp(prefix="knowyourcode-sessions-"))

    def session(self, nom: str = "session") -> Path:
        dossier = self.racine / "-projet"
        dossier.mkdir(parents=True, exist_ok=True)
        chemin = dossier / f"{nom}.jsonl"
        chemin.touch()
        return chemin

    @staticmethod
    def ajouter(chemin: Path, *evenements: dict, entiere: bool = True) -> None:
        ligne = "".join(
            json.dumps(e, ensure_ascii=False) + "\n" for e in evenements
        )
        if not entiere:
            ligne = ligne.rstrip("\n")
        with chemin.open("a", encoding="utf-8") as fichier:
            fichier.write(ligne)
        # Deux écritures dans la même seconde peuvent partager une date ; le
        # guetteur compare aussi la taille, mais autant vérifier le cas où les
        # deux changent, qui est celui de la vraie vie.
        os.utime(chemin, (time.time() + 1, time.time() + 1))


# ----------------------------------------------------------------------
# Le réglage
# ----------------------------------------------------------------------


def verifier_le_reglage() -> None:
    _verifier(not reveil.est_actif(), "l'ouverture automatique est éteinte par défaut")

    reveil.definir_actif(True)
    _verifier(reveil.est_actif(), "elle s'allume et se retient")

    reveil.definir_actif(False)
    _verifier(not reveil.est_actif(), "elle s'éteint")

    reveil._chemin_reglage().write_text("{pas du JSON", encoding="utf-8")
    _verifier(
        not reveil.est_actif(),
        "un réglage illisible laisse l'ouverture éteinte plutôt que de lever",
    )
    reveil.definir_actif(False)


# ----------------------------------------------------------------------
# Ce qu'on reconnaît comme un prompt
# ----------------------------------------------------------------------


def verifier_la_reconnaissance() -> None:
    _verifier(reveil.est_un_prompt(_prompt()), "un prompt tapé est reconnu")
    _verifier(
        not reveil.est_un_prompt(_retour_d_outil()),
        "un retour d'outil n'est pas pris pour un prompt",
    )
    _verifier(not reveil.est_un_prompt(_reponse()), "une réponse n'est pas un prompt")
    _verifier(
        not reveil.est_un_prompt({"type": "system", "content": "x"}),
        "une ligne de service n'est pas un prompt",
    )

    # Un prompt mis en file d'attente pendant que Claude Code travaillait part
    # bien du clavier de quelqu'un : c'est un prompt.
    en_attente = _prompt() | {"promptSource": "queued"}
    _verifier(reveil.est_un_prompt(en_attente), "un prompt mis en file est reconnu")

    # Repli sur la forme du contenu : si `origin` disparaissait d'une version à
    # l'autre, le réveil doit continuer de marcher au lieu de se taire.
    sans_origine = _prompt()
    del sans_origine["origin"]
    _verifier(
        reveil.est_un_prompt(sans_origine),
        "sans le champ d'origine, un prompt reste reconnu à son contenu",
    )
    outil_sans_origine = _retour_d_outil()
    del outil_sans_origine["origin"]
    _verifier(
        not reveil.est_un_prompt(outil_sans_origine),
        "sans le champ d'origine, un retour d'outil reste écarté",
    )


# ----------------------------------------------------------------------
# Le guetteur
# ----------------------------------------------------------------------


def verifier_l_amorce() -> None:
    journal = FauxJournal()
    chemin = journal.session()
    journal.ajouter(chemin, _prompt("d'hier"), _prompt("d'avant-hier"))

    guetteur = reveil.Guetteur(journal.racine)
    _verifier(
        guetteur.prompts() == [],
        "les prompts déjà écrits au démarrage ne remontent pas",
    )

    journal.ajouter(chemin, _prompt("celui de maintenant"))
    _verifier(
        guetteur.prompts() == [DOSSIER_TRAVAIL],
        "un prompt qui arrive remonte, avec son dossier de travail",
    )
    _verifier(guetteur.prompts() == [], "il ne remonte pas une seconde fois")


def verifier_le_bruit() -> None:
    journal = FauxJournal()
    chemin = journal.session()
    guetteur = reveil.Guetteur(journal.racine)

    journal.ajouter(chemin, _reponse(), _retour_d_outil(), _reponse())
    _verifier(
        guetteur.prompts() == [],
        "le travail de Claude Code ne réveille rien",
    )

    journal.ajouter(chemin, _retour_d_outil(), _prompt(), _reponse())
    _verifier(
        guetteur.prompts() == [DOSSIER_TRAVAIL],
        "un prompt noyé dans le bruit est retrouvé, et lui seul",
    )


def verifier_les_sessions_multiples() -> None:
    """Deux projets en parallèle : celui où l'on tape n'est pas le plus bavard."""
    journal = FauxJournal()
    bavarde = journal.session("bavarde")
    silencieuse = journal.session("silencieuse")
    guetteur = reveil.Guetteur(journal.racine)

    journal.ajouter(bavarde, *[_reponse() for _ in range(20)])
    journal.ajouter(silencieuse, _prompt(cwd="/autre/projet"))
    _verifier(
        guetteur.prompts() == ["/autre/projet"],
        "un prompt dans la session la moins active est vu quand même",
    )

    nouvelle = journal.session("ouverte-apres-nous")
    journal.ajouter(nouvelle, _prompt(cwd="/troisieme"))
    _verifier(
        guetteur.prompts() == ["/troisieme"],
        "une session ouverte après le démarrage est suivie dès sa première ligne",
    )


def verifier_les_ecritures_partielles() -> None:
    journal = FauxJournal()
    chemin = journal.session()
    guetteur = reveil.Guetteur(journal.racine)

    journal.ajouter(chemin, _prompt(), entiere=False)
    _verifier(
        guetteur.prompts() == [],
        "une ligne encore en cours d'écriture n'est pas lue à moitié",
    )

    with chemin.open("a", encoding="utf-8") as fichier:
        fichier.write("\n")
    os.utime(chemin, (time.time() + 2, time.time() + 2))
    _verifier(
        guetteur.prompts() == [DOSSIER_TRAVAIL],
        "elle est lue au tour suivant, une fois terminée",
    )

    journal.ajouter(chemin, {"pas": "du tout du JSON valide"})
    chemin.write_text(
        chemin.read_text(encoding="utf-8") + '{"type": "user", tronqué\n',
        encoding="utf-8",
    )
    journal.ajouter(chemin, _prompt(cwd="/apres/la/casse"))
    _verifier(
        guetteur.prompts() == ["/apres/la/casse"],
        "une ligne illisible est sautée sans emporter les suivantes",
    )


def verifier_les_disparitions() -> None:
    journal = FauxJournal()
    chemin = journal.session()
    journal.ajouter(chemin, _prompt("vieux"))
    guetteur = reveil.Guetteur(journal.racine)

    # Un journal qui rétrécit n'est plus le même : Claude Code n'écrit qu'en
    # ajoutant. On ne doit surtout pas repartir de zéro et tout rejouer.
    chemin.write_text("", encoding="utf-8")
    os.utime(chemin, (time.time() + 1, time.time() + 1))
    _verifier(guetteur.prompts() == [], "un journal remis à zéro ne rejoue rien")

    journal.ajouter(chemin, _prompt(cwd="/la/suite"))
    _verifier(
        guetteur.prompts() == ["/la/suite"],
        "et il est suivi de nouveau à partir de là",
    )

    chemin.unlink()
    _verifier(guetteur.prompts() == [], "un journal effacé ne fait pas lever")

    absente = reveil.Guetteur(Path(DOSSIER_TEST) / "aucun-claude-code-ici")
    _verifier(
        absente.prompts() == [],
        "une machine sans Claude Code ne fait pas lever non plus",
    )


def verifier_le_gros_volume() -> None:
    """Un retour d'outil énorme ne doit pas figer la fenêtre."""
    journal = FauxJournal()
    chemin = journal.session()
    guetteur = reveil.Guetteur(journal.racine)

    gros = {"type": "assistant", "message": {"content": "x" * (reveil.OCTETS_MAX * 2)}}
    journal.ajouter(chemin, gros)
    debut = time.perf_counter()
    guetteur.prompts()
    duree = time.perf_counter() - debut
    _verifier(
        duree < 0.5,
        f"un journal qui grossit d'un coup est traité en {duree * 1000:.0f} ms",
    )

    journal.ajouter(chemin, _prompt(cwd="/apres/le/gros"))
    _verifier(
        guetteur.prompts() == ["/apres/le/gros"],
        "le prompt qui suit un gros volume est vu normalement",
    )


# ----------------------------------------------------------------------
# Les vrais journaux de la machine
# ----------------------------------------------------------------------


def verifier_sur_les_vrais_journaux() -> None:
    """Confronte la forme attendue à celle que Claude Code écrit vraiment.

    En lecture seule, et sans rien exiger d'une machine qui n'aurait jamais
    lancé Claude Code.
    """
    racine = reveil.DOSSIER_SESSIONS
    if not racine.is_dir():
        _constats.append((True, "aucun journal réel sur cette machine : série sautée"))
        return

    guetteur = reveil.Guetteur(racine)
    debut = time.perf_counter()
    guetteur.prompts()
    duree = time.perf_counter() - debut
    _verifier(
        duree < 0.2,
        f"un relevé des vrais journaux prend {duree * 1000:.0f} ms (toutes les 2 s)",
    )

    journaux = sorted(
        racine.glob("*/*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True
    )[:5]
    humains = outils = 0
    manques = 0
    for chemin in journaux:
        for ligne in chemin.read_bytes().split(b"\n"):
            if not ligne.strip():
                continue
            try:
                evenement = json.loads(ligne)
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            if not isinstance(evenement, dict) or evenement.get("type") != "user":
                continue
            if reveil.est_un_prompt(evenement):
                humains += 1
                # Le filtre grossier du guetteur écarte les lignes sans
                # `"user"` avant de les analyser. S'il écartait un vrai prompt,
                # le réveil se tairait sans que rien ne le signale.
                if b'"user"' not in ligne:
                    manques += 1
            else:
                outils += 1

    _verifier(humains > 0, f"des prompts humains sont reconnus dans le vrai journal ({humains})")
    _verifier(outils > 0, f"des retours d'outils sont écartés dans le vrai journal ({outils})")
    _verifier(
        manques == 0,
        "le filtre rapide n'écarte aucun vrai prompt avant de l'analyser",
    )
    _verifier(
        humains < outils,
        "les prompts restent une minorité des lignes `user`, comme attendu",
    )


def main() -> int:
    verifier_le_reglage()
    verifier_la_reconnaissance()
    verifier_l_amorce()
    verifier_le_bruit()
    verifier_les_sessions_multiples()
    verifier_les_ecritures_partielles()
    verifier_les_disparitions()
    verifier_le_gros_volume()
    verifier_sur_les_vrais_journaux()

    for ok, description in _constats:
        print(f"{'  ok  ' if ok else 'ÉCHEC '} {description}")

    echecs = [description for ok, description in _constats if not ok]
    print()
    print(f"{len(_constats) - len(echecs)}/{len(_constats)} vérifications passées")
    return 1 if echecs else 0


if __name__ == "__main__":
    raise SystemExit(main())
