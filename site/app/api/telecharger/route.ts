import { NextResponse } from "next/server";

import { dernierePublication, URL_PUBLICATIONS } from "@/lib/release";

/**
 * L'adresse de téléchargement, stable d'une version à l'autre.
 *
 * Le bouton de la page pointe ici et n'en bouge plus : c'est cette route qui
 * va demander à GitHub où se trouve le DMG de la dernière version, puis
 * redirige le navigateur vers lui. Si rien n'est trouvable — pas de version
 * publiée, pas de `.dmg` parmi les fichiers, API muette — on envoie sur la
 * page des versions plutôt que de rendre une erreur : l'utilisateur y verra
 * ce qui existe, ou qu'il n'existe rien encore.
 */
export async function GET() {
  const publication = await dernierePublication();
  const destination = publication?.urlDmg ?? URL_PUBLICATIONS;

  return NextResponse.redirect(destination, 302);
}
