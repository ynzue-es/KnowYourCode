import type { ReactNode } from "react";

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
 * même hiérarchie de titres partout.
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
      className="border-t border-bordure/70 px-6 py-20 sm:py-24"
    >
      <div className="mx-auto w-full max-w-4xl">
        <header className="max-w-2xl">
          {surtitre ? (
            <p className="mb-3 font-mono text-xs tracking-[0.18em] text-discret uppercase">
              {surtitre}
            </p>
          ) : null}
          <h2
            id={`${id}-titre`}
            className="text-2xl font-semibold tracking-tight text-encre sm:text-3xl"
          >
            {titre}
          </h2>
          {chapeau ? (
            <div className="mt-5 space-y-4 text-base leading-relaxed text-attenue sm:text-lg">
              {chapeau}
            </div>
          ) : null}
        </header>
        {children ? <div className="mt-10">{children}</div> : null}
      </div>
    </section>
  );
}

type ProprietesCarte = {
  titre: string;
  children: ReactNode;
};

/** Un bloc encadré, du même gris que le panneau de l'application. */
export function Carte({ titre, children }: ProprietesCarte) {
  return (
    <article className="rounded-2xl border border-bordure bg-panneau p-6 sm:p-7">
      <h3 className="text-base font-semibold text-encre">{titre}</h3>
      <div className="mt-3 space-y-3 text-[0.95rem] leading-relaxed text-attenue">
        {children}
      </div>
    </article>
  );
}
