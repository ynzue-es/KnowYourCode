"""Ce qu'il reste à voir du projet.

Les statistiques disent ce qu'on a fait ; la couverture dit ce qu'il reste. Les
deux sont séparées parce qu'elles ne coûtent pas le même prix : l'une se lit
dans l'historique en quelques millisecondes, l'autre parcourt le projet entier
et se compte en centaines. Elle se calcule donc à part, hors du fil de
l'interface, et arrive après coup dans le tableau de bord.

Le dénominateur est choisi pour rester honnête. Ce n'est pas « le code
couvert » : l'application n'interroge que les fonctions qui portent de quoi
tenir une série, et rapporter le reste ferait un pourcentage qu'on ne pourrait
jamais atteindre. On compte donc ce qui est réellement atteignable — les
fonctions qu'on peut tirer, et les notions qui vivent dessus.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

from .modeles import CARTE, EntreeHistorique
from .reperage import reperer, sujets_distincts
from .selecteur import REPERES_MIN, SelecteurProjet


@dataclass(frozen=True)
class Couverture:
    """L'avancée dans le projet, en fonctions et en notions."""

    fonctions_vues: int = 0
    fonctions_interrogeables: int = 0
    notions_vues: int = 0
    notions_du_projet: int = 0
    notions_restantes: tuple[str, ...] = field(default_factory=tuple)
    """Celles qui sont dans le code et qu'on n'a jamais eu à expliquer. C'est
    la partie utile : un compte dit où l'on en est, une liste dit quoi faire."""

    @property
    def part_des_fonctions(self) -> float:
        if not self.fonctions_interrogeables:
            return 0.0
        return self.fonctions_vues / self.fonctions_interrogeables

    @property
    def part_des_notions(self) -> float:
        if not self.notions_du_projet:
            return 0.0
        return self.notions_vues / self.notions_du_projet


def mesurer(
    entrees: Sequence[EntreeHistorique], dossier: Path | None
) -> Couverture:
    """Compare l'historique au projet. Lent : à ne pas appeler sur le fil de l'interface.

    Rend une couverture vide plutôt que `None` quand il n'y a pas de projet :
    l'affichage n'a alors rien de particulier à faire.
    """
    if dossier is None or not dossier.is_dir():
        return Couverture()

    # On emprunte le recensement du sélecteur plutôt que d'en refaire un :
    # compter sur un corpus qui ne serait pas exactement celui qu'il tire
    # donnerait une progression qui n'avance jamais tout à fait.
    extraits = SelecteurProjet()._recenser(dossier)

    interrogeables: set[str] = set()
    notions_du_projet: set[str] = set()
    for extrait in extraits:
        sujets = sujets_distincts(
            reperer(extrait.code, extrait.langage, extrait.chemin_fichier)
        )
        if len(sujets) < REPERES_MIN:
            continue
        interrogeables.add(extrait.identifiant)
        notions_du_projet.update(
            repere.notion for repere in sujets if repere.notion is not None
        )

    cartes = [entree for entree in entrees if entree.issue == CARTE]
    # Une fonction disparue du projet ne compte plus : la garder ferait un
    # numérateur qui dépasse son dénominateur après un remaniement.
    fonctions_vues = {
        entree.identifiant for entree in cartes if entree.identifiant in interrogeables
    }
    notions_vues = {
        entree.notion
        for entree in cartes
        if entree.notion is not None and entree.notion in notions_du_projet
    }

    return Couverture(
        fonctions_vues=len(fonctions_vues),
        fonctions_interrogeables=len(interrogeables),
        notions_vues=len(notions_vues),
        notions_du_projet=len(notions_du_projet),
        notions_restantes=tuple(sorted(notions_du_projet - notions_vues)),
    )
