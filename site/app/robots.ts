import type { MetadataRoute } from "next";

import { ADRESSE } from "@/lib/site";

/**
 * Le fichier `robots.txt`, engendré.
 *
 * `/api/` est écarté : la route de téléchargement redirige vers GitHub et n'a
 * rien à indexer — la faire visiter par un robot ne ferait que gonfler le
 * compteur de téléchargements sans qu'un humain l'ait demandé.
 */
export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: "/",
      disallow: "/api/",
    },
    sitemap: `${ADRESSE}/sitemap.xml`,
    host: ADRESSE,
  };
}
