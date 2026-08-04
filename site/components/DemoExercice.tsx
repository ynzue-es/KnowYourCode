"use client";

import { useEffect, useMemo, useState } from "react";

import { SegmentsColores, longueur } from "@/components/Code";
import { useDansLeCadre, useMouvementSobre } from "@/lib/cadre";
import { colorer } from "@/lib/coloration";

/* Le contenu est celui d'un vrai tour : une fonction du dépôt, une explication
   plausible, et l'évaluation qu'un modèle en rendrait. Rien n'est inventé pour
   la démonstration — c'est ce que l'application affiche. */

const CHEMIN = "connais_ton_code/selection.py";

const SOURCE = `def fonctions_du_fichier(chemin: Path) -> list[Fonction]:
    """Les fonctions d'un fichier Python, repérées avec ast."""
    try:
        arbre = ast.parse(chemin.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return []

    retenues = []
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, ast.FunctionDef):
            continue
        lignes = noeud.end_lineno - noeud.lineno + 1
        if MIN_LIGNES <= lignes <= MAX_LIGNES:
            retenues.append(Fonction(noeud.name, lignes))
    return retenues`;

const REPONSE =
  "Elle lit le fichier, le parse avec ast, parcourt l'arbre et garde les " +
  "définitions de fonctions dont la longueur tient entre les deux bornes. " +
  "Un fichier illisible renvoie une liste vide.";

const NOTE = 8;

const RESUME = "Le mécanisme est juste, la sélection aussi.";

const OUBLIS = [
  "L'encodage est forcé en UTF-8 à la lecture.",
  "UnicodeDecodeError est rattrapé au même titre qu'une erreur de syntaxe.",
  "ast.walk descend dans tout l'arbre : les fonctions imbriquées sont incluses.",
];

/** Les quatre temps du tour, dans l'ordre. */
const ACTES = [
  { cle: "code", intitule: "Sélection" },
  { cle: "reponse", intitule: "Explication" },
  { cle: "attente", intitule: "Évaluation" },
  { cle: "verdict", intitule: "Verdict" },
] as const;

type Acte = (typeof ACTES)[number]["cle"];

/** Combien de caractères par battement, et à quelle cadence. Le code défile
 *  vite — on regarde du code apparaître, on ne le lit pas encore ; la réponse
 *  est plus lente, parce qu'elle, on la lit. */
const FRAPPE = {
  code: { pas: 4, cadence: 16 },
  reponse: { pas: 2, cadence: 26 },
};

/** Les temps morts, en millisecondes : la pause après la frappe du code, celle
 *  après la réponse, la durée de l'attente, puis celle du verdict à l'écran. */
const PAUSES = { code: 650, reponse: 900, attente: 1200, verdict: 7000 };

export function DemoExercice() {
  const segmentsCode = useMemo(() => colorer(SOURCE), []);
  const tailleCode = useMemo(() => longueur(segmentsCode), [segmentsCode]);

  const [cadre, visible] = useDansLeCadre<HTMLDivElement>(0.25);
  const sobre = useMouvementSobre();
  const [acte, setActe] = useState<Acte>("code");
  const [tapesCode, setTapesCode] = useState(0);
  const [tapesReponse, setTapesReponse] = useState(0);

  /* Quand le système réclame moins de mouvement, la démonstration ne joue pas :
     elle s'affiche d'emblée à son dernier acte, verdict compris. Il n'y a rien
     à comprendre dans la frappe elle-même — seulement dans ce qu'elle produit.
     L'état n'est pas touché, seul l'affichage l'est : rétablir la préférence
     rend la démonstration à l'acte où elle en était. */
  const acteVu: Acte = sobre ? "verdict" : acte;
  const codeVu = sobre ? tailleCode : tapesCode;
  const reponseVue = sobre ? REPONSE.length : tapesReponse;

  /* Un seul effet pilote la suite : chaque acte programme son successeur, et
     le nettoyage coupe le minuteur en cours dès que l'acte change ou que le
     panneau sort du cadre. */
  useEffect(() => {
    if (!visible || sobre) return;

    if (acte === "code") {
      if (tapesCode >= tailleCode) {
        const t = setTimeout(() => setActe("reponse"), PAUSES.code);
        return () => clearTimeout(t);
      }
      const t = setTimeout(
        () => setTapesCode((n) => Math.min(n + FRAPPE.code.pas, tailleCode)),
        FRAPPE.code.cadence,
      );
      return () => clearTimeout(t);
    }

    if (acte === "reponse") {
      if (tapesReponse >= REPONSE.length) {
        const t = setTimeout(() => setActe("attente"), PAUSES.reponse);
        return () => clearTimeout(t);
      }
      const t = setTimeout(
        () =>
          setTapesReponse((n) =>
            Math.min(n + FRAPPE.reponse.pas, REPONSE.length),
          ),
        FRAPPE.reponse.cadence,
      );
      return () => clearTimeout(t);
    }

    if (acte === "attente") {
      const t = setTimeout(() => setActe("verdict"), PAUSES.attente);
      return () => clearTimeout(t);
    }

    const t = setTimeout(() => {
      setTapesCode(0);
      setTapesReponse(0);
      setActe("code");
    }, PAUSES.verdict);
    return () => clearTimeout(t);
  }, [acte, visible, sobre, tapesCode, tapesReponse, tailleCode]);

  const indiceActe = ACTES.findIndex((a) => a.cle === acteVu);
  const lignes = SOURCE.split("\n");

  return (
    <div
      ref={cadre}
      className="border-bordure-vive bg-panneau/80 relative overflow-hidden rounded-2xl border shadow-2xl shadow-black/60 backdrop-blur-xl"
    >
      {/* Le liseré clair du haut : la lumière tombe d'en haut, comme sur une
          fenêtre de macOS. */}
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/20 to-transparent" />

      {/* ------------------------------------------------ Barre de la fenêtre */}
      <div className="border-bordure flex items-center gap-3 border-b px-4 py-3">
        <div aria-hidden="true" className="flex shrink-0 gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full bg-[#ff5f57]" />
          <span className="h-2.5 w-2.5 rounded-full bg-[#febc2e]" />
          <span className="h-2.5 w-2.5 rounded-full bg-[#28c840]" />
        </div>
        <p className="text-discret truncate font-mono text-xs">{CHEMIN}</p>
        <span className="border-bordure-vive text-attenue ml-auto shrink-0 rounded-md border px-2 py-0.5 font-mono text-[0.65rem]">
          Python
        </span>
      </div>

      {/* ------------------------------------------------------------- Code */}
      <div className="relative flex px-4 py-4 font-mono text-[0.72rem] leading-[1.75] sm:text-[0.8rem]">
        <div
          aria-hidden="true"
          className="text-discret/50 mr-4 shrink-0 space-y-0 text-right tabular-nums select-none"
        >
          {lignes.map((_, index) => (
            <div key={index}>{index + 1}</div>
          ))}
        </div>

        {/* Le calque invisible réserve la place de l'extrait entier : sans lui,
            la boîte grandirait ligne à ligne et la page sauterait. */}
        <div className="relative min-w-0 flex-1">
          <pre aria-hidden="true" className="invisible overflow-hidden">
            <code>{SOURCE}</code>
          </pre>
          <pre className="text-encre absolute inset-0 overflow-hidden">
            <code>
              <SegmentsColores
                segments={segmentsCode}
                visibles={acteVu === "code" ? codeVu : undefined}
              />
              {acteVu === "code" ? (
                <span className="bg-accent anime-curseur ml-px inline-block h-[1em] w-[0.5em] translate-y-[0.15em]" />
              ) : null}
            </code>
          </pre>
        </div>
      </div>

      {/* -------------------------------------------------------- Explication */}
      <div className="border-bordure border-t px-4 pt-3 pb-4">
        <p className="text-discret mb-2 font-mono text-[0.65rem] tracking-[0.14em] uppercase">
          Votre explication
        </p>
        <div className="border-bordure bg-fond/60 relative rounded-lg border px-3 py-2.5">
          <p aria-hidden="true" className="invisible text-[0.82rem] leading-relaxed">
            {REPONSE}
          </p>
          <p className="text-attenue absolute inset-0 px-3 py-2.5 text-[0.82rem] leading-relaxed">
            {acteVu === "code" ? (
              <span className="text-discret">Expliquez ce que fait cette fonction…</span>
            ) : (
              <>
                {REPONSE.slice(0, acteVu === "reponse" ? reponseVue : undefined)}
                {acteVu === "reponse" ? (
                  <span className="bg-accent anime-curseur ml-px inline-block h-[1em] w-[2px] translate-y-[0.15em]" />
                ) : null}
              </>
            )}
          </p>
        </div>

        <div className="mt-3 flex items-center gap-3">
          <span
            className={`rounded-md px-2.5 py-1 font-mono text-[0.68rem] transition-colors duration-300 ${
              indiceActe >= 2
                ? "bg-accent/15 text-accent"
                : "border-bordure-vive text-discret border"
            }`}
          >
            ⌘ ⏎ Répondre
          </span>
          <span className="text-discret font-mono text-[0.68rem]">Passer</span>

          {acteVu === "attente" ? (
            <span className="text-attenue ml-auto flex items-center gap-2 font-mono text-[0.68rem]">
              <span className="border-accent/30 border-t-accent h-3 w-3 animate-spin rounded-full border-2" />
              Évaluation…
            </span>
          ) : null}
        </div>
      </div>

      {/* ----------------------------------------------------------- Verdict */}
      <div
        className={`grid transition-[grid-template-rows,opacity] duration-500 ease-[cubic-bezier(0.16,1,0.3,1)] ${
          acteVu === "verdict"
            ? "grid-rows-[1fr] opacity-100"
            : "grid-rows-[0fr] opacity-0"
        }`}
      >
        <div className="overflow-hidden">
          <div className="border-bordure bg-panneau-clair/60 border-t px-4 py-4">
            <div className="flex items-start gap-4">
              <Anneau note={NOTE} actif={acteVu === "verdict"} />
              <div className="min-w-0 flex-1">
                <p className="text-encre text-sm font-medium">{RESUME}</p>
                <p className="text-discret mt-1 font-mono text-[0.65rem] tracking-[0.14em] uppercase">
                  Ce que vous n&apos;avez pas dit
                </p>
                <ul className="mt-2 space-y-1.5">
                  {OUBLIS.map((oubli, index) => (
                    <li
                      key={oubli}
                      className="text-attenue flex gap-2.5 text-[0.8rem] leading-relaxed"
                      style={
                        acteVu === "verdict"
                          ? { animation: `montee 320ms cubic-bezier(0.16,1,0.3,1) ${180 + index * 110}ms both` }
                          : undefined
                      }
                    >
                      <span aria-hidden="true" className="text-ambre mt-px shrink-0">
                        ·
                      </span>
                      {oubli}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* --------------------------------------------------- Rail des actes */}
      <div className="border-bordure bg-fond/40 flex items-center gap-4 border-t px-4 py-2.5">
        {ACTES.map((etape, index) => (
          <div key={etape.cle} className="flex items-center gap-2">
            <span
              aria-hidden="true"
              className={`h-1.5 w-1.5 rounded-full transition-colors duration-300 ${
                index <= indiceActe ? "bg-accent" : "bg-bordure-vive"
              }`}
            />
            <span
              className={`font-mono text-[0.65rem] transition-colors duration-300 ${
                index === indiceActe ? "text-attenue" : "text-discret/60"
              }`}
            >
              {etape.intitule}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

/** La note sur dix, en anneau. Le trait se remplit quand le verdict paraît. */
function Anneau({ note, actif }: { note: number; actif: boolean }) {
  const rayon = 22;
  const tour = 2 * Math.PI * rayon;

  return (
    <div className="relative shrink-0" aria-label={`Note : ${note} sur 10`}>
      <svg viewBox="0 0 56 56" className="h-14 w-14 -rotate-90">
        <circle
          cx="28"
          cy="28"
          r={rayon}
          fill="none"
          strokeWidth="4"
          className="stroke-bordure-vive"
        />
        <circle
          cx="28"
          cy="28"
          r={rayon}
          fill="none"
          strokeWidth="4"
          strokeLinecap="round"
          className="stroke-menthe transition-[stroke-dashoffset] duration-1000 ease-[cubic-bezier(0.16,1,0.3,1)]"
          strokeDasharray={tour}
          strokeDashoffset={actif ? tour * (1 - note / 10) : tour}
        />
      </svg>
      <span className="text-encre absolute inset-0 flex items-center justify-center font-mono text-sm font-medium">
        {note}
      </span>
    </div>
  );
}
