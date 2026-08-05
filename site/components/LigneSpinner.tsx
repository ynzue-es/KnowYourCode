"use client";

import { useEffect, useState } from "react";

import { useDansLeCadre } from "@/lib/cadre";

/** Les phrases telles qu'elles sont écrites dans le fichier : nues, sans la
 *  balise, que l'application ajoute à la pose. */
const PHRASES = [
  "Révise pendant que je travaille",
  "Relis avant de valider",
  "Tu saurais réécrire ça sans moi ?",
  "Une fonction t'attend dans la barre de menus",
  "Explique-moi ce fichier, à froid",
];

/** Les glyphes du compteur d'attente de Claude Code, dans leur ordre. */
const GLYPHES = ["✳", "✻", "✽", "✢", "·", "✢", "✽", "✻"];

/** Le battement du glyphe, et le temps qu'une phrase reste posée. */
const BATTEMENT = 130;
const DUREE_PHRASE = 4200;

/**
 * Le compteur d'attente de Claude Code, rejoué. C'est la surface où le rappel
 * se glisse : le glyphe tourne, la phrase change, les secondes montent.
 */
export function LigneSpinner() {
  const [cadre, visible] = useDansLeCadre<HTMLDivElement>(0.4);
  const [glyphe, setGlyphe] = useState(0);
  const [phrase, setPhrase] = useState(0);
  const [secondes, setSecondes] = useState(0);
  const [enTransition, setEnTransition] = useState(false);

  useEffect(() => {
    if (!visible) return;
    const battement = setInterval(
      () => setGlyphe((n) => (n + 1) % GLYPHES.length),
      BATTEMENT,
    );
    const horloge = setInterval(() => setSecondes((n) => n + 1), 1000);
    return () => {
      clearInterval(battement);
      clearInterval(horloge);
    };
  }, [visible]);

  /* Le changement de phrase se fait en deux temps : on l'efface, on la
     remplace, on la ramène. Sans le fondu, elle claque. */
  useEffect(() => {
    if (!visible) return;
    const rotation = setInterval(() => {
      setEnTransition(true);
      setTimeout(() => {
        setPhrase((n) => (n + 1) % PHRASES.length);
        setSecondes(0);
        setEnTransition(false);
      }, 260);
    }, DUREE_PHRASE);
    return () => clearInterval(rotation);
  }, [visible]);

  return (
    <div
      ref={cadre}
      className="border-bordure bg-panneau-clair/70 relative overflow-hidden rounded-xl border backdrop-blur"
    >
      <div className="border-bordure text-discret flex items-center gap-2 border-b px-4 py-2 font-mono text-xs">
        <span aria-hidden="true" className="flex gap-1.5">
          <span className="h-2 w-2 rounded-full bg-[#ff5f57]/70" />
          <span className="h-2 w-2 rounded-full bg-[#febc2e]/70" />
          <span className="h-2 w-2 rounded-full bg-[#28c840]/70" />
        </span>
        Terminal
      </div>

      <div
        className="px-4 py-4 font-mono text-[0.8rem] leading-relaxed sm:text-[0.85rem]"
        role="img"
        aria-label={`Le compteur d'attente de Claude Code affiche : ${PHRASES[phrase]}`}
      >
        <p className="flex flex-wrap items-baseline gap-x-2">
          <span aria-hidden="true" className="text-accent w-[1ch] shrink-0">
            {GLYPHES[glyphe]}
          </span>
          <span
            aria-hidden="true"
            className={`text-encre min-w-0 transition-opacity duration-200 ${
              enTransition ? "opacity-0" : "opacity-100"
            }`}
          >
            <span className="text-discret">&lt;kyc&gt;</span>
            🧠 {PHRASES[phrase]}
            <span className="text-discret">&lt;/kyc&gt;</span>
          </span>
        </p>
        <p aria-hidden="true" className="text-discret mt-1">
          … ({secondes}s · esc to interrupt)
        </p>
      </div>

      {/* Une lueur qui traverse le bas du bloc : le seul rappel que quelque
          chose tourne, quand la phrase, elle, ne bouge pas. */}
      <div
        aria-hidden="true"
        className="absolute inset-x-0 bottom-0 h-px overflow-hidden"
      >
        <div className="via-accent anime-balayage h-px w-1/3 bg-gradient-to-r from-transparent to-transparent" />
      </div>
    </div>
  );
}
