#!/usr/bin/env python3
"""Vérification de bout en bout : le cycle d'états et le non-vol du focus.

Le scénario reproduit la situation réelle : l'application tourne pendant qu'on
travaille ailleurs, une session démarre, l'invitation apparaît, on répond, on
lit le retour. Pendant tout ce temps le clavier doit rester à l'application
qui l'avait.

Le script se ferme tout seul et rend un code de sortie non nul si une des
vérifications échoue.

    python verifier.py
"""

from __future__ import annotations

import ctypes
import json
import os
import sys
import tempfile

# Avant tout import du paquet : la vérification ne doit pas écrire dans
# l'historique réel.
DOSSIER_TEST = tempfile.mkdtemp(prefix="knowyourcode-verif-")
os.environ["KNOWYOURCODE_DOSSIER"] = DOSSIER_TEST

from PyQt6.QtCore import Qt, QTimer  # noqa: E402
from PyQt6.QtTest import QTest  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from connais_ton_code.affichage import est_a_l_ecran  # noqa: E402
from connais_ton_code.application import (  # noqa: E402
    _autoriser_ctrl_c,
    _passer_en_application_accessoire,
    attendre_les_evaluations,
    construire,
)
from connais_ton_code.etats import Etat  # noqa: E402

_constats: list[tuple[bool, str]] = []


def _verifier(condition: bool, description: str) -> None:
    _constats.append((bool(condition), description))


def _nous_sommes_au_premier_plan() -> bool | None:
    """Rend None si la question n'a pas de sens sur cette plateforme."""
    if sys.platform != "darwin":
        return None
    try:
        from AppKit import NSWorkspace
    except ImportError:
        return None
    devant = NSWorkspace.sharedWorkspace().frontmostApplication()
    return devant is not None and devant.processIdentifier() == os.getpid()


def _panneau_natif(widget):
    if sys.platform != "darwin":
        return None
    try:
        import objc
    except ImportError:
        return None
    return objc.objc_object(c_void_p=ctypes.c_void_p(int(widget.winId()))).window()


def _a_le_clavier(widget) -> bool:
    """Dit si la fenêtre est celle qui reçoit les frappes.

    On interroge la fenêtre native et pas `QWidget.isActiveWindow()` : Qt
    tient sa propre comptabilité, faussée par le fait qu'on affiche sans
    passer par lui.
    """
    panneau = _panneau_natif(widget)
    if panneau is None:
        return widget.isActiveWindow()
    return bool(panneau.isKeyWindow())


def _le_clic_pourra_donner_le_clavier(widget) -> bool:
    """Un panneau non activant ne deviendrait jamais la fenêtre clé.

    Autrement dit : la fenêtre n'attrape pas le focus toute seule, mais elle
    doit pouvoir l'obtenir quand on clique dedans, sinon impossible de taper
    sa réponse.
    """
    panneau = _panneau_natif(widget)
    if panneau is None:
        return True
    masque_non_activant = 1 << 7
    return (
        not panneau.styleMask() & masque_non_activant
        and bool(panneau.canBecomeKeyWindow())
    )


def main() -> int:
    application = QApplication(sys.argv)
    _passer_en_application_accessoire()
    _autoriser_ctrl_c(application)

    orchestrateur = construire(application)
    fenetre = orchestrateur._fenetre
    bulle = orchestrateur._bulle
    barre = orchestrateur._barre

    def _entrees_historique() -> list:
        journal = os.path.join(DOSSIER_TEST, "historique.json")
        if not os.path.exists(journal):
            return []
        with open(journal, encoding="utf-8") as fichier:
            return json.load(fichier).get("entrees", [])

    def demarrage() -> None:
        _verifier(
            orchestrateur.etat() is Etat.MASQUEE,
            "au démarrage, l'état est Masquée",
        )
        _verifier(not est_a_l_ecran(fenetre), "la fenêtre n'est pas à l'écran")
        _verifier(not bulle.est_visible(), "la bulle n'est pas à l'écran")
        _verifier(barre.isVisible(), "l'icône de la barre de menus est en place")
        _verifier(
            _nous_sommes_au_premier_plan() is not True,
            "le lancement laisse le focus à l'application précédente",
        )
        barre.detection_simulee.emit()

    def invitation() -> None:
        _verifier(
            orchestrateur.etat() is Etat.INVITATION,
            "une détection ouvre l'état Invitation",
        )
        _verifier(bulle.est_visible(), "la bulle d'invitation est à l'écran")
        _verifier(
            not est_a_l_ecran(fenetre),
            "l'invitation n'ouvre pas encore la question",
        )
        _verifier(
            _nous_sommes_au_premier_plan() is not True,
            "l'invitation ne prend pas le focus",
        )
        bulle.rejet_demande.emit()

    def apres_rejet() -> None:
        _verifier(
            orchestrateur.etat() is Etat.MASQUEE, "une invitation écartée referme tout"
        )
        _verifier(not bulle.est_visible(), "la bulle écartée quitte l'écran")
        _verifier(
            _entrees_historique() == [],
            "une invitation écartée ne consomme aucun extrait",
        )
        barre.detection_simulee.emit()

    def acceptation() -> None:
        _verifier(
            orchestrateur.etat() is Etat.INVITATION,
            "une deuxième détection réarme l'invitation",
        )
        bulle.ouverture_demandee.emit()

    def question() -> None:
        _verifier(
            orchestrateur.etat() is Etat.QUESTION,
            "accepter l'invitation ouvre la question",
        )
        _verifier(not bulle.est_visible(), "la bulle s'efface derrière la question")
        _verifier(est_a_l_ecran(fenetre), "la fenêtre de question est à l'écran")
        _verifier(
            _nous_sommes_au_premier_plan() is not True,
            "l'affichage de la question ne prend pas le focus",
        )
        _verifier(
            not _a_le_clavier(fenetre),
            "la fenêtre affichée ne reçoit pas les frappes clavier",
        )
        _verifier(
            QApplication.focusWidget() is None,
            "aucun widget n'a capté le clavier",
        )
        _verifier(
            _le_clic_pourra_donner_le_clavier(fenetre),
            "un clic pourra donner le clavier à la fenêtre",
        )
        _verifier(
            fenetre._etiquette_fonction.text() != "",
            "le nom de la fonction est affiché",
        )
        _verifier(
            "<span" in fenetre._zone_code.toHtml(),
            "le code est affiché avec coloration syntaxique",
        )
        fenetre._zone_reponse.setPlainText(
            "Cette fonction regroupe les évènements par journée locale."
        )
        fenetre._bouton_repondre.click()

    def evaluation() -> None:
        _verifier(
            orchestrateur.etat() is Etat.EVALUATION,
            "la réponse fait passer en état Évaluation",
        )
        _verifier(
            est_a_l_ecran(fenetre),
            "la fenêtre reste affichée pendant l'évaluation",
        )
        _verifier(
            _nous_sommes_au_premier_plan() is not True,
            "l'évaluation ne prend pas le focus",
        )

    def retour() -> None:
        _verifier(
            orchestrateur.etat() is Etat.RETOUR,
            "l'évaluation aboutit à l'état Retour",
        )
        _verifier(
            len(_entrees_historique()) == 1,
            "la réponse est enregistrée dans l'historique",
        )
        fenetre._bouton_suivant.click()

    def suite() -> None:
        _verifier(
            orchestrateur.etat() is Etat.MASQUEE, "Suivant ramène à l'état Masquée"
        )
        _verifier(not est_a_l_ecran(fenetre), "la fenêtre est retirée de l'écran")
        barre.question_demandee.emit()

    def echappement() -> None:
        _verifier(
            orchestrateur.etat() is Etat.QUESTION,
            "le menu pose une question sans passer par l'invitation",
        )
        QTest.keyClick(fenetre._zone_reponse, Qt.Key.Key_Escape)

    def apres_echappement() -> None:
        _verifier(orchestrateur.etat() is Etat.MASQUEE, "Esc masque la fenêtre")
        _verifier(not est_a_l_ecran(fenetre), "Esc retire la fenêtre de l'écran")
        _verifier(
            len(_entrees_historique()) == 1,
            "Esc n'enregistre rien dans l'historique",
        )
        _verifier(
            _nous_sommes_au_premier_plan() is not True,
            "jusqu'ici l'application n'a jamais pris le premier plan",
        )
        print("La dernière étape prend volontairement le focus une seconde,")
        print("pour vérifier qu'un clic permet bien de répondre au clavier.")
        barre.question_demandee.emit()

    def clic_simule() -> None:
        """Reproduit le clic de l'utilisateur dans la fenêtre."""
        _verifier(
            orchestrateur.etat() is Etat.QUESTION,
            "une dernière question s'ouvre pour l'essai au clavier",
        )
        try:
            from AppKit import NSApplication
        except ImportError:
            return
        NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
        panneau = _panneau_natif(fenetre)
        if panneau is not None:
            panneau.makeKeyWindow()
        fenetre._zone_reponse.setFocus()

    def raccourci() -> None:
        _verifier(_a_le_clavier(fenetre), "après le clic, la fenêtre a le clavier")
        _verifier(
            QApplication.focusWidget() is fenetre._zone_reponse,
            "le curseur est dans la zone de réponse",
        )
        fenetre._zone_reponse.setPlainText("Réponse envoyée au clavier.")
        # Sur macOS, Qt fait correspondre ControlModifier à la touche Cmd.
        QTest.keyClick(
            fenetre._zone_reponse,
            Qt.Key.Key_Return,
            Qt.KeyboardModifier.ControlModifier,
        )

    def fin() -> None:
        _verifier(
            orchestrateur.etat() is Etat.EVALUATION,
            "Cmd+Entrée envoie la réponse",
        )
        fenetre.masquage_demande.emit()

    def restitution() -> None:
        _verifier(
            orchestrateur.etat() is Etat.MASQUEE,
            "Esc interrompt l'évaluation en cours",
        )
        _verifier(
            len(_entrees_historique()) == 1,
            "une évaluation interrompue ne laisse pas de trace",
        )
        _verifier(
            _nous_sommes_au_premier_plan() is not True,
            "en se masquant, la fenêtre rend le clavier à l'application d'avant",
        )
        application.quit()

    for delai, etape in (
        (700, demarrage),
        (1800, invitation),
        (2100, apres_rejet),
        (3200, acceptation),
        (3500, question),
        (3800, evaluation),
        (5000, retour),
        (5400, suite),
        (5700, echappement),
        (6100, apres_echappement),
        (6400, clic_simule),
        (6900, raccourci),
        (7200, fin),
        (7700, restitution),
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
