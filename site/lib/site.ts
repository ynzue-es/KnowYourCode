/**
 * Les constantes du site, à un seul endroit.
 *
 * L'adresse est réglable au déploiement : une préproduction Vercel doit
 * pouvoir servir la même page sans annoncer l'adresse de production dans ses
 * balises canoniques, sans quoi les moteurs indexeraient la préproduction sous
 * le nom du site.
 */
export const ADRESSE =
  process.env.NEXT_PUBLIC_ADRESSE_SITE ?? "https://knowyourcode.fr";

export const NOM = "KnowYourCode";

export const TITRE =
  "KnowYourCode — on délègue le code, pas la compréhension";

export const DESCRIPTION =
  "Un utilitaire de barre de menus pour macOS. Il tire au hasard une fonction " +
  "du projet en cours et vous demande de l'expliquer. Un modèle tiers compare " +
  "votre explication au code et vous dit ce que vous avez oublié.";

export const AUTEUR = "Yannis Nzue Essono";
