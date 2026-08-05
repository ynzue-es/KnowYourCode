"use client";

import {
  useEffect,
  useRef,
  useState,
  type ElementType,
  type ReactNode,
} from "react";

type ProprietesRevelation = {
  children: ReactNode;
  /** Le retard à l'apparition, pour décaler les éléments d'une même rangée. */
  retard?: number;
  /** La balise à produire — `div` par défaut, `li` dans une liste. */
  as?: ElementType;
  className?: string;
};

/**
 * Fait monter son contenu à la première entrée dans le cadre, puis se tait :
 * l'observateur est débranché aussitôt. Une révélation qui se rejoue à chaque
 * passage transforme un retour en arrière en diaporama.
 *
 * Le mouvement lui-même est décrit par `.a-reveler` dans `globals.css`, qui
 * l'annule quand le système réclame moins d'animation.
 */
export function Revelation({
  children,
  retard = 0,
  as: Balise = "div",
  className = "",
}: ProprietesRevelation) {
  const cadre = useRef<HTMLElement>(null);
  const [vu, setVu] = useState(false);

  useEffect(() => {
    const element = cadre.current;
    if (!element) return;

    const observateur = new IntersectionObserver(
      ([entree]) => {
        if (!entree.isIntersecting) return;
        setVu(true);
        observateur.disconnect();
      },
      // Une marge négative en bas retarde le déclenchement : l'élément doit
      // être franchement entré, pas seulement affleurer.
      { rootMargin: "0px 0px -12% 0px", threshold: 0.1 },
    );

    observateur.observe(element);
    return () => observateur.disconnect();
  }, []);

  return (
    <Balise
      ref={cadre}
      className={`a-reveler ${vu ? "vu" : ""} ${className}`}
      style={{ "--retard": `${retard}ms` } as React.CSSProperties}
    >
      {children}
    </Balise>
  );
}
