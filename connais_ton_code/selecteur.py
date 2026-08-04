"""Choix de l'extrait de code à faire expliquer.

BOUCHON : seule la version factice existe pour l'instant.
"""

from __future__ import annotations

from typing import Iterable, Protocol, runtime_checkable

from .modeles import Extrait


@runtime_checkable
class Selecteur(Protocol):
    """Contrat : rendre un bout de code que l'utilisateur a écrit récemment.

    L'orchestrateur passe les identifiants déjà vus ; à charge du sélecteur de
    les éviter tant qu'il a mieux à proposer. Rendre `None` est une réponse
    valable et veut dire « rien à demander maintenant » : la fenêtre reste
    alors masquée plutôt que d'afficher un extrait sans intérêt.

    L'appel a lieu sur le fil principal, juste avant l'affichage : il doit
    rester rapide.

    Implémentation prévue : lire le diff des sept derniers jours, en extraire
    les fonctions modifiées, et préférer les plus grosses et les moins
    récemment interrogées.
    """

    def choisir(self, deja_vus: Iterable[str]) -> Extrait | None:
        """Rend un extrait à faire expliquer, ou `None` si rien ne convient."""
        ...


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

    Les extraits déjà vus sont écartés en priorité, mais une fois la liste
    épuisée on recommence au lieu de rendre `None` : sans vraie source de code,
    rendre `None` rendrait l'application intestable au deuxième lancement.
    """

    def __init__(self, extraits: tuple[Extrait, ...] = _EXTRAITS_FACTICES) -> None:
        self._extraits = extraits
        self._prochain = 0

    def choisir(self, deja_vus: Iterable[str]) -> Extrait | None:
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
