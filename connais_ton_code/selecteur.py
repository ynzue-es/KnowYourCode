"""Choix de l'extrait de code à faire expliquer."""

from __future__ import annotations

import random
from pathlib import Path
from typing import Iterable, Protocol, runtime_checkable

from .extraction import LANGAGES, fonctions
from .modeles import Extrait

# Trop courte, il n'y a rien à expliquer ; trop longue, on ne relit pas.
LIGNES_MIN = 4
LIGNES_MAX = 60

# Garde-fous du parcours : la sélection a lieu pendant que l'utilisateur
# attend, elle doit rester de l'ordre de la fraction de seconde.
FICHIERS_MAX = 600
OCTETS_MAX = 300_000

DOSSIERS_IGNORES = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "env",
        "node_modules",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "dist",
        "build",
        "out",
        ".next",
        ".turbo",
        "coverage",
        "site-packages",
        "vendor",
        "target",
        ".idea",
        ".vscode",
    }
)


@runtime_checkable
class Selecteur(Protocol):
    """Contrat : rendre un bout de code écrit dans le projet visé.

    L'orchestrateur passe les identifiants déjà vus et le dossier du projet
    sur lequel la session travaille. Rendre `None` est une réponse valable et
    veut dire « rien à demander » : la fenêtre reste alors masquée plutôt que
    d'afficher un extrait sans intérêt.

    L'appel a lieu sur le fil principal, juste avant l'affichage : il doit
    rester rapide.
    """

    def choisir(
        self, deja_vus: Iterable[str], dossier: Path | None = None
    ) -> Extrait | None:
        """Rend un extrait à faire expliquer, ou `None` si rien ne convient."""
        ...


class SelecteurProjet:
    """Tire une fonction au hasard dans le dossier du projet.

    Au hasard, et non « la plus récemment modifiée » : le code qu'on ne
    comprend plus n'est pas toujours celui qu'on vient d'écrire, et un tirage
    uniforme finit par tout couvrir sans rien décider.
    """

    def choisir(
        self, deja_vus: Iterable[str], dossier: Path | None = None
    ) -> Extrait | None:
        if dossier is None or not dossier.is_dir():
            return None

        candidats = self._recenser(dossier)
        if not candidats:
            return None

        vus = set(deja_vus)
        jamais_vus = [e for e in candidats if e.identifiant not in vus]
        # Une fois tout le projet parcouru, mieux vaut réviser que se taire.
        return random.choice(jamais_vus or candidats)

    def _recenser(self, dossier: Path) -> list[Extrait]:
        extraits: list[Extrait] = []
        for fichier in self._fichiers(dossier):
            langage = LANGAGES[fichier.suffix]
            try:
                if fichier.stat().st_size > OCTETS_MAX:
                    continue
                texte = fichier.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue

            try:
                relatif = fichier.relative_to(dossier).as_posix()
            except ValueError:
                relatif = fichier.name

            for fonction in fonctions(texte, langage):
                if not LIGNES_MIN <= fonction.nombre_de_lignes <= LIGNES_MAX:
                    continue
                # Un constructeur ou une méthode spéciale se raconte tout
                # seul : il n'y a rien à y comprendre qui ne soit dans le nom.
                if fonction.nom.startswith("__") and fonction.nom.endswith("__"):
                    continue
                extraits.append(
                    Extrait(
                        identifiant=f"{relatif}:{fonction.nom}",
                        chemin_fichier=relatif,
                        nom_fonction=fonction.nom,
                        langage=langage,
                        code=fonction.code,
                    )
                )
        return extraits

    def _fichiers(self, dossier: Path) -> list[Path]:
        trouves: list[Path] = []
        a_parcourir = [dossier]
        while a_parcourir and len(trouves) < FICHIERS_MAX:
            courant = a_parcourir.pop()
            try:
                entrees = list(courant.iterdir())
            except OSError:
                continue
            for entree in entrees:
                if entree.name.startswith(".") and entree.name not in {".claude"}:
                    continue
                if entree.is_dir():
                    if entree.name not in DOSSIERS_IGNORES:
                        a_parcourir.append(entree)
                elif entree.suffix in LANGAGES:
                    trouves.append(entree)
                    if len(trouves) >= FICHIERS_MAX:
                        break
        return trouves


_EXTRAITS_FACTICES: tuple[Extrait, ...] = (
    Extrait(
        identifiant="factice:agregation.py:regrouper_par_jour",
        chemin_fichier="services/agregation.py",
        nom_fonction="regrouper_par_jour",
        langage="python",
        code='''def regrouper_par_jour(evenements, fuseau="Europe/Paris"):
    """Regroupe des évènements par journée locale."""
    zone = ZoneInfo(fuseau)
    par_jour = defaultdict(list)

    for evenement in sorted(evenements, key=lambda e: e.horodatage):
        locale = evenement.horodatage.astimezone(zone)
        # Une journée d'usage commence à 4h : les sessions nocturnes
        # appartiennent à la veille, pas au petit matin suivant.
        if locale.hour < 4:
            locale -= timedelta(days=1)
        par_jour[locale.date()].append(evenement)

    return {jour: tuple(liste) for jour, liste in sorted(par_jour.items())}
''',
    ),
    Extrait(
        identifiant="factice:cache.py:memoriser_resultat",
        chemin_fichier="outils/cache.py",
        nom_fonction="memoriser_resultat",
        langage="python",
        code='''def memoriser_resultat(duree_secondes):
    def decorateur(fonction):
        cache = {}
        verrou = threading.Lock()

        @functools.wraps(fonction)
        def enveloppe(*arguments):
            maintenant = time.monotonic()
            with verrou:
                entree = cache.get(arguments)
                if entree is not None and maintenant - entree[0] < duree_secondes:
                    return entree[1]

            # Le calcul se fait hors du verrou : deux appels concurrents sur
            # une clé froide font le travail deux fois, ce qui coûte moins
            # cher que de sérialiser tous les appelants.
            valeur = fonction(*arguments)

            with verrou:
                cache[arguments] = (maintenant, valeur)
            return valeur

        return enveloppe

    return decorateur
''',
    ),
    Extrait(
        identifiant="factice:ListeFiltrable.tsx:ListeFiltrable",
        chemin_fichier="app/components/ListeFiltrable.tsx",
        nom_fonction="ListeFiltrable",
        langage="tsx",
        code='''export function ListeFiltrable({ elements, delaiMs = 250 }: Props) {
  const [saisie, setSaisie] = useState("");
  const [filtre, setFiltre] = useState("");
  const dernierRendu = useRef(0);

  useEffect(() => {
    const minuteur = setTimeout(() => setFiltre(saisie), delaiMs);
    return () => clearTimeout(minuteur);
  }, [saisie, delaiMs]);

  const visibles = useMemo(() => {
    dernierRendu.current += 1;
    const terme = filtre.trim().toLowerCase();
    if (!terme) return elements;
    return elements.filter((element) =>
      element.libelle.toLowerCase().includes(terme),
    );
  }, [elements, filtre]);

  return (
    <div className="flex flex-col gap-2">
      <input value={saisie} onChange={(e) => setSaisie(e.target.value)} />
      {visibles.map((element) => (
        <Ligne key={element.id} element={element} />
      ))}
    </div>
  );
}
''',
    ),
)


class SelecteurFactice:
    """Sert en boucle une petite liste d'extraits écrits en dur.

    Sert aux vérifications, et de repli quand le projet visé ne contient
    aucune fonction exploitable.
    """

    def __init__(self, extraits: tuple[Extrait, ...] = _EXTRAITS_FACTICES) -> None:
        self._extraits = extraits
        self._prochain = 0

    def choisir(
        self, deja_vus: Iterable[str], dossier: Path | None = None
    ) -> Extrait | None:
        if not self._extraits:
            return None

        vus = set(deja_vus)
        for decalage in range(len(self._extraits)):
            candidat = self._extraits[(self._prochain + decalage) % len(self._extraits)]
            if candidat.identifiant not in vus:
                self._prochain = (self._prochain + decalage + 1) % len(self._extraits)
                return candidat

        candidat = self._extraits[self._prochain]
        self._prochain = (self._prochain + 1) % len(self._extraits)
        return candidat
