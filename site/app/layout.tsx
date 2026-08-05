import type { Metadata, Viewport } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";

import { Ambiance } from "@/components/Ambiance";
import { URL_DEPOT } from "@/lib/release";
import { ADRESSE, AUTEUR, DESCRIPTION, NOM, TITRE } from "@/lib/site";

import "./globals.css";

/** Inter pour le texte, JetBrains Mono pour le code. Les deux sont exposées
 *  en variables CSS, que `globals.css` place en tête des piles de polices. */
const inter = Inter({
  subsets: ["latin"],
  variable: "--police-sans",
  display: "swap",
});

const jetbrains = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--police-mono",
  display: "swap",
});

export const metadata: Metadata = {
  metadataBase: new URL(ADRESSE),
  title: {
    default: TITRE,
    template: `%s — ${NOM}`,
  },
  description: DESCRIPTION,
  applicationName: NOM,
  authors: [{ name: AUTEUR, url: URL_DEPOT }],
  creator: AUTEUR,
  publisher: AUTEUR,
  category: "technology",
  keywords: [
    "KnowYourCode",
    "macOS",
    "barre de menus",
    "relecture de code",
    "revue de code",
    "Claude Code",
    "Mistral",
    "Python",
    "TypeScript",
    "outil pour développeurs",
  ],
  alternates: { canonical: "/" },
  openGraph: {
    type: "website",
    locale: "fr_FR",
    url: "/",
    siteName: NOM,
    title: TITRE,
    description: DESCRIPTION,
  },
  twitter: {
    card: "summary_large_image",
    title: TITRE,
    description: DESCRIPTION,
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      // Sans ces trois lignes, Google tronque l'aperçu de lui-même. Le site
      // tient en une page : autant qu'elle soit résumée en entier.
      "max-snippet": -1,
      "max-image-preview": "large",
      "max-video-preview": -1,
    },
  },
  // Le numéro de téléphone du pied de page n'existe pas : sans cela, Safari
  // transforme les numéros de version en liens d'appel.
  formatDetection: { telephone: false, address: false, email: false },
};

export const viewport: Viewport = {
  themeColor: "#0b0c0e",
  colorScheme: "dark",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="fr"
      className={`${inter.variable} ${jetbrains.variable} h-full antialiased`}
    >
      <body className="relative flex min-h-full flex-col">
        <Ambiance />
        {children}
      </body>
    </html>
  );
}
