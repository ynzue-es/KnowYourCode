/**
 * Le décor de la page : une trame de grille et deux halos qui dérivent
 * lentement derrière le contenu.
 *
 * Tout est posé en fixe et en `pointer-events: none` : rien ici n'intercepte
 * un clic, et rien ne défile — le fond reste immobile pendant que la page
 * glisse dessus, ce qui donne la profondeur sans coûter un seul repaint.
 */
export function Ambiance() {
  return (
    <div
      aria-hidden="true"
      className="pointer-events-none fixed inset-0 -z-10 overflow-hidden"
    >
      <div className="grille absolute inset-0" />

      <div
        className="halo anime-derive absolute -top-40 left-1/2 h-[38rem] w-[38rem] -translate-x-1/2 rounded-full opacity-25"
        style={{
          background:
            "radial-gradient(circle, var(--color-accent), transparent 70%)",
        }}
      />

      <div
        className="halo anime-derive absolute top-[38rem] -right-40 h-[30rem] w-[30rem] rounded-full opacity-[0.12]"
        style={{
          animationDelay: "-9s",
          background:
            "radial-gradient(circle, var(--color-menthe), transparent 70%)",
        }}
      />

      {/* Un voile sombre en bas de page : les halos ne doivent pas remonter
          dans le pied de page, où le texte est déjà discret. */}
      <div className="from-fond absolute inset-x-0 bottom-0 h-64 bg-gradient-to-t to-transparent" />
    </div>
  );
}
