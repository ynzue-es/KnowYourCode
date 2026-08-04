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
    attendre_les_evaluations,
    construire,
)
from connais_ton_code.etats import Etat  # noqa: E402
from connais_ton_code.extraction import fonctions  # noqa: E402
from connais_ton_code.historique import Historique  # noqa: E402
from connais_ton_code.modeles import EntreeHistorique  # noqa: E402
from connais_ton_code import rappel  # noqa: E402
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


def _entree(
    identifiant: str,
    chemin: str,
    nom: str,
    langage: str,
    date: datetime,
    issue: str,
    score: int | None = None,
    points_oublies: tuple[str, ...] = (),
) -> EntreeHistorique:
    """Construit une entrée d'historique à la main, pour les contrôles de calcul."""
    return EntreeHistorique(
        identifiant=identifiant,
        chemin_fichier=chemin,
        nom_fonction=nom,
        langage=langage,
        date=date,
        issue=issue,
        score=score,
        verdict="verdict" if issue == "repondu" else None,
        reponse="une réponse" if issue == "repondu" else None,
        points_oublies=list(points_oublies),
    )


def verifier_statistiques() -> None:
    """Contrôles sans interface, sur le calcul des statistiques de progression.

    L'historique est construit à la main plutôt que rejoué depuis un fichier :
    c'est le calcul qu'on vérifie ici, pas la lecture du disque. Deux langages,
    des passages, et une même fonction posée deux fois, pour couvrir le
    groupement et pas seulement la moyenne.
    """
    t1 = datetime(2024, 1, 1, 9, 0, tzinfo=timezone.utc)
    t2 = datetime(2024, 1, 2, 9, 0, tzinfo=timezone.utc)
    t3 = datetime(2024, 1, 3, 9, 0, tzinfo=timezone.utc)
    t4 = datetime(2024, 1, 4, 9, 0, tzinfo=timezone.utc)
    t5 = datetime(2024, 1, 5, 9, 0, tzinfo=timezone.utc)
    t6 = datetime(2024, 1, 6, 9, 0, tzinfo=timezone.utc)

    entrees = [
        _entree("fct-a", "src/a.py", "additionner", "python", t1, "repondu", 40, ("l'edge case b=0",)),
        _entree("fct-b", "src/b.ts", "trierListe", "typescript", t2, "repondu", 90),
        _entree("fct-c", "src/c.py", "diviser", "python", t3, "passe"),
        _entree("fct-a", "src/a.py", "additionner", "python", t4, "repondu", 60, ("la division par zéro",)),
        _entree("fct-d", "src/d.ts", "formater", "typescript", t5, "repondu", 70, ("le fuseau horaire",)),
        _entree("fct-e", "src/e.py", "filtrer", "python", t6, "passe"),
    ]

    statistiques = calculer_statistiques(entrees)

    _verifier(
        statistiques.nombre_de_questions == 6, "le nombre de questions compte toutes les entrées"
    )
    _verifier(
        statistiques.nombre_de_reponses == 4, "le nombre de réponses écarte les passages"
    )
    _verifier(
        statistiques.nombre_de_passages == 2, "le nombre de passages écarte les réponses"
    )
    _verifier(
        statistiques.score_moyen == 65.0, "la moyenne générale ne porte que sur les réponses"
    )
    _verifier(
        statistiques.score_moyen_recent == 65.0,
        "en dessous du seuil des dix dernières, la moyenne récente vaut la moyenne générale",
    )
    _verifier(
        statistiques.scores_recents == [40, 90, 60, 70],
        "les scores récents suivent l'ordre chronologique, le plus ancien d'abord",
    )
    _verifier(
        [f.identifiant for f in statistiques.fonctions_mal_expliquees]
        == ["fct-a", "fct-d", "fct-b"],
        "les fonctions mal expliquées sont triées du pire score moyen au meilleur",
    )
    _verifier(
        statistiques.fonctions_mal_expliquees[0].nombre_de_fois == 2,
        "une même fonction posée deux fois se regroupe au lieu de se dédoubler",
    )
    _verifier(
        statistiques.fonctions_mal_expliquees[0].score_moyen == 50.0,
        "le score moyen d'une fonction posée deux fois moyenne ses deux réponses",
    )
    _verifier(
        [o.point for o in statistiques.oublis_recents]
        == ["le fuseau horaire", "la division par zéro", "l'edge case b=0"],
        "les oublis récents remontent du plus récent au plus ancien",
    )
    _verifier(
        [
            (l.langage, l.nombre_de_reponses, l.score_moyen)
            for l in statistiques.repartition_par_langage
        ]
        == [("python", 2, 50.0), ("typescript", 2, 80.0)],
        "la répartition par langage distingue Python et TypeScript",
    )
    _verifier(
        statistiques.derniere_reponse == t5,
        "la dernière réponse retient la date de la plus récente, pas de la dernière entrée",
    )

    vide = calculer_statistiques([])
    _verifier(
        vide.nombre_de_questions == 0
        and vide.nombre_de_reponses == 0
        and vide.nombre_de_passages == 0
        and vide.score_moyen == 0.0
        and vide.score_moyen_recent == 0.0
        and vide.scores_recents == []
        and vide.fonctions_mal_expliquees == []
        and vide.oublis_recents == []
        and vide.repartition_par_langage == []
        and vide.derniere_reponse is None,
        "un historique vide rend des statistiques neutres sans lever d'exception",
    )


def verifier_regularite() -> None:
    """Contrôles sur la série, la tendance et le calendrier.

    Ces trois calculs dépendent de la date du jour : elle est passée en
    paramètre, sinon la vérification changerait de résultat à minuit.
    """
    jour = date(2026, 8, 5)

    def le(jour_du_mois: int, score: int) -> EntreeHistorique:
        return _entree(
            "id", "a.py", "f", "python",
            datetime(2026, 8, jour_du_mois, 10, tzinfo=timezone.utc),
            "repondu", score,
        )

    suite = calculer_statistiques([le(3, 50), le(4, 60), le(5, 70)], aujourdhui=jour)
    _verifier(suite.serie_en_cours == 3, "trois jours d'affilée font une série de trois")

    trou = calculer_statistiques([le(1, 50), le(3, 60), le(5, 70)], aujourdhui=jour)
    _verifier(trou.serie_en_cours == 1, "un jour manquant casse la série")

    ancienne = calculer_statistiques([le(1, 50), le(2, 60)], aujourdhui=jour)
    _verifier(
        ancienne.serie_en_cours == 0,
        "une série finie il y a plusieurs jours ne compte plus",
    )

    veille = calculer_statistiques([le(3, 50), le(4, 60)], aujourdhui=jour)
    _verifier(
        veille.serie_en_cours == 2,
        "une série qui s'arrête hier compte encore, la journée n'est pas finie",
    )

    courte = calculer_statistiques([le(4, 50), le(5, 60)], aujourdhui=jour)
    _verifier(
        courte.tendance is None,
        "sans deux paquets complets, aucune tendance n'est affichée",
    )

    dix = [le(1, 40)] * 5 + [le(5, 80)] * 5
    _verifier(
        calculer_statistiques(dix, aujourdhui=jour).tendance == 40.0,
        "la tendance compare les cinq dernières aux cinq précédentes",
    )

    calendrier = calculer_statistiques([le(5, 70), le(5, 80)], aujourdhui=jour)
    _verifier(
        len(calendrier.activite) == 84,
        "le calendrier couvre douze semaines, jours vides compris",
    )
    _verifier(
        calendrier.activite[-1].jour == jour and calendrier.activite[-1].nombre == 2,
        "le dernier jour du calendrier est aujourd'hui, avec son compte",
    )

    tranches = calculer_statistiques(
        [le(5, 10), le(5, 45), le(5, 65), le(5, 95), le(5, 100)], aujourdhui=jour
    ).repartition_scores
    _verifier(
        [t.nombre for t in tranches] == [1, 1, 1, 2],
        "chaque note tombe dans sa tranche, cent compris",
    )

    vide = calculer_statistiques([], aujourdhui=jour)
    _verifier(
        vide.serie_en_cours == 0
        and vide.tendance is None
        and vide.meilleur_score == 0
        and len(vide.activite) == 84,
        "un historique vide rend des valeurs neutres sans lever",
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


def main() -> int:
    verifier_extraction()
    verifier_statistiques()
    verifier_lecture_historique()
    verifier_rappel()
    verifier_regularite()

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

    def question() -> None:
        _verifier(
            orchestrateur.etat() is Etat.QUESTION,
            "demander une question l'affiche",
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
        # Une réponse vient d'être enregistrée : c'est le bon moment pour
        # vérifier que la grande fenêtre a quelque chose à montrer.
        panneau.fenetre_demandee.emit()

    def grande_fenetre() -> None:
        fenetre = orchestrateur._fenetre
        _verifier(fenetre.isVisible(), "l'icône du panneau ouvre la grande fenêtre")
        _verifier(
            orchestrateur.etat() is Etat.REPOS,
            "la grande fenêtre n'interrompt pas le cycle de l'exercice",
        )
        _verifier(panneau.isVisible(), "le panneau reste ouvert derrière elle")
        fenetre.close()
        panneau.question_demandee.emit()

    def apres_tableau() -> None:
        _verifier(
            orchestrateur.etat() is Etat.QUESTION,
            "après la grande fenêtre, on revient à une question",
        )
        _verifier(panneau.isVisible(), "le panneau reste ouvert en revenant à la question")
        panneau._bouton_passer.click()

    def apres_passage() -> None:
        _verifier(
            orchestrateur.etat() is Etat.REPOS, "passer la question ramène de nouveau au repos"
        )
        _verifier(
            len(_historique()) == 2, "le passage est lui aussi enregistré dans l'historique"
        )
        panneau.fermeture_demandee.emit()

    def ferme() -> None:
        _verifier(orchestrateur.etat() is Etat.FERME, "la fermeture referme le panneau")
        _verifier(not panneau.isVisible(), "le panneau a bien disparu")
        _verifier(len(_historique()) == 2, "refermer n'enregistre rien de plus")

    def fin() -> None:
        _verifier(
            orchestrateur.etat() is Etat.FERME,
            "le panneau reste fermé jusqu'au prochain clic",
        )
        application.quit()

    for delai, etape in (
        (600, demarrage),
        (900, repos_initial),
        (1200, question),
        (1500, evaluation),
        (3400, retour),
        (3700, repos),
        (3900, grande_fenetre),
        (4100, apres_tableau),
        (4300, apres_passage),
        (4600, ferme),
        (4900, fin),
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
