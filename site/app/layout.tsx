import type { Metadata, Viewport } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";

import { Ambiance } from "@/components/Ambiance";

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

const TITRE = "KnowYourCode — connaître son code plutôt que son client";
const DESCRIPTION =
  "Un utilitaire de barre de menus pour macOS. Il tire au hasard une fonction du projet en cours et vous demande de l'expliquer. Un modèle tiers compare votre explication au code et vous dit ce que vous avez oublié.";

/** L'adresse publique du site, réglable au déploiement. */
const ADRESSE =
  process.env.NEXT_PUBLIC_ADRESSE_SITE ?? "https://knowyourcode.vercel.app";

export const metadata: Metadata = {
  metadataBase: new URL(ADRESSE),
  title: {
    default: TITRE,
    template: "%s — KnowYourCode",
  },
  description: DESCRIPTION,
  applicationName: "KnowYourCode",
  authors: [{ name: "Yannis Nzue Essono" }],
  creator: "Yannis Nzue Essono",
  keywords: [
    "KnowYourCode",
    "macOS",
    "barre de menus",
    "relecture de code",
    "Claude Code",
    "Python",
    "TypeScript",
  ],
  alternates: { canonical: "/" },
  openGraph: {
    type: "website",
    locale: "fr_FR",
    url: "/",
    siteName: "KnowYourCode",
    title: TITRE,
    description: DESCRIPTION,
  },
  twitter: {
    card: "summary_large_image",
    title: TITRE,
    description: DESCRIPTION,
  },
  robots: { index: true, follow: true },
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
