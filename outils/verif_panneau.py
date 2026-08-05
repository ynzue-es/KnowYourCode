#!/usr/bin/env python3
"""Vérification du panneau : une série de cartes, posée et corrigée à l'écran.

Le scénario suit le chemin réel d'un utilisateur : il ouvre le panneau, part
sur une série, répond carte après carte, lit l'explication, arrive au bilan,
en relance une, et referme. La série est écrite en dur et couvre les deux
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

from PyQt6.QtCore import QRect, Qt, QTimer  # noqa: E402
from PyQt6.QtGui import QGuiApplication  # noqa: E402
from PyQt6.QtTest import QTest  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from connais_ton_code.apparence import appliquer_theme_sombre  # noqa: E402
from connais_ton_code.application import (  # noqa: E402
    _autoriser_ctrl_c,
    _mode_barre_de_menus,
)
from connais_ton_code.barre_menu import BarreMenu  # noqa: E402
from connais_ton_code.cartes import (  # noqa: E402
    Carte,
    Forme,
    Serie,
    bonne_reponse,
)
from connais_ton_code.etats import Etat, transition_valide  # noqa: E402
from connais_ton_code.fenetre_principale import FenetrePrincipale  # noqa: E402
from connais_ton_code.historique import Historique  # noqa: E402
from connais_ton_code.modeles import Extrait  # noqa: E402
from connais_ton_code.orchestrateur import Orchestrateur  # noqa: E402
from connais_ton_code.panneau import (  # noqa: E402
    HAUTEUR_BILAN,
    HAUTEUR_BOUTON_OPTION,
    HAUTEUR_CORRECTION,
    HAUTEUR_MANCHE,
    HAUTEUR_MINIMALE,
    HAUTEUR_REPOS,
    LARGEUR,
    Panneau,
)
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
        bonne=0,
        ligne=5,
    ),
    Carte(
        forme=Forme.VRAI_FAUX,
        question="Ligne 8 : cette soustraction modifie l'évènement d'origine.",
        explication=(
            "`locale` est une variable locale, obtenue par conversion : la "
            "réassigner ne touche pas à `evenement.horodatage`. C'est ce qui "
            "permet de décaler la journée sans réécrire les données lues."
        ),
        options=("Vrai", "Faux"),
        bonne=1,
        ligne=8,
    ),
    Carte(
        forme=Forme.QCM,
        question="Ligne 7 : à quoi sert de comparer l'heure à quatre ?",
        explication=(
            "La journée d'usage commence à quatre heures du matin : en deçà, "
            "on est encore dans la soirée de la veille. C'est la seule ligne à "
            "porter cette convention ; la suivante ne fait qu'appliquer le "
            "décalage qu'elle a décidé."
        ),
        options=(
            "À rattacher une session nocturne à la veille",
            "À ignorer les évènements du petit matin",
            "À corriger un décalage de fuseau horaire",
            "À éviter une division par zéro sur `locale`",
        ),
        bonne=0,
        ligne=7,
    ),
    Carte(
        forme=Forme.QCM,
        question="Ligne 11 : que prend chaque valeur du dictionnaire rendu ?",
        explication=(
            "Les listes accumulées pendant la boucle sont figées en tuples au "
            "moment de rendre le résultat. L'appelant repart donc avec quelque "
            "chose qu'il ne peut pas modifier par mégarde."
        ),
        options=(
            "Un tuple, figé à la sortie",
            "La liste construite pendant la boucle",
            "Le `defaultdict` lui-même",
            "Un dictionnaire par évènement",
        ),
        bonne=0,
        ligne=11,
    ),
    Carte(
        forme=Forme.VRAI_FAUX,
        question="Ligne 3 : sans `defaultdict`, la ligne 9 lèverait une erreur.",
        explication=(
            "`defaultdict(list)` fabrique la liste manquante à la première "
            "visite d'une date. Avec un dictionnaire ordinaire, `par_jour` "
            "n'aurait pas la clé et `append` lèverait un `KeyError`."
        ),
        options=("Vrai", "Faux"),
        bonne=0,
        notion="defaultdict",
        ligne=3,
    ),
)

TOTAL = len(CARTES)

# La cadence des étapes, et le nombre de fois qu'on redemande l'ouverture avant
# de renoncer : macOS met parfois près d'une seconde à donner le focus à une
# application accessoire, surtout quand une autre vient de se fermer.
CADENCE_MS = 180
ESSAIS_MAX = 25


class GuetteurFige:
    """Annonce un prompt, une fois. Programme contre le contrat du vrai."""

    def __init__(self) -> None:
        self._reste = True

    def prompts(self) -> list[str]:
        if not self._reste:
            return []
        self._reste = False
        return ["/un/projet"]


class GenerateurFige:
    """Rend toujours la même série, quel que soit l'extrait reçu.

    Programme contre le contrat du vrai générateur : `fabriquer(extrait)`
    rend une `Serie` ou `None`.
    """

    def fabriquer(self, extrait: Extrait) -> Serie | None:
        return Serie(extrait=extrait, cartes=CARTES)


# ----------------------------------------------------------------------
# Le geste de réponse : un clic sur une option, et rien d'autre
# ----------------------------------------------------------------------


def _reponse_juste(carte: Carte) -> str:
    return carte.options[carte.bonne]


def _mauvaise_option(carte: Carte) -> str:
    juste = _reponse_juste(carte)
    return next(option for option in carte.options if option != juste)


def _cliquer_option(panneau: Panneau, texte: str) -> bool:
    """Clique vraiment le bouton, comme le ferait la main."""
    for bouton in panneau._boutons_options:
        if bouton.text() == texte:
            QTest.mouseClick(bouton, Qt.MouseButton.LeftButton)
            return True
    return False


def _repondre(panneau: Panneau, carte: Carte, juste: bool) -> bool:
    return _cliquer_option(
        panneau, _reponse_juste(carte) if juste else _mauvaise_option(carte)
    )


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
        attendues = 2 if modele.forme is Forme.VRAI_FAUX else 4
        _verifier(
            len(panneau._boutons_options) == attendues,
            f"carte {numero} ({marque}) : la forme {modele.forme.name} pose "
            f"{attendues} boutons",
        )

        # Des propositions serrées se lisent comme une seule phrase coupée, et
        # on hésite sur celle qu'on vise. Les rectangles doivent donc être à la
        # fois assez hauts et bien séparés.
        cadres = [bouton.geometry() for bouton in panneau._boutons_options]
        _verifier(
            all(cadre.height() >= HAUTEUR_BOUTON_OPTION for cadre in cadres),
            f"carte {numero} ({marque}) : chaque proposition garde sa hauteur",
        )
        _verifier(
            all(
                not premier.intersects(second)
                for i, premier in enumerate(cadres)
                for second in cadres[i + 1 :]
            ),
            f"carte {numero} ({marque}) : deux propositions ne se touchent pas",
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

        _verifier(
            panneau._zone_code._ligne_visee == modele.ligne,
            f"carte {numero} ({marque}) : la ligne visée est mise en évidence",
        )
        _verifier(
            len(panneau._zone_code.extraSelections()) == 1,
            f"carte {numero} ({marque}) : une seule bande, celle de la ligne visée",
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
            _verifier(
                bonne_reponse(modele) in panneau._etiquette_bonne_reponse.text(),
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

    def placement() -> None:
        """Le panneau doit rester entier à l'écran, où que soit l'icône.

        L'icône vit dans la barre de menus, donc n'importe où sur la largeur ;
        et la fenêtre grandit en passant à la correction. Les deux ensemble la
        faisaient sortir par la droite ou par le bas.
        """
        ecran = QGuiApplication.primaryScreen()
        zone = ecran.availableGeometry()

        for description, gauche in (
            ("collée au bord gauche", zone.left()),
            ("au milieu", zone.center().x()),
            ("collée au bord droit", zone.right() - 24),
        ):
            panneau.ancrer(QRect(gauche, zone.top(), 24, 22))
            for hauteur, moment in (
                (HAUTEUR_MANCHE, "sur la carte"),
                (HAUTEUR_CORRECTION, "sur la correction"),
            ):
                panneau.resize(LARGEUR, hauteur)
                panneau._positionner()
                cadre = panneau.geometry()
                _verifier(
                    zone.contains(cadre),
                    f"icône {description}, {moment} : la fenêtre tient dans l'écran",
                )

        # Le placement ne doit jamais agrandir une fenêtre qu'on a voulue
        # petite : le repos ne demande que 170 pixels, et les lui refuser
        # ouvrait un panneau aux trois quarts vide.
        # En passant par le vrai affichage : c'est lui qui masque le code et
        # rétrécit la zone basse, donc lui seul qui autorise une petite
        # fenêtre. La redimensionner à la main se heurterait au minimum que
        # les blocs imposent, et le contrôle passerait pour de mauvaises
        # raisons.
        for afficher, hauteur, page in (
            (
                lambda: panneau.afficher_repos("Rien en attente."),
                HAUTEUR_REPOS,
                "au repos",
            ),
            (
                lambda: panneau.afficher_bilan(1, 2, "Bien."),
                HAUTEUR_BILAN,
                "sur le bilan",
            ),
        ):
            afficher()
            # Redimensionner une fenêtre déjà à l'écran passe par le système :
            # la mesurer sans laisser Qt appliquer la géométrie donnerait
            # l'ancienne taille, et le constat ne dirait rien.
            application.processEvents()
            avant = panneau.height()
            panneau._positionner()
            application.processEvents()

            # Qt impose ses propres minimums, et ceux-là ne regardent pas le
            # placement. Ce qu'on lui demande est plus étroit et se vérifie
            # exactement : ne jamais agrandir ce qu'on lui donne.
            _verifier(
                panneau.height() <= avant,
                f"{page}, le placement n'agrandit pas la fenêtre "
                f"({avant} → {panneau.height()})",
            )
            _verifier(
                avant < HAUTEUR_MINIMALE,
                f"{page}, la fenêtre reste petite ({avant} px) au lieu d'être "
                f"gonflée au plancher de {HAUTEUR_MINIMALE}",
            )

        # L'écran de la machine qui fait tourner ce script est ce qu'il est :
        # on ne peut pas en changer, et le rétrécissement resterait sinon
        # jamais éprouvé. On lui substitue donc une place mesurée à la main.
        vrai_zone_ecran = panneau._zone_ecran
        for largeur_ecran, hauteur_ecran in ((1280, 600), (900, 500)):
            etroit = QRect(0, 0, largeur_ecran, hauteur_ecran)
            panneau._zone_ecran = lambda zone=etroit: zone
            panneau.resize(LARGEUR, HAUTEUR_CORRECTION)
            panneau._positionner()
            _verifier(
                etroit.contains(panneau.geometry()),
                f"sur un écran de {largeur_ecran}×{hauteur_ecran}, "
                "la fenêtre se rétrécit au lieu de déborder",
            )
        panneau._zone_ecran = vrai_zone_ecran

    def _reveiller() -> None:
        """Fait comme si un prompt venait de partir vers Claude Code."""
        orchestrateur._guetteur_prompts = GuetteurFige()
        orchestrateur._sur_guet()

    def desaccord() -> None:
        """Le réveil doit survivre à un panneau disparu sans prévenir.

        On reproduit le cas en cachant la fenêtre sans passer par la fermeture,
        comme le ferait macOS en retirant une fenêtre accessoire : l'état croit
        le panneau ouvert alors que l'écran est vide. Sans rattrapage, le
        réveil se tairait pour toujours après un seul raté.
        """
        orchestrateur.ouvrir()
        panneau.blockSignals(True)
        panneau.hide()
        panneau.blockSignals(False)
        _verifier(
            orchestrateur.etat() is not Etat.FERME and not panneau.isVisible(),
            "le désaccord entre l'état et l'écran est bien reproduit",
        )

        orchestrateur._reveil_actif = True
        _reveiller()

    def desaccord_suite() -> None:
        """La série arrive au tour suivant : sa fabrication passe par un fil."""
        _verifier(
            panneau.isVisible(),
            "le guet rattrape le désaccord et rouvre au lieu de se taire",
        )
        _verifier(
            orchestrateur.etat() is Etat.QUESTION,
            "le réveil pose bien une carte, pas seulement une fenêtre",
        )

        # L'inverse doit rester vrai : tant qu'une carte attend sa réponse, un
        # prompt ne doit pas la balayer.
        _reveiller()
        _verifier(
            orchestrateur.etat() is Etat.QUESTION
            and panneau._etiquette_avancement.text() == f"1 / {TOTAL}",
            "une carte en attente n'est pas balayée par le prompt suivant",
        )

    def repos_reveille() -> None:
        """Un panneau laissé au repos doit repartir sur un prompt.

        C'est le cas qui condamnait le réveil : après une série, la fenêtre
        traîne à l'écran, l'état n'est plus « fermé », et s'en tenir à cet état
        revenait à ne plus jamais rien poser.
        """
        orchestrateur.fermer()
        orchestrateur.ouvrir()
        _verifier(
            orchestrateur.etat() is Etat.REPOS,
            "le panneau ouvert sans série est bien au repos",
        )
        _reveiller()

    def repos_reveille_suite() -> None:
        _verifier(
            orchestrateur.etat() is Etat.QUESTION,
            "un prompt reçu au repos pose une série au lieu de ne rien faire",
        )
        orchestrateur.fermer()

    def fin() -> None:
        _verifier(
            orchestrateur.etat() is Etat.FERME,
            "le panneau reste fermé jusqu'au prochain clic",
        )
        application.quit()

    # `demarrage` reste hors de l'enchaînement : c'est lui qui ouvre, et son
    # constat porte justement sur l'état d'avant l'ouverture.
    etapes = [demarrage, repos_initial]
    for juste in (True, False):
        for numero in range(1, TOTAL + 1):
            etapes.append(partial(carte, numero, juste))
            etapes.append(partial(correction, numero, juste))
        etapes.append(partial(bilan, juste))
    etapes += [
        transitions_interdites,
        fermeture,
        placement,
        desaccord,
        desaccord_suite,
        repos_reveille,
        repos_reveille_suite,
        fin,
    ]

    # Les étapes s'enchaînent, elles ne se minutent pas. Programmées d'avance
    # sur une horloge absolue, elles tombaient sur une fenêtre pas encore
    # affichée quand le démarrage traînait — ce qui arrive juste après une
    # autre application Qt — et les gestes n'atteignaient rien, sans qu'aucun
    # constat n'échoue pour autant. Un contrôle dont le résultat dépend de ce
    # qui a tourné avant ne garantit rien.
    reste = list(etapes)

    def enchainer() -> None:
        if not reste:
            return
        reste.pop(0)()
        if reste:
            QTimer.singleShot(CADENCE_MS, enchainer)

    def demarrer() -> None:
        """Attend que la fenêtre existe vraiment avant de jouer le scénario."""
        if not panneau.isVisible() and demarrer.essais < ESSAIS_MAX:
            demarrer.essais += 1
            orchestrateur.ouvrir()
            QTimer.singleShot(CADENCE_MS, demarrer)
            return
        enchainer()

    demarrer.essais = 0

    # Le premier constat exige le panneau fermé : on le vérifie avant d'ouvrir
    # quoi que ce soit, puis on laisse la fenêtre se poser.
    QTimer.singleShot(300, reste.pop(0))
    QTimer.singleShot(600, demarrer)
    # Un filet : si le scénario se bloque, le script doit rendre la main. Les
    # constats manquants feront échouer le compte.
    QTimer.singleShot(60_000, application.quit)

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
