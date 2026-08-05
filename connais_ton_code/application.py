"""Point d'entrée : assemble les briques et lance la boucle Qt."""

from __future__ import annotations

import signal
import sys

from PyQt6.QtCore import QThreadPool, QTimer
from PyQt6.QtWidgets import QApplication

from .apparence import appliquer_theme_sombre
from .barre_menu import BarreMenu
from .fenetre_principale import FenetrePrincipale
from .generateur import (
    Generateur,
    GenerateurFactice,
    GenerateurMistral,
    cle_mistral,
)
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


def _choisir_generateur(factice: bool) -> Generateur:
    if factice:
        return GenerateurFactice()
    cle = cle_mistral()
    if cle:
        return GenerateurMistral(cle)
    print(
        "Aucune clé Mistral : cartes fabriquées sans modèle, à partir du seul "
        "repérage. Renseigne MISTRAL_API_KEY ou ~/.knowyourcode/cle_mistral."
    )
    return GenerateurFactice()


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

    fenetre = FenetrePrincipale()

    barre = BarreMenu(application)
    barre.show()

    orchestrateur = Orchestrateur(
        panneau=panneau,
        fenetre=fenetre,
        barre=barre,
        projet=_choisir_projet(factice),
        selecteur=_choisir_selecteur(factice),
        generateur=_choisir_generateur(factice),
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


def lancer() -> int:
    application = QApplication(sys.argv)
    application.setApplicationName("KnowYourCode")
    _mode_barre_de_menus()
    _autoriser_ctrl_c(application)

    # Rien ne s'ouvre au lancement : l'application se contente de poser son
    # icône dans la barre et d'attendre qu'on clique dessus.
    construire(application)

    code = application.exec()
    attendre_les_evaluations()
    return code
