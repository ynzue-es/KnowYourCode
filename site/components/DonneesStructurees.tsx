import type { Publication } from "@/lib/release";
import { URL_DEPOT, URL_LICENCE } from "@/lib/release";
import { ADRESSE, AUTEUR, DESCRIPTION, NOM } from "@/lib/site";

type ProprietesDonnees = {
  publication: Publication | null;
};

/**
 * Les données structurées de la page, au format JSON-LD.
 *
 * C'est ce qui permet à un moteur de comprendre qu'il a affaire à un logiciel
 * téléchargeable, et non à un article : le prix, le système requis et la
 * version s'affichent alors dans le résultat de recherche.
 *
 * Les champs que GitHub n'a pas donnés sont omis, jamais devinés — annoncer
 * une version qu'on ignore vaut moins que ne rien annoncer.
 */
export function DonneesStructurees({ publication }: ProprietesDonnees) {
  const logiciel = {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    name: NOM,
    description: DESCRIPTION,
    url: ADRESSE,
    applicationCategory: "DeveloperApplication",
    operatingSystem: "macOS 12.0 or later",
    inLanguage: "fr",
    license: URL_LICENCE,
    codeRepository: URL_DEPOT,
    author: {
      "@type": "Person",
      name: AUTEUR,
      url: URL_DEPOT,
    },
    offers: {
      "@type": "Offer",
      price: "0",
      priceCurrency: "EUR",
      availability: "https://schema.org/InStock",
    },
    ...(publication?.version ? { softwareVersion: publication.version } : {}),
    ...(publication?.publieeLe ? { datePublished: publication.publieeLe } : {}),
    ...(publication?.urlDmg ? { downloadUrl: publication.urlDmg } : {}),
    ...(publication?.tailleMo
      ? { fileSize: `${publication.tailleMo} MB` }
      : {}),
  };

  return (
    <script
      type="application/ld+json"
      // Le contenu est construit ici, à partir de constantes et de champs que
      // `lib/release` a déjà validés : rien qui vienne d'une saisie.
      dangerouslySetInnerHTML={{ __html: JSON.stringify(logiciel) }}
    />
  );
}
