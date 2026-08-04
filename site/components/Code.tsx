import { CLASSE_GENRE, colorer, type Segment } from "@/lib/coloration";

type ProprietesCode = {
  source: string;
  /** Nombre de caractères à peindre, pour une frappe progressive. `undefined`
   *  peint tout — c'est le cas de tous les blocs statiques. */
  visibles?: number;
  className?: string;
};

/**
 * Un extrait coloré. Le découpage est refait à chaque rendu : il coûte un
 * balayage d'une vingtaine de lignes, contre un `useMemo` et sa dépendance à
 * surveiller. Pour un extrait plus long, mémoriser le tableau de segments en
 * amont et passer par `SegmentsColores`.
 */
export function Code({ source, visibles, className = "" }: ProprietesCode) {
  return (
    <SegmentsColores
      segments={colorer(source)}
      visibles={visibles}
      className={className}
    />
  );
}

type ProprietesSegments = {
  segments: Segment[];
  visibles?: number;
  className?: string;
};

/** La même chose à partir de segments déjà découpés : c'est cette forme
 *  qu'emploie l'animation, qui recalculerait sinon la coloration à chaque
 *  caractère frappé. */
export function SegmentsColores({
  segments,
  visibles,
  className = "",
}: ProprietesSegments) {
  const limite = visibles ?? Number.POSITIVE_INFINITY;

  // La position de chaque segment dans l'extrait, calculée d'un coup : c'est
  // elle qui dit combien de caractères du segment tombent sous la limite.
  const debuts: number[] = [];
  let parcourus = 0;
  for (const segment of segments) {
    debuts.push(parcourus);
    parcourus += segment.texte.length;
  }

  return (
    <span className={className}>
      {segments.map((segment, index) => {
        const restant = limite - debuts[index];
        if (restant <= 0) return null;

        const texte =
          restant >= segment.texte.length
            ? segment.texte
            : segment.texte.slice(0, restant);

        const classe = CLASSE_GENRE[segment.genre];
        return classe ? (
          <span key={index} className={classe}>
            {texte}
          </span>
        ) : (
          <span key={index}>{texte}</span>
        );
      })}
    </span>
  );
}

/** Le nombre total de caractères d'un extrait découpé — la borne haute de la
 *  frappe. */
export function longueur(segments: Segment[]): number {
  return segments.reduce((total, segment) => total + segment.texte.length, 0);
}
