/**
 * Une coloration syntaxique minuscule, pour Python et TypeScript.
 *
 * Le site n'affiche qu'une poignée d'extraits écrits à la main : embarquer une
 * bibliothèque de coloration ferait entrer une grammaire complète et quelques
 * centaines de kilo-octets pour une vingtaine de lignes. Le découpage ci-
 * dessous ne comprend pas le code, il le reconnaît de loin — assez pour que
 * les mots-clés, les chaînes et les commentaires se détachent.
 *
 * Ce qu'il ne sait pas faire, et qu'il ne faut pas lui demander : les chaînes
 * à interpolation (le contenu de `${…}` reste peint en chaîne), les expressions
 * régulières littérales, et les mots-clés contextuels de TypeScript employés
 * comme identifiants.
 */

export type Genre =
  | "cle"
  | "chaine"
  | "note"
  | "nombre"
  | "appel"
  | "type"
  | "decorateur"
  | "signe"
  | "texte";

export type Segment = {
  texte: string;
  genre: Genre;
};

/** L'union des mots réservés des deux langages. Les confondre est sans
 *  conséquence : aucun extrait ne mélange les deux. */
const MOTS_CLES = new Set([
  // Python
  "def",
  "class",
  "return",
  "if",
  "elif",
  "else",
  "for",
  "while",
  "in",
  "not",
  "and",
  "or",
  "is",
  "None",
  "True",
  "False",
  "import",
  "from",
  "as",
  "with",
  "try",
  "except",
  "finally",
  "raise",
  "lambda",
  "yield",
  "pass",
  "break",
  "continue",
  "global",
  "nonlocal",
  "del",
  "assert",
  "async",
  "await",
  "self",
  // TypeScript
  "const",
  "let",
  "var",
  "function",
  "new",
  "export",
  "default",
  "type",
  "interface",
  "enum",
  "extends",
  "implements",
  "readonly",
  "private",
  "public",
  "protected",
  "static",
  "this",
  "null",
  "undefined",
  "true",
  "false",
  "void",
  "typeof",
  "instanceof",
  "switch",
  "case",
  "throw",
  "catch",
  "do",
  "satisfies",
  "keyof",
  "infer",
  "declare",
  "namespace",
]);

/**
 * Un seul balayage, une seule expression : commentaires, puis chaînes, puis
 * décorateurs, puis nombres, puis mots, puis ponctuation. L'ordre compte —
 * un `#` dans une chaîne ne doit pas ouvrir un commentaire, donc les chaînes
 * passent avant… sauf qu'un guillemet dans un commentaire ne doit pas ouvrir
 * une chaîne non plus. Les commentaires courent jusqu'au bout de la ligne et
 * sont donc placés en premier : c'est le cas le plus fréquent dans nos
 * extraits.
 */
const DECOUPE = new RegExp(
  [
    /#[^\n]*/.source,
    /\/\/[^\n]*/.source,
    /\/\*[\s\S]*?\*\//.source,
    /"""[\s\S]*?"""/.source,
    /'''[\s\S]*?'''/.source,
    /`(?:\\[\s\S]|[^`\\])*`/.source,
    /"(?:\\.|[^"\\\n])*"/.source,
    /'(?:\\.|[^'\\\n])*'/.source,
    /@[A-Za-z_][\w.]*/.source,
    /\b\d[\d_]*(?:\.\d+)?\b/.source,
    /[A-Za-z_$][\w$]*/.source,
    /[{}()[\].,:;=+\-*/%<>!&|?~^]+/.source,
  ].join("|"),
  "g",
);

/** Le genre d'un mot : mot-clé, appel, type, ou rien de particulier. */
function genreDuMot(mot: string, source: string, apres: number): Genre {
  if (MOTS_CLES.has(mot)) return "cle";

  // Un identifiant suivi d'une parenthèse est un appel — ou une définition,
  // ce qui se peint pareil.
  let i = apres;
  while (i < source.length && (source[i] === " " || source[i] === "\t")) i += 1;
  if (source[i] === "(") return "appel";

  // Faute de table des symboles, l'initiale majuscule tient lieu de type.
  if (/^[A-Z]/.test(mot)) return "type";

  return "texte";
}

/** Découpe un extrait en segments colorés. Le texte non reconnu ressort tel
 *  quel, en genre `texte` : la concaténation des segments redonne la source. */
export function colorer(source: string): Segment[] {
  const segments: Segment[] = [];
  let curseur = 0;

  const pousser = (texte: string, genre: Genre) => {
    if (!texte) return;
    // Deux segments de même genre qui se suivent forment un seul nœud : moins
    // de balises à poser, et le calcul de frappe s'en trouve allégé.
    const dernier = segments[segments.length - 1];
    if (dernier && dernier.genre === genre) dernier.texte += texte;
    else segments.push({ texte, genre });
  };

  for (const trouve of source.matchAll(DECOUPE)) {
    const texte = trouve[0];
    const debut = trouve.index;

    pousser(source.slice(curseur, debut), "texte");
    curseur = debut + texte.length;

    const tete = texte[0];
    if (tete === "#" || texte.startsWith("//") || texte.startsWith("/*")) {
      pousser(texte, "note");
    } else if (tete === '"' || tete === "'" || tete === "`") {
      pousser(texte, "chaine");
    } else if (tete === "@") {
      pousser(texte, "decorateur");
    } else if (tete >= "0" && tete <= "9") {
      pousser(texte, "nombre");
    } else if (/[A-Za-z_$]/.test(tete)) {
      pousser(texte, genreDuMot(texte, source, curseur));
    } else {
      pousser(texte, "signe");
    }
  }

  pousser(source.slice(curseur), "texte");
  return segments;
}

/** La classe Tailwind de chaque genre. `texte` n'en a pas : il hérite de la
 *  couleur du bloc, qui est déjà la bonne. */
export const CLASSE_GENRE: Record<Genre, string> = {
  cle: "text-[var(--color-syntaxe-cle)]",
  chaine: "text-[var(--color-syntaxe-chaine)]",
  note: "text-[var(--color-syntaxe-note)] italic",
  nombre: "text-[var(--color-syntaxe-nombre)]",
  appel: "text-[var(--color-syntaxe-appel)]",
  type: "text-[var(--color-syntaxe-type)]",
  decorateur: "text-ambre",
  signe: "text-[var(--color-syntaxe-signe)]",
  texte: "",
};
