import type { MetadataRoute } from "next";

import { DESCRIPTION, NOM } from "@/lib/site";

/**
 * Le manifeste, pour l'épinglage sur un écran d'accueil.
 *
 * `display: browser` et non `standalone` : le site est une page de
 * présentation, pas une application. La déguiser en application installée
 * priverait le visiteur de sa barre d'adresse pour rien.
 */
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: NOM,
    short_name: NOM,
    description: DESCRIPTION,
    start_url: "/",
    display: "browser",
    background_color: "#0b0c0e",
    theme_color: "#0b0c0e",
    lang: "fr",
    categories: ["developer", "productivity", "utilities"],
    icons: [
      {
        src: "/logo.svg",
        sizes: "any",
        type: "image/svg+xml",
        purpose: "any",
      },
    ],
  };
}
