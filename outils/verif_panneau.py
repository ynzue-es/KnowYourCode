#!/usr/bin/env python3
"""Vérification du panneau : une série de cartes, posée et corrigée à l'écran.

Le scénario suit le chemin réel d'un utilisateur : il ouvre le panneau, part
sur une série, répond carte après carte, lit l'explication, arrive au bilan,
en relance une, et referme. La série est écrite en dur et couvre les cinq
formes ; elle est jouée deux fois, une fois toute juste et une fois toute
fausse, parce que le retour en cas d'erreur est justement ce qui compte.

Le script se ferme tout seul et rend un code de sortie non nul si une des
vérifications échoue. Il ouvre le panneau à l'écran et prend le focus pendant
quelques secondes : c'est normal, il se sert de l'interface comme un
utilisateur.

    python outils/verif_panneau.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from functools import partial
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))

# Avant tout import du paquet : la vérification ne doit pas écrire dans
# l'historique réel.
DOSSIER_TEST = tempfile.mkdtemp(prefix="knowyourcode-verif-panneau-")
os.environ["KNOWYOURCODE_DOSSIER"] = DOSSIER_TEST

from PyQt6.QtCore import QPoint, Qt, QTimer  # noqa: E402
from PyQt6.QtGui import QTextCursor  # noqa: E402
from PyQt6.QtTest import QTest  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from connais_ton_code.apparence import appliquer_theme_sombre  # noqa: E402
from connais_ton_code.application import (  # noqa: E402
    _autoriser_ctrl_c,
    _mode_barre_de_menus,
)
from connais_ton_code.barre_menu import BarreMenu  # noqa: E402
from connais_ton_code.cartes import Carte, Forme, Serie  # noqa: E402
from connais_ton_code.etats import Etat, transition_valide  # noqa: E402
from connais_ton_code.fenetre_principale import FenetrePrincipale  # noqa: E402
from connais_ton_code.historique import Historique  # noqa: E402
from connais_ton_code.modeles import Extrait  # noqa: E402
from connais_ton_code.orchestrateur import Orchestrateur  # noqa: E402
from connais_ton_code.panneau import Panneau  # noqa: E402
from connais_ton_code.projet import ProjetFactice  # noqa: E402
from connais_ton_code.selecteur import SelecteurFactice  # noqa: E402

_constats: list[tuple[bool, str]] = []


def _verifier(condition: bool, description: str) -> None:
    _constats.append((bool(condition), description))


# ----------------------------------------------------------------------
# L'extrait et sa série, écrits à la main
# ----------------------------------------------------------------------

EXTRAIT = Extrait(
    identifiant="verif:agregation.py:regrouper_par_jour",
    chemin_fichier="services/agregation.py",
    nom_fonction="regrouper_par_jour",
    langage="python",
    code='''def regrouper_par_jour(evenements, fuseau="Europe/Paris"):
    zone = ZoneInfo(fuseau)
    par_jour = defaultdict(list)

    for evenement in sorted(evenements, key=lambda e: e.horodatage):
        locale = evenement.horodatage.astimezone(zone)
        if locale.hour < 4:
            locale -= timedelta(days=1)
        par_jour[locale.date()].append(evenement)

    return {jour: tuple(liste) for jour, liste in sorted(par_jour.items())}
''',
)

NOMBRE_DE_LIGNES = 11

CARTES: tuple[Carte, ...] = (
    Carte(
        forme=Forme.QCM,
        question="Ligne 5, pourquoi trier avant de boucler ?",
        reponse="Pour que les journées se remplissent dans l'ordre",
        explication=(
            "Le regroupement lui-même n'a pas besoin d'ordre : un dictionnaire "
            "accepterait les évènements en vrac. Le tri sert aux listes "
            "rangées derrière chaque date, qui ressortent chronologiques sans "
            "qu'on ait à les retrier une par une."
        ),
        options=(
            "Pour que les journées se remplissent dans l'ordre",
            "Pour supprimer les doublons",
            "Parce que defaultdict l'exige",
            "Pour accélérer la conversion de fuseau",
        ),
        ligne=5,
    ),
    Carte(
        forme=Forme.VRAI_FAUX,
        question="Ligne 8 : cette soustraction modifie l'évènement d'origine.",
        reponse="Faux",
        explication=(
            "`locale` est une variable locale, obtenue par conversion : la "
            "réassigner ne touche pas à `evenement.horodatage`. C'est ce qui "
            "permet de décaler la journée sans réécrire les données lues."
        ),
        options=("Vrai", "Faux"),
        ligne=8,
    ),
    Carte(
        forme=Forme.REPERER,
        question="Quelle ligne rattache une session nocturne à la veille ?",
        reponse="7",
        explication=(
            "La journée d'usage commence à quatre heures du matin : en deçà, "
            "on est encore dans la soirée de la veille. Le test est la seule "
            "ligne à porter cette convention ; la ligne suivante ne fait "
            "qu'appliquer le décalage qu'elle a décidé."
        ),
        ligne=0,
    ),
    Carte(
        forme=Forme.PREDIRE,
        question="Ligne 11 : quel type prend chaque valeur du dictionnaire rendu ?",
        reponse="tuple",
        explication=(
            "Les listes accumulées pendant la boucle sont figées en tuples au "
            "moment de rendre le résultat. L'appelant repart donc avec quelque "
            "chose qu'il ne peut pas modifier par mégarde."
        ),
        variantes=("tuples", "un tuple"),
        ligne=11,
    ),
    Carte(
        forme=Forme.NOMMER,
        question="Ligne 3 : comment s'appelle ce dictionnaire à valeur par défaut ?",
        reponse="defaultdict",
        explication=(
            "`defaultdict(list)` fabrique la liste manquante à la première "
            "visite d'une date. C'est ce qui permet à la ligne 9 d'appeler "
            "`append` sans avoir jamais créé la journée."
        ),
        ligne=3,
    ),
)

TOTAL = len(CARTES)


class GenerateurFige:
    """Rend toujours la même série, quel que soit l'extrait reçu.

    Programme contre le contrat du vrai générateur : `fabriquer(extrait)`
    rend une `Serie` ou `None`.
    """

    def fabriquer(self, extrait: Extrait) -> Serie | None:
        return Serie(extrait=extrait, cartes=CARTES)


# ----------------------------------------------------------------------
# Les gestes de réponse, un par forme
# ----------------------------------------------------------------------


def _mauvaise_option(carte: Carte) -> str:
    return next(option for option in carte.options if option != carte.reponse)


def _cliquer_option(panneau: Panneau, texte: str) -> bool:
    for bouton in panneau._boutons_options:
        if bouton.text() == texte:
            bouton.click()
            return True
    return False


def _cliquer_ligne(panneau: Panneau, ligne: int) -> bool:
    """Clique vraiment dans le code, à la souris, comme le ferait la main."""
    zone = panneau._zone_code
    bloc = zone.document().findBlockByNumber(ligne - 1)
    if not bloc.isValid():
        return False
    rectangle = zone.cursorRect(QTextCursor(bloc))
    point = QPoint(rectangle.center().x() + 24, rectangle.center().y())
    QTest.mouseClick(zone.viewport(), Qt.MouseButton.LeftButton, pos=point)
    return True


def _repondre(panneau: Panneau, carte: Carte, juste: bool) -> bool:
    if carte.forme in (Forme.QCM, Forme.VRAI_FAUX):
        return _cliquer_option(
            panneau, carte.reponse if juste else _mauvaise_option(carte)
        )
    if carte.forme is Forme.REPERER:
        attendue = int(carte.reponse)
        return _cliquer_ligne(panneau, attendue if juste else attendue - 5)
    panneau._champ_mot.setText(carte.reponse if juste else "pasdutout")
    panneau._bouton_valider.click()
    return True


def _page_attendue(carte: Carte) -> int:
    if carte.forme in (Forme.QCM, Forme.VRAI_FAUX):
        return 0
    return 1 if carte.forme is Forme.REPERER else 2


def main() -> int:
    application = QApplication(sys.argv)
    _mode_barre_de_menus()
    _autoriser_ctrl_c(application)
    appliquer_theme_sombre()

    panneau = Panneau()
    fenetre = FenetrePrincipale()
    barre = BarreMenu(application)
    barre.show()

    orchestrateur = Orchestrateur(
        panneau=panneau,
        fenetre=fenetre,
        barre=barre,
        projet=ProjetFactice(),
        selecteur=SelecteurFactice(extraits=(EXTRAIT,)),
        generateur=GenerateurFige(),
        historique=Historique(),
        parent=application,
    )
    application.setQuitOnLastWindowClosed(False)

    def demarrage() -> None:
        _verifier(
            orchestrateur.etat() is Etat.FERME, "au démarrage, le panneau est fermé"
        )
        _verifier(not panneau.isVisible(), "rien ne s'affiche au lancement")
        _verifier(barre.isVisible(), "l'icône de la barre de menus est en place")
        _verifier(
            not hasattr(Etat, "EVALUATION"),
            "l'état d'évaluation a disparu du cycle avec l'attente réseau",
        )
        orchestrateur.ouvrir()

    def repos_initial() -> None:
        _verifier(
            orchestrateur.etat() is Etat.REPOS,
            "un clic sur l'icône ouvre le panneau au repos",
        )
        _verifier(panneau.isVisible(), "le panneau est visible")
        panneau.question_demandee.emit()

    def carte(numero: int, juste: bool) -> None:
        modele = CARTES[numero - 1]
        marque = "juste" if juste else "faux"
        _verifier(
            orchestrateur.etat() is Etat.QUESTION,
            f"carte {numero} ({marque}) : le panneau attend une réponse",
        )
        _verifier(
            panneau._etiquette_avancement.text() == f"{numero} / {TOTAL}",
            f"carte {numero} ({marque}) : l'avancement affiche {numero} / {TOTAL}",
        )
        _verifier(
            panneau._etiquette_question.text() == modele.question,
            f"carte {numero} ({marque}) : la question posée est celle de la carte",
        )
        _verifier(
            panneau._pile_reponses.currentIndex() == _page_attendue(modele),
            f"carte {numero} ({marque}) : la forme {modele.forme.name} a son geste",
        )

        if numero == 1 and juste:
            _verifier(
                panneau.pos().y() < 60,
                "le panneau s'ouvre en haut, sous la barre de menus",
            )
            html = panneau._zone_code.toHtml()
            _verifier("<span" in html, "le code est affiché avec coloration syntaxique")
            lignes = [
                ligne.replace("\xa0", " ").strip()
                for ligne in panneau._zone_code.toPlainText().split("\n")
            ]
            _verifier(
                len(lignes) == NOMBRE_DE_LIGNES,
                "le code affiché a autant de lignes que la source",
            )
            _verifier(
                lignes[0].startswith("1 ") and lignes[6].startswith("7 "),
                "chaque ligne de code porte son numéro",
            )
            _verifier(
                len(panneau._boutons_options) == 4,
                "un QCM propose quatre options cliquables",
            )

        if modele.forme is Forme.VRAI_FAUX:
            _verifier(
                len(panneau._boutons_options) == 2,
                f"carte {numero} ({marque}) : un vrai ou faux propose deux options",
            )

        if modele.forme is Forme.REPERER:
            _verifier(
                panneau._zone_code._cliquable,
                f"carte {numero} ({marque}) : les lignes du code deviennent cliquables",
            )
            _verifier(
                panneau._zone_code._ligne_visee == 0,
                f"carte {numero} ({marque}) : rien n'est souligné, la ligne est la réponse",
            )
        else:
            _verifier(
                not panneau._zone_code._cliquable,
                f"carte {numero} ({marque}) : hors repérage, le code n'est pas cliquable",
            )
            _verifier(
                panneau._zone_code._ligne_visee == modele.ligne,
                f"carte {numero} ({marque}) : la ligne visée est mise en évidence",
            )

        _verifier(
            _repondre(panneau, modele, juste),
            f"carte {numero} ({marque}) : la réponse se donne en un geste",
        )

    def correction(numero: int, juste: bool) -> None:
        modele = CARTES[numero - 1]
        marque = "juste" if juste else "faux"
        _verifier(
            orchestrateur.etat() is Etat.RETOUR,
            f"carte {numero} ({marque}) : la réponse mène droit à la correction",
        )
        _verifier(
            panneau._etiquette_verdict.text() == ("Juste" if juste else "Raté"),
            f"carte {numero} ({marque}) : le verdict dit ce qu'il en est",
        )
        _verifier(
            panneau._etiquette_explication.text() == modele.explication,
            f"carte {numero} ({marque}) : l'explication en prose s'affiche",
        )
        _verifier(
            panneau._etiquette_bonne_reponse.isVisible() is not juste,
            f"carte {numero} ({marque}) : la bonne réponse n'est rappelée qu'en cas d'erreur",
        )
        if not juste:
            attendue = (
                f"ligne {modele.reponse}"
                if modele.forme is Forme.REPERER
                else modele.reponse
            )
            _verifier(
                attendue in panneau._etiquette_bonne_reponse.text(),
                f"carte {numero} (faux) : la bonne réponse est donnée en clair",
            )
        _verifier(
            panneau._bouton_suivant.text()
            == ("Voir le bilan" if numero == TOTAL else "Carte suivante"),
            f"carte {numero} ({marque}) : le bouton annonce ce qui vient ensuite",
        )

        if numero == 1 and juste:
            panneau._repondre("une réponse de plus")
            _verifier(
                orchestrateur.etat() is Etat.RETOUR,
                "répondre une seconde fois à la même carte ne change rien",
            )

        panneau._bouton_suivant.click()

    def bilan(juste: bool) -> None:
        marque = "juste" if juste else "faux"
        attendu = f"{TOTAL if juste else 0} / {TOTAL}"
        _verifier(
            orchestrateur.etat() is Etat.BILAN,
            f"série ({marque}) : la dernière carte mène au bilan",
        )
        _verifier(
            panneau._etiquette_bilan.text() == attendu,
            f"série ({marque}) : le bilan compte {attendu}",
        )
        _verifier(
            not panneau._zone_code.isVisible(),
            f"série ({marque}) : le bilan laisse le code de côté",
        )
        if juste:
            panneau._bouton_serie_suivante.click()

    def transitions_interdites() -> None:
        _verifier(
            not transition_valide(Etat.RETOUR, Etat.REPOS),
            "on ne repasse pas de la correction au repos sans abandonner",
        )
        _verifier(
            not transition_valide(Etat.QUESTION, Etat.BILAN),
            "on ne saute pas d'une carte au bilan",
        )
        _verifier(
            not transition_valide(Etat.BILAN, Etat.RETOUR),
            "le bilan ne revient pas sur la correction d'une carte",
        )
        _verifier(
            transition_valide(Etat.QUESTION, Etat.RETOUR)
            and transition_valide(Etat.RETOUR, Etat.QUESTION),
            "une carte et sa correction s'enchaînent sans état intermédiaire",
        )

        refusee = False
        try:
            orchestrateur._aller_vers(Etat.RETOUR)
        except RuntimeError:
            refusee = True
        _verifier(refusee, "une transition hors table lève au lieu de passer")
        _verifier(
            orchestrateur.etat() is Etat.BILAN,
            "la transition refusée laisse l'état où il était",
        )

        panneau.suite_demandee.emit()
        _verifier(
            orchestrateur.etat() is Etat.BILAN,
            "demander la suite depuis le bilan ne mène nulle part",
        )
        panneau.reponse_donnee.emit("une réponse sans carte")
        _verifier(
            orchestrateur.etat() is Etat.BILAN,
            "une réponse hors série est ignorée",
        )
        panneau.fermeture_demandee.emit()

    def fermeture() -> None:
        _verifier(orchestrateur.etat() is Etat.FERME, "la fermeture referme le panneau")
        _verifier(not panneau.isVisible(), "le panneau a bien disparu")

    def fin() -> None:
        _verifier(
            orchestrateur.etat() is Etat.FERME,
            "le panneau reste fermé jusqu'au prochain clic",
        )
        application.quit()

    etapes = [demarrage, repos_initial]
    for juste in (True, False):
        for numero in range(1, TOTAL + 1):
            etapes.append(partial(carte, numero, juste))
            etapes.append(partial(correction, numero, juste))
        etapes.append(partial(bilan, juste))
    etapes += [transitions_interdites, fermeture, fin]

    # Une cadence régulière plutôt que des délais choisis un par un : les
    # étapes se ressemblent toutes, et la liste reste lisible quand la série
    # s'allonge.
    for rang, etape in enumerate(etapes):
        QTimer.singleShot(500 + rang * 180, etape)

    application.exec()

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
