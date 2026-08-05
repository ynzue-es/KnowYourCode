"use client";

import type { MouseEvent, ReactNode } from "react";

type ProprietesCarte = {
  titre: string;
  /** Un chiffre ou un sigle monospace, posé en tête de carte. */
  marque?: string;
  children: ReactNode;
};

/**
 * Un bloc encadré, du même gris que le panneau de l'application. Sa bordure
 * s'éclaire là où passe le pointeur.
 *
 * La position est écrite dans deux variables CSS plutôt que dans l'état React :
 * un `setState` à chaque pixel parcouru redéclencherait le rendu de toute la
 * grille de cartes pour ne déplacer qu'un dégradé.
 */
export function Carte({ titre, marque, children }: ProprietesCarte) {
  const suivre = (evenement: MouseEvent<HTMLElement>) => {
    const cadre = evenement.currentTarget.getBoundingClientRect();
    evenement.currentTarget.style.setProperty(
      "--pointeur-x",
      `${evenement.clientX - cadre.left}px`,
    );
    evenement.currentTarget.style.setProperty(
      "--pointeur-y",
      `${evenement.clientY - cadre.top}px`,
    );
  };

  return (
    <article
      onMouseMove={suivre}
      className="border-bordure bg-panneau/60 bordure-suiveuse hover:bg-panneau relative rounded-2xl border p-6 backdrop-blur-sm transition-colors duration-300 sm:p-7"
    >
      <div className="flex items-baseline gap-3">
        {marque ? (
          <span
            aria-hidden="true"
            className="text-accent/70 font-mono text-[0.68rem] tracking-widest"
          >
            {marque}
          </span>
        ) : null}
        <h3 className="text-encre text-[0.95rem] font-semibold">{titre}</h3>
      </div>
      <div className="text-attenue mt-2.5 space-y-2.5 text-[0.88rem] leading-relaxed">
        {children}
      </div>
    </article>
  );
}
