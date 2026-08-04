"""Point d'entrée : assemble les briques et lance la boucle Qt."""

from __future__ import annotations

import signal
import sys

from PyQt6.QtCore import Qt, QThreadPool, QTimer
from PyQt6.QtWidgets import QApplication

from .apparence import appliquer_theme_sombre
from .barre_menu import BarreMenu
from .evaluateur import Evaluateur, EvaluateurFactice, EvaluateurMistral, cle_mistral
from .historique import Historique
from .orchestrateur import Orchestrateur
from .panneau import Panneau
from .projet import Projet, ProjetClaudeCode, ProjetFactice
from .selecteur import Selecteur, SelecteurFactice, SelecteurProjet


def _mode_barre_de_menus() -> None:
    """Fait de l'application un utilitaire de barre de menus.

    Une application « accessoire » n'a ni icône au Dock ni barre de menus
    propre : elle vit uniquement dans son icône en haut de l'écran, comme les
    utilitaires du système. Elle peut toujours passer au premier plan quand on
    clique dessus.
    """
    if sys.platform != "darwin":
        return
    try:
        from AppKit import NSApplication, NSApplicationActivationPolicyAccessory
    except ImportError:
        # pyobjc absent : l'application reste normale, avec icône au Dock.
        return
    NSApplication.sharedApplication().setActivationPolicy_(
        NSApplicationActivationPolicyAccessory
    )


def _autoriser_ctrl_c(application: QApplication) -> None:
    """Rend le Ctrl+C du terminal efficace pendant la boucle Qt.

    Qt garde la main sur la boucle d'évènements : sans réveil régulier de
    l'interpréteur, Python ne traite jamais le signal.
    """
    signal.signal(signal.SIGINT, lambda *_: application.quit())
    reveil = QTimer(application)
    reveil.start(200)
    reveil.timeout.connect(lambda: None)


def _choisir_projet(factice: bool) -> Projet:
    if factice:
        return ProjetFactice()
    reel = ProjetClaudeCode()
    if reel.disponible():
        return reel
    print("~/.claude/projects/ introuvable : le projet en cours restera inconnu.")
    return ProjetFactice()


def _choisir_evaluateur(factice: bool) -> Evaluateur:
    if factice:
        return EvaluateurFactice()
    cle = cle_mistral()
    if cle:
        return EvaluateurMistral(cle)
    print(
        "Aucune clé Mistral : évaluation factice. Renseigne MISTRAL_API_KEY "
        "ou ~/.knowyourcode/cle_mistral."
    )
    return EvaluateurFactice()


def _choisir_selecteur(factice: bool) -> Selecteur:
    return SelecteurFactice() if factice else SelecteurProjet()


def construire(application: QApplication, factice: bool = False) -> Orchestrateur:
    """Monte l'application et rend l'orchestrateur.

    `factice` force les briques bouchonnées, ce dont a besoin la vérification :
    elle ne doit dépendre ni du disque, ni du réseau, ni de la présence d'une
    session Claude Code en cours.
    """
    appliquer_theme_sombre()

    historique = Historique()

    panneau = Panneau()
    panneau.sortie_demandee.connect(application.quit)

    barre = BarreMenu(application)
    barre.show()

    orchestrateur = Orchestrateur(
        panneau=panneau,
        barre=barre,
        projet=_choisir_projet(factice),
        selecteur=_choisir_selecteur(factice),
        evaluateur=_choisir_evaluateur(factice),
        historique=historique,
        parent=application,
    )
    # Le panneau est gardé vivant par l'orchestrateur, qui appartient à
    # l'application ; et le refermer ne doit pas arrêter le programme.
    application.setQuitOnLastWindowClosed(False)
    return orchestrateur


def attendre_les_evaluations(delai_ms: int = 3000) -> None:
    """Laisse les évaluations en cours se terminer avant de démonter Qt.

    Une évaluation abandonnée continue de tourner dans son fil : si Qt est
    démonté avant qu'elle rende son résultat, elle l'émet sur des objets qui
    n'existent plus et la sortie du programme se termine par une trace
    d'erreur sans intérêt.
    """
    QThreadPool.globalInstance().waitForDone(delai_ms)


def _ouvrir_a_l_activation(
    application: QApplication, orchestrateur: Orchestrateur
) -> None:
    """Fait que cliquer sur l'application ouvre le panneau.

    Sans ça, lancer l'application une deuxième fois ne produit rien : macOS
    voit un programme déjà en marche et se contente de l'activer, or il n'a
    aucune fenêtre à montrer. On ouvre donc le panneau à chaque fois que
    l'application devient active, ce qui couvre aussi le tout premier
    lancement.

    Un utilitaire de barre de menus n'apparaît ni au Dock ni dans le
    sélecteur d'applications : il ne devient actif que si on clique sur son
    icône, sur son panneau, ou sur l'application elle-même. Il n'y a donc pas
    d'activation involontaire à craindre.
    """

    def sur_changement(etat: Qt.ApplicationState) -> None:
        if etat == Qt.ApplicationState.ApplicationActive:
            orchestrateur.ouvrir()

    application.applicationStateChanged.connect(sur_changement)


def lancer() -> int:
    application = QApplication(sys.argv)
    application.setApplicationName("KnowYourCode")
    _mode_barre_de_menus()
    _autoriser_ctrl_c(application)

    orchestrateur = construire(application)
    _ouvrir_a_l_activation(application, orchestrateur)

    # Lancer l'application doit produire quelque chose de visible. Le délai
    # laisse à l'icône le temps d'exister : le panneau s'accroche dessous, et
    # sans elle il ne saurait pas où s'ouvrir.
    QTimer.singleShot(500, orchestrateur.ouvrir)

    code = application.exec()
    attendre_les_evaluations()
    return code
