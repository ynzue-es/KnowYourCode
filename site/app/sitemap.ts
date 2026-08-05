import type { MetadataRoute } from "next";

import { dernierePublication } from "@/lib/release";
import { ADRESSE } from "@/lib/site";

/** Le plan du site est reconstruit au même rythme que la page. */
export const revalidate = 300;

/**
 * Une seule page, mais datée : `lastModified` suit la dernière version
 * publiée, puisque c'est la seule chose qui change ici sans redéploiement.
 * Faute de version connue, on ne date rien plutôt que d'annoncer une
 * fraîcheur inventée.
 */
export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const publication = await dernierePublication();

  return [
    {
      url: ADRESSE,
      lastModified: publication?.publieeLe
        ? new Date(publication.publieeLe)
        : undefined,
      changeFrequency: "monthly",
      priority: 1,
    },
  ];
}
