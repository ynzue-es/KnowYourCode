import type { ReactNode } from "react";

import { Revelation } from "@/components/Revelation";

type ProprietesSection = {
  /** L'ancre, reprise par les liens de l'entête. */
  id: string;
  /** Le petit intitulé posé au-dessus du titre. */
  surtitre?: string;
  titre: string;
  /** Le paragraphe d'introduction, sous le titre. */
  chapeau?: ReactNode;
  children?: ReactNode;
};

/**
 * Une section de la page : même rythme vertical, même largeur de colonne,
 * même hiérarchie de titres partout. L'entête et le contenu montent l'un
 * après l'autre à l'entrée dans le cadre.
 */
export function Section({
  id,
  surtitre,
  titre,
  chapeau,
  children,
}: ProprietesSection) {
  return (
    <section
      id={id}
      aria-labelledby={`${id}-titre`}
      className="border-bordure/60 relative border-t px-5 py-20 sm:px-6 sm:py-32"
    >
      {/* Le trait du haut n'est pas uniforme : il s'éteint vers les bords, ce
          qui évite la rayure d'un bout à l'autre de l'écran. */}
      <div
        aria-hidden="true"
        className="via-bordure-vive absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent to-transparent"
      />

      <div className="mx-auto w-full max-w-5xl">
        <Revelation className="max-w-2xl">
          <header>
            {surtitre ? (
              <p className="text-accent/80 mb-3 flex items-center gap-3 font-mono text-[0.68rem] tracking-[0.2em] uppercase">
                <span aria-hidden="true" className="bg-accent/40 h-px w-6" />
                {surtitre}
              </p>
            ) : null}
            <h2
              id={`${id}-titre`}
              className="text-encre text-[1.35rem] font-semibold tracking-tight text-balance sm:text-3xl"
            >
              {titre}
            </h2>
            {chapeau ? (
              <div className="text-attenue mt-4 space-y-3 text-[0.92rem] leading-relaxed sm:text-base">
                {chapeau}
              </div>
            ) : null}
          </header>
        </Revelation>

        {children ? (
          <Revelation retard={120} className="mt-12">
            {children}
          </Revelation>
        ) : null}
      </div>
    </section>
  );
}
