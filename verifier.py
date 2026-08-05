#!/usr/bin/env python3
"""Vérification de bout en bout : le repérage des fonctions et le cycle du panneau.

Le scénario suit le chemin réel : une session est détectée, une notification
part, l'utilisateur ouvre le panneau quand ça l'arrange, répond, lit le
retour, consulte le tableau de bord, referme.

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
from datetime import date, datetime, timezone
from pathlib import Path

# Avant tout import du paquet : la vérification ne doit pas écrire dans
# l'historique réel.
DOSSIER_TEST = tempfile.mkdtemp(prefix="knowyourcode-verif-")
os.environ["KNOWYOURCODE_DOSSIER"] = DOSSIER_TEST

from PyQt6.QtCore import QTimer  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from connais_ton_code.application import (  # noqa: E402
    _autoriser_ctrl_c,
    _mode_barre_de_menus,
    attendre_les_fabrications,
    construire,
)
from connais_ton_code.cartes import Forme  # noqa: E402
from connais_ton_code.etats import Etat  # noqa: E402
from connais_ton_code.extraction import fonctions  # noqa: E402
from connais_ton_code.historique import Historique  # noqa: E402
from connais_ton_code.modeles import EntreeHistorique  # noqa: E402
from connais_ton_code import rappel  # noqa: E402
from connais_ton_code.reperage import notion_reconnue, reperer  # noqa: E402
from connais_ton_code.statistiques import calculer_statistiques  # noqa: E402

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


# Chaque cas donne le fragment attendu sur la ligne arrivée en tête, ou `None`
# quand la bonne réponse est de ne rien signaler. Ce dernier point compte
# autant que les autres : le repérage n'a d'intérêt que s'il se tait sur du
# code ordinaire.
_CAS_REPERAGE: tuple[tuple[str, str, str, str | None], ...] = (
    (
        "une valeur par défaut mutable est signalée",
        "python",
        "def ajouter(element, seau=[]):\n    seau.append(element)\n    return seau\n",
        "seau=[]",
    ),
    (
        "shell=True est signalé",
        "python",
        "def lancer(nom):\n"
        "    import subprocess\n"
        "    return subprocess.run(f'ls {nom}', shell=True)\n",
        "shell=True",
    ),
    (
        "une requête SQL assemblée à la main est signalée",
        "python",
        "def chercher(curseur, nom):\n"
        '    curseur.execute(f"SELECT * FROM gens WHERE nom = \'{nom}\'")\n'
        "    return curseur.fetchall()\n",
        "SELECT",
    ),
    (
        "un assert servant de garde est signalé",
        "python",
        "def payer(montant):\n    assert montant > 0\n    return montant * 2\n",
        "assert",
    ),
    (
        "le else d'une boucle est montré sur son mot-clé",
        "python",
        "def chercher(elements, cible):\n"
        "    for element in elements:\n"
        "        if element == cible:\n"
        "            break\n"
        "    else:\n"
        "        return None\n"
        "    return element\n",
        "else:",
    ),
    (
        "un commentaire ne déplace pas le finally",
        "python",
        "def lire(chemin):\n"
        "    fichier = open(chemin)\n"
        "    try:\n"
        "        return fichier.read()\n"
        "    finally:\n"
        "        # on ferme quoi qu'il arrive\n"
        "        fichier.close()\n",
        "finally:",
    ),
    (
        "la capture tardive dans une boucle est signalée",
        "python",
        "def fabriquer(nombres):\n"
        "    sorties = []\n"
        "    for nombre in nombres:\n"
        "        sorties.append(lambda: nombre * 2)\n"
        "    return sorties\n",
        "lambda",
    ),
    (
        "un except nu est signalé",
        "python",
        "def lire(chemin):\n"
        "    try:\n"
        "        return open(chemin).read()\n"
        "    except:\n"
        "        return ''\n",
        "except:",
    ),
    (
        "le or de repli est signalé, celui de condition non",
        "python",
        "def saluer(saisie, poli):\n"
        "    if saisie or poli:\n"
        "        pass\n"
        "    nom = saisie or 'anonyme'\n"
        "    return nom\n",
        "'anonyme'",
    ),
    (
        "un is not None ordinaire ne déclenche rien",
        "python",
        "def valeur(entree):\n"
        "    if entree is not None:\n"
        "        return entree\n"
        "    return 0\n",
        None,
    ),
    (
        "une clé de liste prise sur la position est signalée",
        "tsx",
        "export function Liste({ elements }: Props) {\n"
        "  return (\n"
        "    <ul>\n"
        "      {elements.map((e, index) => (\n"
        "        <li key={index}>{e.libelle}</li>\n"
        "      ))}\n"
        "    </ul>\n"
        "  );\n"
        "}\n",
        "key={index}",
    ),
    (
        "le double égal est signalé, le triple non",
        "typescript",
        "export function memes(a: unknown, b: unknown) {\n"
        "  const pareil = a == b;\n"
        "  return pareil;\n"
        "}\n",
        "a == b",
    ),
    (
        "un await pris dans une boucle est signalé",
        "typescript",
        "export async function toutCharger(ids: string[]) {\n"
        "  const sortie = [];\n"
        "  for (const id of ids) {\n"
        "    sortie.push(await charger(id));\n"
        "  }\n"
        "  return sortie;\n"
        "}\n",
        "await charger",
    ),
    (
        "dangerouslySetInnerHTML est signalé",
        "tsx",
        "export function Brut({ html }: Props) {\n"
        "  return <div dangerouslySetInnerHTML={{ __html: html }} />;\n"
        "}\n",
        "dangerouslySetInnerHTML",
    ),
)


def verifier_reperage() -> None:
    """Contrôles sur le choix des lignes qui méritent une question.

    C'est la brique dont dépendent toutes les cartes : une ligne mal désignée
    devient une leçon fausse, et une leçon fausse est pire que pas de leçon.
    """
    for description, langage, code, attendu in _CAS_REPERAGE:
        reperes = reperer(code, langage)
        lignes = code.splitlines()
        if attendu is None:
            _verifier(not reperes, description)
        else:
            _verifier(
                bool(reperes) and attendu in lignes[reperes[0].ligne - 1],
                description,
            )

    for saisie, notion, attendu in (
        ("Closures", "fermeture", True),
        ("  CLÔTURE ", "fermeture", True),
        ("décorateurs", "décorateur", True),
        ("memoization", "mémoïsation", True),
        ("boucle", "fermeture", False),
        ("", "fermeture", False),
    ):
        _verifier(
            notion_reconnue(saisie, notion) is attendu,
            f"« {saisie.strip() or 'rien' } » {'vaut' if attendu else 'ne vaut pas'} "
            f"« {notion} »",
        )


def verifier_rappel() -> None:
    """Contrôles sans interface sur le rappel posé dans Claude Code.

    Ce module écrit dans le fichier de réglages personnels de l'utilisateur :
    la moindre erreur lui ferait perdre sa configuration. Les contrôles
    portent donc autant sur ce qui doit être conservé que sur ce qui change,
    et travaillent sur une copie.
    """
    faux = Path(tempfile.mkdtemp(prefix="knowyourcode-reglages-")) / "settings.json"
    faux.write_text(
        json.dumps({"theme": "auto", "effortLevel": "high"}), encoding="utf-8"
    )

    _verifier(not rappel.est_installe(faux), "au départ, le rappel n'est pas posé")
    _verifier(rappel.installer(faux), "poser le rappel réussit")
    _verifier(rappel.est_installe(faux), "le rappel posé est reconnu")

    apres = json.loads(faux.read_text(encoding="utf-8"))
    _verifier(
        apres.get("theme") == "auto" and apres.get("effortLevel") == "high",
        "poser le rappel conserve les réglages personnels",
    )
    _verifier(
        apres["spinnerVerbs"]["mode"] == "replace",
        "le rappel remplace les verbes plutôt que de s'y ajouter",
    )
    _verifier(
        len(apres["spinnerVerbs"]["verbs"]) == len(rappel.phrases()),
        "toutes les phrases sont posées",
    )

    _verifier(rappel.retirer(faux), "retirer le rappel réussit")
    apres = json.loads(faux.read_text(encoding="utf-8"))
    _verifier("spinnerVerbs" not in apres, "le retrait efface le bloc")
    _verifier(
        apres.get("theme") == "auto",
        "le retrait conserve lui aussi les réglages personnels",
    )

    absent = Path(tempfile.mkdtemp(prefix="knowyourcode-vide-")) / "inexistant.json"
    _verifier(
        not rappel.est_installe(absent),
        "un fichier de réglages absent ne fait pas tomber la lecture",
    )
    _verifier(
        not rappel.installer(absent),
        "poser le rappel sur un fichier absent échoue sans lever",
    )


def verifier_lecture_historique() -> None:
    """Contrôles sans interface, sur la tolérance de l'historique aux lignes invalides.

    Le fichier sur disque peut porter les traces d'une écriture interrompue ou
    d'un format plus ancien : une ligne pareille doit être écartée, pas faire
    tomber toute la lecture.
    """
    chemin = Path(DOSSIER_TEST) / "historique_corrompu.json"
    brut = {
        "version": 1,
        "entrees": [
            {
                "identifiant": "ok-1",
                "chemin_fichier": "a.py",
                "nom_fonction": "f",
                "langage": "python",
                "issue": "repondu",
                "date": "2024-01-01T10:00:00+00:00",
                "score": 80,
                "verdict": "bien",
                "points_oublies": [],
            },
            {
                "identifiant": "ok-2",
                "chemin_fichier": "b.py",
                "nom_fonction": "g",
                "langage": "python",
                "issue": "passe",
                "date": "2024-01-02T10:00:00+00:00",
            },
            # Une écriture interrompue : les champs obligatoires manquent.
            {"identifiant": "corrompu", "chemin_fichier": "c.py"},
            # Un format plus ancien, avant le renommage des champs.
            {"identifiant": "ancien-format", "fonction": "h", "date": "2024-01-03T10:00:00+00:00"},
            # Une ligne qui n'est même pas un objet.
            "une chaîne au lieu d'une entrée",
        ],
    }
    with open(chemin, "w", encoding="utf-8") as fichier:
        json.dump(brut, fichier)

    lues = Historique(chemin=chemin).entrees()
    _verifier(
        {entree.identifiant for entree in lues} == {"ok-1", "ok-2"},
        "une entrée corrompue ou d'un ancien format est ignorée sans faire tomber la lecture",
    )


def _reponse_juste(carte) -> str:
    """Ce qu'il faut répondre pour tomber juste, dans la forme que le panneau émet.

    Distinct de `bonne_reponse`, qui rend de quoi *afficher* la réponse :
    « ligne 7 » se lit bien mais ne s'émet pas.
    """
    if carte.forme in (Forme.QCM, Forme.VRAI_FAUX):
        return carte.options[carte.bonne]
    if carte.forme is Forme.REPERER:
        return str(carte.bonne)
    return carte.notion or (carte.attendu[0] if carte.attendu else "")


def main() -> int:
    verifier_extraction()
    verifier_reperage()
    verifier_lecture_historique()
    verifier_rappel()

    application = QApplication(sys.argv)
    _mode_barre_de_menus()
    _autoriser_ctrl_c(application)

    # Les briques réelles dépendent du disque, du réseau et d'une session
    # Claude Code en cours : la vérification ne doit dépendre d'aucun des trois.
    orchestrateur = construire(application, factice=True)
    panneau = orchestrateur._panneau
    barre = orchestrateur._barre

    def _historique() -> list:
        journal = os.path.join(DOSSIER_TEST, "historique.json")
        if not os.path.exists(journal):
            return []
        with open(journal, encoding="utf-8") as fichier:
            return json.load(fichier).get("entrees", [])

    def demarrage() -> None:
        _verifier(orchestrateur.etat() is Etat.FERME, "au démarrage, le panneau est fermé")
        _verifier(not panneau.isVisible(), "rien ne s'affiche au lancement")
        _verifier(barre.isVisible(), "l'icône de la barre de menus est en place")
        orchestrateur.ouvrir()

    def repos_initial() -> None:
        _verifier(
            orchestrateur.etat() is Etat.REPOS,
            "un clic sur l'icône ouvre le panneau au repos",
        )
        _verifier(panneau.isVisible(), "le panneau est visible")
        panneau.question_demandee.emit()

    # La série se joue en suivant l'état, pas l'horloge : la fabrication passe
    # par un fil secondaire, et son temps de retour ne se prédit pas. Un
    # scénario minuté à la milliseconde près aurait échoué au hasard.
    compte = {"cartes": 0, "repondues": 0, "premiere": True}

    def jouer_la_serie() -> None:
        etat = orchestrateur.etat()

        if etat is Etat.PREPARATION:
            _verifier(panneau.isVisible(), "le panneau reste ouvert pendant la fabrication")
            return

        if etat is Etat.QUESTION:
            serie = orchestrateur._serie
            if serie is None:
                return
            if compte["premiere"]:
                compte["premiere"] = False
                compte["cartes"] = len(serie.cartes)
                _verifier(compte["cartes"] > 0, "la série apporte au moins une carte")
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
            panneau.reponse_donnee.emit(
                _reponse_juste(serie.cartes[orchestrateur._index])
            )
            compte["repondues"] += 1
            return

        if etat is Etat.RETOUR:
            _verifier(
                len(_historique()) == compte["repondues"],
                f"la carte {compte['repondues']} est enregistrée aussitôt répondue",
            )
            panneau.suite_demandee.emit()
            return

        if etat is Etat.BILAN:
            minuteur.stop()
            bilan()

    def bilan() -> None:
        _verifier(
            compte["repondues"] == compte["cartes"],
            "la série va jusqu'à sa dernière carte, puis s'arrête",
        )
        _verifier(
            len(_historique()) == compte["cartes"],
            "chaque carte laisse une trace, une et une seule",
        )
        _verifier(panneau.isVisible(), "le panneau reste ouvert sur le bilan")
        # Une série vient d'être jouée : c'est le bon moment pour vérifier que
        # la grande fenêtre a quelque chose à montrer.
        panneau.fenetre_demandee.emit()
        QTimer.singleShot(200, grande_fenetre)

    def grande_fenetre() -> None:
        fenetre = orchestrateur._fenetre
        _verifier(fenetre.isVisible(), "l'icône du panneau ouvre la grande fenêtre")
        _verifier(
            orchestrateur.etat() is Etat.BILAN,
            "la grande fenêtre n'interrompt pas le cycle de l'exercice",
        )
        _verifier(panneau.isVisible(), "le panneau reste ouvert derrière elle")
        fenetre.close()
        panneau.question_demandee.emit()
        QTimer.singleShot(900, apres_tableau)

    def apres_tableau() -> None:
        _verifier(
            orchestrateur.etat() is Etat.QUESTION,
            "après la grande fenêtre, on revient à une série",
        )
        _verifier(panneau.isVisible(), "le panneau reste ouvert en revenant à la carte")
        avant = len(_historique())
        panneau.passage_demande.emit()
        QTimer.singleShot(200, lambda: apres_passage(avant))

    def apres_passage(avant: int) -> None:
        _verifier(
            orchestrateur.etat() is Etat.REPOS,
            "laisser la série de côté ramène au repos",
        )
        _verifier(
            len(_historique()) == avant + 1,
            "l'abandon est lui aussi enregistré dans l'historique",
        )
        compte["apres_passage"] = len(_historique())
        panneau.fermeture_demandee.emit()
        QTimer.singleShot(200, ferme)

    def ferme() -> None:
        _verifier(orchestrateur.etat() is Etat.FERME, "la fermeture referme le panneau")
        _verifier(not panneau.isVisible(), "le panneau a bien disparu")
        _verifier(
            len(_historique()) == compte["apres_passage"],
            "refermer n'enregistre rien de plus",
        )
        QTimer.singleShot(300, fin)

    def fin() -> None:
        _verifier(
            orchestrateur.etat() is Etat.FERME,
            "le panneau reste fermé jusqu'au prochain clic",
        )
        application.quit()

    minuteur = QTimer()
    minuteur.setInterval(150)
    minuteur.timeout.connect(jouer_la_serie)

    QTimer.singleShot(600, demarrage)
    QTimer.singleShot(900, repos_initial)
    QTimer.singleShot(1200, minuteur.start)
    # Un filet : si la série se bloque, on ne veut pas d'un script qui ne
    # rend jamais la main. Les constats manquants feront échouer le compte.
    QTimer.singleShot(30_000, application.quit)

    application.exec()
    attendre_les_fabrications()

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
