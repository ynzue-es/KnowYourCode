"use client";

import { useEffect, useState } from "react";

import { Logo } from "@/components/Logo";

const NAVIGATION = [
  { id: "principe", intitule: "Le principe" },
  { id: "surfaces", intitule: "Les surfaces" },
  { id: "rappel", intitule: "Le rappel" },
  { id: "fonctionnement", intitule: "Fonctionnement" },
  { id: "installation", intitule: "Installation" },
];

type ProprietesEntete = {
  lienTelechargement: string;
};

/**
 * L'entête collante : une jauge de progression au ras du haut, et le lien de
 * la section en cours mis en avant. Les deux se calent sur le défilement.
 */
export function Entete({ lienTelechargement }: ProprietesEntete) {
  const [avancement, setAvancement] = useState(0);
  const [pose, setPose] = useState(false);
  const [courante, setCourante] = useState<string | null>(null);

  /* La jauge suit le défilement. `requestAnimationFrame` sert d'étranglement :
     l'événement part à chaque pixel, le rendu n'a besoin que d'une image. */
  useEffect(() => {
    let enAttente = false;

    const mesurer = () => {
      enAttente = false;
      const parcourable =
        document.documentElement.scrollHeight - window.innerHeight;
      setAvancement(parcourable > 0 ? window.scrollY / parcourable : 0);
      setPose(window.scrollY > 8);
    };

    const auDefilement = () => {
      if (enAttente) return;
      enAttente = true;
      requestAnimationFrame(mesurer);
    };

    mesurer();
    window.addEventListener("scroll", auDefilement, { passive: true });
    window.addEventListener("resize", auDefilement);
    return () => {
      window.removeEventListener("scroll", auDefilement);
      window.removeEventListener("resize", auDefilement);
    };
  }, []);

  /* La section courante est la dernière dont le titre a franchi le haut de
     l'écran. Une bande étroite sous l'entête sert de ligne de mire : c'est ce
     qui reste visible quand deux sections se croisent. */
  useEffect(() => {
    const sections = NAVIGATION.map((lien) =>
      document.getElementById(lien.id),
    ).filter((element): element is HTMLElement => element !== null);
    if (sections.length === 0) return;

    const observateur = new IntersectionObserver(
      (entrees) => {
        const visibles = entrees.filter((entree) => entree.isIntersecting);
        if (visibles.length > 0) {
          setCourante(visibles[visibles.length - 1].target.id);
        }
      },
      { rootMargin: "-20% 0px -70% 0px" },
    );

    sections.forEach((section) => observateur.observe(section));
    return () => observateur.disconnect();
  }, []);

  return (
    <header
      className={`sticky top-0 z-30 transition-colors duration-300 ${
        pose
          ? "border-bordure/70 bg-fond/80 border-b backdrop-blur-xl"
          : "border-b border-transparent"
      }`}
    >
      {/* La jauge. Elle est portée par une transformation, pas par une largeur :
          c'est la seule façon de la faire avancer sans relayout. */}
      <div
        aria-hidden="true"
        className="absolute inset-x-0 top-0 h-px origin-left bg-gradient-to-r from-transparent via-[var(--color-accent)] to-[var(--color-menthe)]"
        style={{ transform: `scaleX(${avancement})` }}
      />

      <div className="mx-auto flex h-16 w-full max-w-5xl items-center justify-between gap-6 px-6">
        <a href="#haut" className="flex shrink-0 items-center gap-2.5 rounded-md">
          <Logo taille={26} className="rounded-[7px]" />
          <span className="text-encre text-sm font-semibold tracking-tight">
            KnowYourCode
          </span>
        </a>

        <nav aria-label="Sections de la page" className="hidden lg:block">
          <ul className="flex items-center gap-1 text-sm">
            {NAVIGATION.map((lien) => {
              const active = courante === lien.id;
              return (
                <li key={lien.id}>
                  <a
                    href={`#${lien.id}`}
                    aria-current={active ? "true" : undefined}
                    className={`relative rounded-md px-3 py-1.5 transition-colors duration-200 ${
                      active
                        ? "text-encre bg-panneau"
                        : "text-attenue hover:text-encre"
                    }`}
                  >
                    {lien.intitule}
                  </a>
                </li>
              );
            })}
          </ul>
        </nav>

        <a
          href={lienTelechargement}
          className="bg-encre hover:bg-encre/90 shrink-0 rounded-full px-4 py-1.5 text-sm font-medium text-[#0b0c0e] transition-all duration-200 hover:shadow-[0_0_24px_-4px] hover:shadow-white/30"
        >
          Télécharger
        </a>
      </div>
    </header>
  );
}
