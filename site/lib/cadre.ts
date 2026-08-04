"use client";

import {
  useEffect,
  useRef,
  useState,
  useSyncExternalStore,
  type RefObject,
} from "react";

/**
 * Dit si l'élément visé est à l'écran.
 *
 * Sert à couper les animations qui tournent en boucle dès qu'elles sortent du
 * cadre : un minuteur qui bat huit fois par seconde derrière deux écrans de
 * défilement ne fait que vider la batterie.
 */
export function useDansLeCadre<T extends Element>(
  seuil = 0.2,
): [RefObject<T | null>, boolean] {
  const cadre = useRef<T>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const element = cadre.current;
    if (!element) return;

    const observateur = new IntersectionObserver(
      ([entree]) => setVisible(entree.isIntersecting),
      { threshold: seuil },
    );
    observateur.observe(element);
    return () => observateur.disconnect();
  }, [seuil]);

  return [cadre, visible];
}

const REQUETE_SOBRE = "(prefers-reduced-motion: reduce)";

function ecouterMouvement(rappel: () => void) {
  const requete = window.matchMedia(REQUETE_SOBRE);
  requete.addEventListener("change", rappel);
  return () => requete.removeEventListener("change", rappel);
}

/**
 * Dit si le système réclame moins de mouvement, et le redit si le réglage
 * change en cours de route.
 *
 * Passer par `useSyncExternalStore` plutôt que par un effet évite la double
 * peinture : la valeur est lue au premier rendu client, pas après. Au rendu
 * serveur, où il n'y a pas de préférence à consulter, on répond `false` — le
 * mouvement est le cas courant, et l'hydratation corrige aussitôt.
 */
export function useMouvementSobre(): boolean {
  return useSyncExternalStore(
    ecouterMouvement,
    () => window.matchMedia(REQUETE_SOBRE).matches,
    () => false,
  );
}
