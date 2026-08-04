"""Point d'entrée : assemble les briques et lance la boucle Qt."""

from __future__ import annotations

import signal
import sys

from PyQt6.QtCore import QThreadPool, QTimer
from PyQt6.QtWidgets import QApplication

from .affichage import amorcer
from .apparence import appliquer_theme_sombre
from .detecteur import DetecteurFactice
from .evaluateur import EvaluateurFactice
from .fenetre import FenetreFlottante
from .historique import Historique
from .orchestrateur import Orchestrateur
from .pastille import PastilleTest
from .placement import restaurer_ou_placer
from .reglages import Reglages
from .selecteur import SelecteurFactice


def _passer_en_application_accessoire() -> None:
    """Retire l'icône du Dock et la barre de menus sur macOS.

    Une application « accessoire » ne devient jamais active toute seule, ce
    qui est la deuxième moitié de la promesse de ne pas voler le focus : sans
    ça, le simple lancement fait basculer macOS sur notre processus. Elle peut
    toujours prendre le focus si l'utilisateur clique dedans.

    L'appel doit venir après la création du QApplication, sinon Qt repasse en
    application classique en s'initialisant.
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


def construire(application: QApplication) -> Orchestrateur:
    """Monte l'application et rend l'orchestrateur, déjà démarré."""
    appliquer_theme_sombre()

    reglages = Reglages()
    historique = Historique()

    fenetre = FenetreFlottante()
    restaurer_ou_placer(fenetre, reglages, "fenetre")
    amorcer(fenetre)

    pastille = PastilleTest()
    restaurer_ou_placer(
        pastille, reglages, "pastille", decalage_vertical=fenetre.height()
    )
    pastille.fermeture_demandee.connect(application.quit)
    amorcer(pastille, montrer_ensuite=True)

    orchestrateur = Orchestrateur(
        fenetre=fenetre,
        detecteur=DetecteurFactice(),
        selecteur=SelecteurFactice(),
        evaluateur=EvaluateurFactice(),
        historique=historique,
        reglages=reglages,
        pastille=pastille,
        parent=application,
    )
    orchestrateur.demarrer()

    # Les fenêtres sont gardées vivantes par l'orchestrateur, qui appartient
    # à l'application ; sans cela le ramasse-miettes les ferait disparaître.
    application.setQuitOnLastWindowClosed(False)
    return orchestrateur


def lancer() -> int:
    application = QApplication(sys.argv)
    application.setApplicationName("KnowYourCode")
    _passer_en_application_accessoire()
    _autoriser_ctrl_c(application)

    construire(application)
    code = application.exec()
    attendre_les_evaluations()
    return code


def attendre_les_evaluations(delai_ms: int = 3000) -> None:
    """Laisse les évaluations en cours se terminer avant de démonter Qt.

    Une évaluation abandonnée continue de tourner dans son fil : si Qt est
    démonté avant qu'elle rende son résultat, elle l'émet sur des objets qui
    n'existent plus et la sortie du programme se termine par une trace
    d'erreur sans intérêt.
    """
    QThreadPool.globalInstance().waitForDone(delai_ms)
