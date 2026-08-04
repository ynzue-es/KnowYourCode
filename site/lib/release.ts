/**
 * Les métadonnées de la dernière version publiée.
 *
 * Le DMG ne vit pas sur Vercel : il pèse trop pour l'offre Hobby. Il est
 * déposé dans les Releases du dépôt, et le site ne fait que pointer vers lui.
 * Tout ce qui suit doit donc supporter que GitHub soit injoignable, que le
 * quota d'appels soit épuisé, ou qu'aucune version n'ait encore été publiée :
 * dans ces cas-là on rend `null`, jamais une erreur. Le bouton de
 * téléchargement reste affiché, la mention de version disparaît.
 */

export const PROPRIETAIRE = "ynzue-es";
export const DEPOT = "KnowYourCode";

export const URL_DEPOT = `https://github.com/${PROPRIETAIRE}/${DEPOT}`;
export const URL_PUBLICATIONS = `${URL_DEPOT}/releases`;
export const URL_LICENCE = `${URL_DEPOT}/blob/main/LICENSE`;

const URL_API = `https://api.github.com/repos/${PROPRIETAIRE}/${DEPOT}/releases/latest`;

/** Cinq minutes : assez pour absorber un pic, assez court pour qu'une
 *  nouvelle version apparaisse sans redéploiement. */
export const DUREE_CACHE = 300;

type AssetGitHub = {
  name?: string;
  size?: number;
  browser_download_url?: string;
};

type PublicationGitHub = {
  tag_name?: string;
  html_url?: string;
  published_at?: string;
  assets?: AssetGitHub[];
};

export type Publication = {
  /** Le tag tel que publié, par exemple `v1.0.0`. */
  version: string;
  /** La taille du DMG en mégaoctets, arrondie. `null` si GitHub ne la donne pas. */
  tailleMo: number | null;
  /** La date de publication au format ISO, ou `null`. */
  publieeLe: string | null;
  /** La page de la version sur GitHub. */
  urlPublication: string;
  /** Le lien direct vers le DMG, celui vers lequel la route redirige. */
  urlDmg: string;
};

/** L'API GitHub exige un `User-Agent` et refuse les requêtes qui n'en ont pas. */
function entetes(): HeadersInit {
  const entetes: Record<string, string> = {
    Accept: "application/vnd.github+json",
    "User-Agent": `${DEPOT}-site`,
    "X-GitHub-Api-Version": "2022-11-28",
  };

  // Facultatif : sans jeton, l'API accorde soixante appels par heure et par
  // adresse, ce qui suffit largement vu le cache. Avec, cinq mille.
  const jeton = process.env.GITHUB_TOKEN;
  if (jeton) {
    entetes.Authorization = `Bearer ${jeton}`;
  }

  return entetes;
}

/**
 * La dernière version publiée, ou `null` si rien n'est exploitable.
 *
 * Ne lève jamais : un build ne doit pas échouer parce que l'API GitHub a
 * répondu de travers.
 */
export async function dernierePublication(): Promise<Publication | null> {
  try {
    const reponse = await fetch(URL_API, {
      headers: entetes(),
      next: { revalidate: DUREE_CACHE },
    });

    if (!reponse.ok) {
      return null;
    }

    const publication = (await reponse.json()) as PublicationGitHub;
    const dmg = publication.assets?.find(
      (asset) =>
        typeof asset.browser_download_url === "string" &&
        typeof asset.name === "string" &&
        asset.name.toLowerCase().endsWith(".dmg"),
    );

    if (!dmg?.browser_download_url) {
      return null;
    }

    return {
      version: publication.tag_name ?? "",
      tailleMo:
        typeof dmg.size === "number" && dmg.size > 0
          ? Math.round(dmg.size / 1_000_000)
          : null,
      publieeLe: publication.published_at ?? null,
      urlPublication: publication.html_url ?? URL_PUBLICATIONS,
      urlDmg: dmg.browser_download_url,
    };
  } catch {
    return null;
  }
}

/** « 4 mars 2026 », ou une chaîne vide si la date est absente ou illisible. */
export function dateEnFrancais(iso: string | null): string {
  if (!iso) {
    return "";
  }

  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return "";
  }

  return new Intl.DateTimeFormat("fr-FR", {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  }).format(date);
}
