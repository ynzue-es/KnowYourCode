"""Choix de l'extrait de code sur lequel poser une série de cartes."""

from __future__ import annotations

import random
from pathlib import Path
from typing import Iterable, Protocol, runtime_checkable

from .extraction import LANGAGES, fonctions
from .modeles import Extrait
from .reperage import Repere, reperer

# Trop courte, il n'y a rien à expliquer ; trop longue, on ne relit pas.
LIGNES_MIN = 4
LIGNES_MAX = 60

# Garde-fous du parcours : la sélection a lieu pendant que l'utilisateur
# attend, elle doit rester de l'ordre de la fraction de seconde.
FICHIERS_MAX = 600
OCTETS_MAX = 300_000

# Le repérage coûte environ un demi-millième de seconde par fonction. C'est
# gratuit à l'unité et ruineux en masse : sur ce dépôt, les mille extraits
# recensés font une demi-seconde à eux seuls, doublant le prix de l'appel.
# On mélange donc les candidats et on n'en analyse que jusqu'à en tenir assez
# pour tirer. Le plafond borne le pire cas — un projet où rien n'est repéré,
# où l'on chercherait sinon jusqu'au dernier extrait.
ANALYSES_MAX = 140
RETENUS_ASSEZ = 24

# Le meilleur repère fixe le poids : c'est lui qui donnera son sujet à la
# première carte, et une faille de sécurité mérite d'être posée même si le
# reste de la fonction est banal. Les repères suivants ne font qu'un appoint,
# parce qu'ils ne changent pas la nature de l'extrait — ils promettent
# seulement de quoi tenir quatre cartes sans se répéter.
#
# L'appoint est plafonné, et c'est tout l'intérêt du barème : sans plafond,
# une fonction longue et bavarde finirait par passer devant un extrait qui
# porte un vrai piège, alors qu'elle n'a que le nombre pour elle. Avec ces
# valeurs, un extrait bourré de tournures courantes plafonne à 45 et ne
# rattrape jamais la moindre notion isolée, qui vaut 55.
APPOINT_RICHESSE = 5
REPERES_EN_APPOINT = 3

def _autre_copie(dossier: Path) -> bool:
    """Dit si ce dossier est une autre copie du dépôt plutôt qu'un sous-dossier.

    Un worktree git — ceux que Claude Code range sous `.claude/worktrees/`,
    ceux qu'on crée à la main — contient le projet entier, souvent sur une
    autre branche et parfois à moitié fini. Le parcourir ferait poser des
    questions sur du code qui n'est pas celui sur lequel on travaille, et
    reposer la même fonction autant de fois qu'il y a de copies.

    Le signe est le même dans tous les cas : un `.git` à la racine du dossier.
    C'est un fichier dans un worktree, un dossier dans un clone imbriqué ; les
    deux disent « ici commence un autre dépôt », et les deux s'arrêtent ici.
    """
    return (dossier / ".git").exists()


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


def poids_de(reperes: list[Repere]) -> int:
    """Pèse un extrait d'après les repères qu'il porte, le meilleur en tête.

    `reperer` rend déjà sa liste triée : on lit le premier et on compte les
    autres, sans les relire.
    """
    appoint = APPOINT_RICHESSE * min(len(reperes) - 1, REPERES_EN_APPOINT)
    return reperes[0].poids + appoint


class SelecteurProjet:
    """Tire une fonction du projet parmi celles qui ont quelque chose à dire.

    Au hasard, et non « la plus récemment modifiée » : le code qu'on ne
    comprend plus n'est pas toujours celui qu'on vient d'écrire. Mais plus au
    hasard uniforme : sur ce dépôt, deux fonctions sur trois ne portent aucun
    repère, et une ouverture sur un accesseur de trois lignes est une
    interruption pour rien. On ne garde donc que les extraits repérés, et on
    les tire pondérés — sans les classer, sinon ce serait toujours les cinq
    mêmes.
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
        # Le repli joue aussi quand le neuf ne donne rien de repérable : mieux
        # vaut reposer une bonne fonction que d'en servir une vide.
        retenus = self._peser(jamais_vus) or self._peser(candidats)
        if not retenus:
            return None

        extraits = [extrait for extrait, _ in retenus]
        poids = [poids for _, poids in retenus]
        return random.choices(extraits, weights=poids)[0]

    def _peser(self, candidats: list[Extrait]) -> list[tuple[Extrait, int]]:
        """Analyse un échantillon des candidats et pèse ceux qui sont repérés.

        Le mélange n'est pas une coquetterie : c'est lui qui fait que
        l'échantillon change à chaque ouverture. La pondération ne joue qu'à
        l'intérieur de cet échantillon, ce qui suffit — on ne cherche pas le
        meilleur extrait du projet, seulement un bon.
        """
        echantillon = list(candidats)
        random.shuffle(echantillon)

        retenus: list[tuple[Extrait, int]] = []
        for extrait in echantillon[:ANALYSES_MAX]:
            reperes = reperer(extrait.code, extrait.langage)
            if not reperes:
                continue
            retenus.append((extrait, poids_de(reperes)))
            if len(retenus) >= RETENUS_ASSEZ:
                break
        return retenus

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
                    if entree.name not in DOSSIERS_IGNORES and not _autre_copie(
                        entree
                    ):
                        a_parcourir.append(entree)
                elif entree.suffix in LANGAGES:
                    trouves.append(entree)
                    if len(trouves) >= FICHIERS_MAX:
                        break
        return trouves


# Chacun porte de quoi tenir une série entière, et les quatre couvrent les
# trois familles de repères, sécurité comprise : ils servent de repli quand le
# projet visé ne donne rien, et de matière aux vérifications, qui exigent que
# tout extrait servi soit repéré.
_EXTRAITS_FACTICES: tuple[Extrait, ...] = (
    Extrait(
        identifiant="factice:agregation.py:regrouper_par_jour",
        chemin_fichier="services/agregation.py",
        nom_fonction="regrouper_par_jour",
        langage="python",
        code='''def regrouper_par_jour(evenements, fuseau="Europe/Paris", types_ignores=[]):
    """Regroupe des évènements par journée locale."""
    zone = ZoneInfo(fuseau)
    par_jour = defaultdict(list)

    for evenement in sorted(evenements, key=lambda e: e.horodatage):
        if evenement.type in types_ignores:
            continue
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
    Extrait(
        identifiant="factice:entrepot.py:chercher_commandes",
        chemin_fichier="services/entrepot.py",
        nom_fonction="chercher_commandes",
        langage="python",
        code='''def chercher_commandes(connexion, client, statut=None, limite=50):
    conditions = [f"client_id = '{client}'"]
    if statut is not None:
        conditions.append(f"statut = '{statut}'")

    requete = "SELECT * FROM commandes WHERE " + " AND ".join(conditions)
    curseur = connexion.cursor()
    try:
        curseur.execute(requete + f" ORDER BY cree_le DESC LIMIT {limite}")
        return [Commande(*ligne) for ligne in curseur.fetchall()]
    finally:
        curseur.close()
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
