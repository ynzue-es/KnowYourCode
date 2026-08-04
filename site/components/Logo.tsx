import Image from "next/image";

type ProprietesLogo = {
  /** Côté du carré, en pixels. Le dessin est vectoriel, il suit. */
  taille: number;
  className?: string;
};

/**
 * Le logo de l'application, le même dessin que l'icône de la barre de menus.
 *
 * Servi tel quel, sans passer par l'optimiseur d'images : un SVG de huit
 * kilo-octets n'a rien à y gagner.
 */
export function Logo({ taille, className }: ProprietesLogo) {
  return (
    <Image
      src="/logo.svg"
      alt="Le logo de KnowYourCode : deux chevrons et une barre oblique dans une fenêtre de terminal."
      width={taille}
      height={taille}
      className={className}
      unoptimized
      priority
    />
  );
}
