#!/usr/bin/env python3
"""Vérification de bout en bout : le repérage des fonctions et le cycle du panneau.

Le scénario suit le chemin réel : une session est détectée, une notification
part, l'utilisateur ouvre le panneau quand ça l'arrange, répond, lit le
retour, referme.

Le script se ferme tout seul et rend un code de sortie non nul si une des
vérifications échoue. Il ouvre le panneau à l'écran et prend le focus pendant
quelques secondes : c'est normal, il se sert de l'interface comme un
utilisateur.

    python verifier.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile

# Avant tout import du paquet : la vérification ne doit pas écrire dans
# l'historique réel.
DOSSIER_TEST = tempfile.mkdtemp(prefix="knowyourcode-verif-")
os.environ["KNOWYOURCODE_DOSSIER"] = DOSSIER_TEST

from PyQt6.QtCore import QTimer  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from connais_ton_code.application import (  # noqa: E402
    _autoriser_ctrl_c,
    _mode_barre_de_menus,
    attendre_les_evaluations,
    construire,
)
from connais_ton_code.etats import Etat  # noqa: E402
from connais_ton_code.extraction import fonctions  # noqa: E402

_constats: list[tuple[bool, str]] = []


def _verifier(condition: bool, description: str) -> None:
    _constats.append((bool(condition), description))


# Le repérage des fonctions TypeScript compte les accolades à la main : c'est
# la partie la plus facile à casser du projet, et la seule qui se vérifie sans
# interface.
_CAS_TYPESCRIPT = (
    (
        "un paramètre déstructuré ne coupe pas la fonction",
        """function Theme({
  enfants,
  ...reste
}: React.ComponentProps<typeof Fournisseur>) {
  return <Fournisseur {...reste}>{enfants}</Fournisseur>
}""",
    ),
    (
        "une contrainte générique en objet ne coupe pas la fonction",
        """export function trier<T extends { id: string }>(elements: T[]): T[] {
  const copie = [...elements];
  copie.sort((a, b) => a.id.localeCompare(b.id));
  return copie;
}""",
    ),
    (
        "une fléchée à un seul paramètre sans parenthèses est repérée",
        """const doubler = x => {
  const resultat = x * 2;
  return resultat;
};""",
    ),
    (
        "une fléchée rendant un objet va jusqu'à sa parenthèse",
        """export const config = (delai = 5) => ({
  delai,
  actif: true,
  libelle: "un } piege",
});""",
    ),
    (
        "une accolade dans une chaîne ne referme pas le bloc",
        """function piege() {
  const modele = "ceci { n'est pas } un bloc";
  return modele;
}""",
    ),
)


def verifier_extraction() -> None:
    """Contrôles sans interface, sur le repérage des fonctions."""
    for description, code in _CAS_TYPESCRIPT:
        trouvees = fonctions(code, "tsx")
        attendu = code.count("\n") + 1
        _verifier(
            len(trouvees) == 1 and trouvees[0].nombre_de_lignes == attendu,
            description,
        )

    python = '''def additionner(a, b):
    """Somme."""
    return a + b


def soustraire(a, b):
    return a - b
'''
    trouvees = fonctions(python, "python")
    _verifier(
        [f.nom for f in trouvees] == ["additionner", "soustraire"],
        "les fonctions Python sont repérées dans l'ordre du fichier",
    )


def main() -> int:
    verifier_extraction()

    application = QApplication(sys.argv)
    _mode_barre_de_menus()
    _autoriser_ctrl_c(application)

    # Les briques réelles dépendent du disque, du réseau et d'une session
    # Claude Code en cours : la vérification ne doit dépendre d'aucun des trois.
    orchestrateur = construire(application, factice=True)
    panneau = orchestrateur._panneau
    barre = orchestrateur._barre
    detecteur = orchestrateur._detecteur

    def _historique() -> list:
        journal = os.path.join(DOSSIER_TEST, "historique.json")
        if not os.path.exists(journal):
            return []
        with open(journal, encoding="utf-8") as fichier:
            return json.load(fichier).get("entrees", [])

    def _reglages() -> dict:
        fichier = os.path.join(DOSSIER_TEST, "reglages.json")
        if not os.path.exists(fichier):
            return {}
        with open(fichier, encoding="utf-8") as ouvert:
            return json.load(ouvert)

    def demarrage() -> None:
        _verifier(orchestrateur.etat() is Etat.FERME, "au démarrage, le panneau est fermé")
        _verifier(not panneau.isVisible(), "rien ne s'affiche au lancement")
        _verifier(barre.isVisible(), "l'icône de la barre de menus est en place")
        _verifier(orchestrateur.est_actif(), "la détection démarre à l'écoute")
        _verifier(
            "écoute" in barre.toolTip(), "l'infobulle annonce l'état à l'écoute"
        )
        detecteur.demander_question()

    def apres_detection() -> None:
        _verifier(
            orchestrateur.question_en_attente(),
            "une détection met une question en attente",
        )
        _verifier(
            orchestrateur.etat() is Etat.FERME,
            "la détection prévient sans ouvrir le panneau",
        )
        _verifier(not panneau.isVisible(), "la notification n'ouvre rien à l'écran")
        _verifier(
            "attend" in barre.toolTip(),
            "l'icône signale elle aussi la question en attente",
        )
        orchestrateur.ouvrir()

    def question() -> None:
        _verifier(
            orchestrateur.etat() is Etat.QUESTION,
            "ouvrir le panneau sert la question qui attendait",
        )
        _verifier(panneau.isVisible(), "le panneau est visible")
        _verifier(
            not orchestrateur.question_en_attente(),
            "la question en attente est consommée",
        )
        _verifier(
            "attend" not in barre.toolTip(),
            "l'icône cesse de signaler une attente",
        )
        _verifier(
            panneau._etiquette_fonction.text() != "",
            "le nom de la fonction est affiché",
        )
        _verifier(
            "<span" in panneau._zone_code.toHtml(),
            "le code est affiché avec coloration syntaxique",
        )
        _verifier(
            panneau.pos().y() < 60,
            "le panneau s'ouvre en haut, sous la barre de menus",
        )
        panneau._zone_reponse.setPlainText("Elle regroupe les évènements par jour.")
        panneau._bouton_repondre.click()

    def evaluation() -> None:
        _verifier(
            orchestrateur.etat() is Etat.EVALUATION,
            "la réponse fait passer en état Évaluation",
        )
        _verifier(panneau.isVisible(), "le panneau reste ouvert pendant l'évaluation")

    def retour() -> None:
        _verifier(
            orchestrateur.etat() is Etat.RETOUR, "l'évaluation aboutit à l'état Retour"
        )
        _verifier(len(_historique()) == 1, "la réponse est enregistrée dans l'historique")
        panneau._bouton_suivant.click()

    def repos() -> None:
        _verifier(orchestrateur.etat() is Etat.REPOS, "Suivant ramène au repos")
        _verifier(panneau.isVisible(), "le panneau reste ouvert au repos")
        panneau.fermeture_demandee.emit()

    def ferme() -> None:
        _verifier(orchestrateur.etat() is Etat.FERME, "la fermeture referme le panneau")
        _verifier(not panneau.isVisible(), "le panneau a bien disparu")
        _verifier(len(_historique()) == 1, "refermer n'enregistre rien de plus")
        panneau.activation_changee.emit(False)

    def en_pause() -> None:
        _verifier(not orchestrateur.est_actif(), "l'interrupteur met en pause")
        _verifier("pause" in barre.toolTip(), "l'infobulle annonce la pause")
        _verifier(
            _reglages().get("detection_active") is False,
            "la pause est écrite sur le disque",
        )
        detecteur.demander_question()

    def pause_sans_effet() -> None:
        _verifier(
            not orchestrateur.question_en_attente(),
            "en pause, une détection ne met rien en attente",
        )
        _verifier(orchestrateur.etat() is Etat.FERME, "en pause, rien ne s'ouvre")
        orchestrateur.ouvrir()

    def repos_en_pause() -> None:
        _verifier(
            orchestrateur.etat() is Etat.REPOS,
            "le panneau s'ouvre quand même à la demande",
        )
        _verifier(
            "pause" in panneau._message_repos.text().lower(),
            "le panneau dit que la détection est en pause",
        )
        panneau.question_demandee.emit()

    def question_manuelle() -> None:
        _verifier(
            orchestrateur.etat() is Etat.QUESTION,
            "en pause, on peut toujours demander une question",
        )
        panneau.activation_changee.emit(True)

    def fin() -> None:
        _verifier(orchestrateur.est_actif(), "l'interrupteur remet à l'écoute")
        _verifier(
            _reglages().get("detection_active") is True,
            "la reprise est écrite sur le disque",
        )
        application.quit()

    for delai, etape in (
        (600, demarrage),
        (1700, apres_detection),
        (2000, question),
        (2300, evaluation),
        (3500, retour),
        (3800, repos),
        (4100, ferme),
        (4400, en_pause),
        (5600, pause_sans_effet),
        (5900, repos_en_pause),
        (6200, question_manuelle),
        (6500, fin),
    ):
        QTimer.singleShot(delai, etape)

    application.exec()
    attendre_les_evaluations()

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
