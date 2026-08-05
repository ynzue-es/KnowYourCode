import type { CSSProperties } from "react";

type ProprietesFaisceau = {
  /** Longueur du trait lumineux, en pixels. */
  taille?: number;
  /** Durée d'un tour complet, en secondes. */
  duree?: number;
  /** Épaisseur du liseré, en pixels. */
  epaisseur?: number;
  /** Décalage au départ, en secondes : deux faisceaux sur le même cadre ne
   *  doivent pas partir ensemble. */
  retard?: number;
  depuis?: string;
  vers?: string;
  className?: string;
};

/**
 * Un trait lumineux qui fait le tour de la bordure de son parent.
 *
 * Repris de `border-beam` de MagicUI (21st.dev), adapté à ce dépôt : le `cn`
 * d'origine est remplacé par une chaîne — le projet n'a ni `clsx` ni
 * `tailwind-merge`, et n'en fera pas entrer pour concaténer deux classes — et
 * les couleurs par défaut sont celles du site plutôt que l'orange et le
 * violet d'origine.
 *
 * Le parent doit être en `relative` et porter son propre arrondi : le
 * faisceau hérite du rayon, il ne le décide pas.
 *
 * Le mouvement tient à `offset-path`, qui fait courir le pseudo-élément le
 * long d'un rectangle arrondi. Là où la propriété manque, le trait reste posé
 * dans un coin sans bouger : c'est discret, et la bordure du parent, elle,
 * est toujours là.
 *
 * Le dessin lui-même est dans `globals.css`, sous `.faisceau` : le masque qui
 * ne garde que le liseré demande une variante préfixée que les classes
 * utilitaires ne savent pas écrire.
 */
export function FaisceauBordure({
  taille = 220,
  duree = 9,
  epaisseur = 1.5,
  retard = 0,
  depuis = "var(--color-accent)",
  vers = "var(--color-menthe)",
  className = "",
}: ProprietesFaisceau) {
  return (
    <div
      aria-hidden="true"
      style={
        {
          "--taille": taille,
          "--duree": duree,
          "--epaisseur": epaisseur,
          "--retard": `-${retard}s`,
          "--depuis": depuis,
          "--vers": vers,
        } as CSSProperties
      }
      className={`faisceau ${className}`}
    />
  );
}
