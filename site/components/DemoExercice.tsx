"use client";

import { useEffect, useState } from "react";

import { SegmentsColores } from "@/components/Code";
import { FaisceauBordure } from "@/components/FaisceauBordure";
import { useDansLeCadre, useMouvementSobre } from "@/lib/cadre";
import { colorer, type Segment } from "@/lib/coloration";

/* Le contenu est celui d'une vraie série : un extrait du projet, les cartes
   qu'un modèle en a tirées, et l'explication qui suit chaque réponse. Rien
   n'est inventé pour la démonstration — c'est ce que l'application affiche. */

const CHEMIN = "composants/ListeFiltrable.tsx";

/* Les lignes sont tenues sous quarante caractères. Le code ne se recompose
   pas : sur un téléphone, une ligne plus longue serait rognée sans recours. */
const SOURCE = `function ListeFiltrable({ elements }) {
  const [mot, setMot] = useState("");

  const visibles = useMemo(
    () => elements.filter(garder(mot)),
    [elements, mot],
  );

  useEffect(() => {
    const t = setTimeout(mesurer, 300);
    return () => clearTimeout(t);
  }, [visibles]);

  return <Liste items={visibles} />;
}`;

type Ligne = {
  segments: Segment[];
  /** Sa position dans la source entière, saut de ligne compris. */
  debut: number;
  taille: number;
};

/* Chaque ligne est colorée à part et gardée séparément : une carte « repérer »
   surligne une ligne, ce qu'un bloc d'un seul tenant ne permet pas. */
function decouper(source: string): Ligne[] {
  let debut = 0;
  return source.split("\n").map((texte) => {
    const ligne = { segments: colorer(texte), debut, taille: texte.length };
    debut += texte.length + 1;
    return ligne;
  });
}

const LIGNES = decouper(SOURCE);

type Commun = {
  /** La forme de la carte, telle qu'elle paraît au-dessus de la question. */
  forme: string;
  question: string;
  /** L'explication qui suit la réponse — juste ou fausse, elle vient
   *  toujours, et elle parle du code qu'on a sous les yeux. */
  pourquoi: string;
  juste: boolean;
  /** Indices de la bonne réponse et de celle qui est jouée : une option pour
   *  les unes, une ligne de l'extrait pour les autres. */
  bonne: number;
  jouee: number;
};

type Carte =
  | (Commun & { genre: "options"; options: string[] })
  | (Commun & { genre: "lignes" });

type CarteOptions = Extract<Carte, { genre: "options" }>;

const CARTES: Carte[] = [
  {
    genre: "options",
    forme: "QCM",
    question: "Au deuxième rendu, mot inchangé : que renvoie useMemo ?",
    options: [
      "Un tableau neuf",
      "Le tableau du premier rendu",
      "undefined",
      "Une promesse",
    ],
    bonne: 1,
    jouee: 1,
    juste: true,
    pourquoi:
      "useMemo garde le tableau tant que elements et mot n'ont pas bougé. " +
      "C'est ce qui épargne un rendu à Liste : la même référence, pas une " +
      "copie identique.",
  },
  {
    genre: "lignes",
    forme: "Repérer",
    question: "Quelle ligne empêche la minuterie de fuir ?",
    bonne: 10,
    jouee: 9,
    juste: false,
    pourquoi:
      "La ligne 10 pose la minuterie, la 11 la retire. Sans ce retour, " +
      "chaque changement de visibles en laisserait une derrière lui.",
  },
  {
    genre: "options",
    forme: "Vrai / faux",
    question: "L'effet se rejoue à chaque frappe dans le champ.",
    options: ["Vrai", "Faux"],
    bonne: 0,
    jouee: 0,
    juste: true,
    pourquoi:
      "mot change, donc useMemo recalcule, donc visibles est une nouvelle " +
      "référence, donc l'effet se rejoue. Les 300 ms sont là pour ça.",
  },
];

/** Les temps d'une carte : la question posée, la réponse choisie, le pourquoi
 *  à l'écran. La frappe du code n'a lieu qu'au premier tour de la série. */
type Temps = "code" | "enonce" | "choix" | "pourquoi";

/** Combien de caractères par battement, et à quelle cadence. Le code défile
 *  vite : on regarde du code apparaître, on ne le lit pas encore. */
const FRAPPE = { pas: 4, cadence: 16 };

/** Les temps morts, en millisecondes. Le dernier pourquoi tient plus
 *  longtemps : c'est celui qu'on lit avant que la série reparte. */
const PAUSES = {
  code: 550,
  enonce: 1000,
  choix: 500,
  pourquoi: 4200,
  derniere: 5600,
};

export function DemoExercice() {
  const [cadre, visible] = useDansLeCadre<HTMLDivElement>(0.25);
  const sobre = useMouvementSobre();
  const [temps, setTemps] = useState<Temps>("code");
  const [carte, setCarte] = useState(0);
  const [tapes, setTapes] = useState(0);

  /* Quand le système réclame moins de mouvement, la démonstration ne joue pas :
     elle s'affiche d'emblée à sa dernière carte, explication comprise. Il n'y
     a rien à comprendre dans la frappe elle-même — seulement dans ce qu'elle
     produit. L'état n'est pas touché, seul l'affichage l'est : rétablir la
     préférence rend la démonstration là où elle en était. */
  const tempsVu: Temps = sobre ? "pourquoi" : temps;
  const carteVue = sobre ? CARTES.length - 1 : carte;
  const tapesVus = sobre ? SOURCE.length : tapes;

  /* Un seul effet pilote la suite : chaque temps programme son successeur, et
     le nettoyage coupe le minuteur en cours dès que le temps change ou que le
     panneau sort du cadre. */
  useEffect(() => {
    if (!visible || sobre) return;

    if (temps === "code") {
      if (tapes < SOURCE.length) {
        const t = setTimeout(
          () => setTapes((n) => Math.min(n + FRAPPE.pas, SOURCE.length)),
          FRAPPE.cadence,
        );
        return () => clearTimeout(t);
      }
      const t = setTimeout(() => setTemps("enonce"), PAUSES.code);
      return () => clearTimeout(t);
    }

    if (temps === "enonce") {
      const t = setTimeout(() => setTemps("choix"), PAUSES.enonce);
      return () => clearTimeout(t);
    }

    if (temps === "choix") {
      const t = setTimeout(() => setTemps("pourquoi"), PAUSES.choix);
      return () => clearTimeout(t);
    }

    const derniere = carte === CARTES.length - 1;
    const t = setTimeout(
      () => {
        if (derniere) {
          setCarte(0);
          setTapes(0);
          setTemps("code");
        } else {
          setCarte((n) => n + 1);
          setTemps("enonce");
        }
      },
      derniere ? PAUSES.derniere : PAUSES.pourquoi,
    );
    return () => clearTimeout(t);
  }, [temps, carte, tapes, visible, sobre]);

  const enCours = CARTES[carteVue];

  /* La ligne où le curseur clignote : celle dans laquelle tombe le dernier
     caractère frappé. */
  const ligneFrappee = LIGNES.findIndex(
    (ligne) =>
      tapesVus >= ligne.debut && tapesVus <= ligne.debut + ligne.taille,
  );

  const teinteLigne = (index: number) => {
    if (enCours.genre !== "lignes" || tempsVu === "code") return "";
    /* Tant que rien n'est cliqué, les lignes s'éclairent au survol : c'est
       toute la consigne de cette forme de carte. */
    if (tempsVu === "enonce") return "hover:bg-panneau-clair/60";
    if (tempsVu === "choix") {
      return index === enCours.jouee ? "bg-accent/10" : "";
    }
    if (index === enCours.bonne) return "bg-menthe/15 text-encre";
    if (index === enCours.jouee) return "bg-ambre/15";
    return "";
  };

  return (
    <div
      ref={cadre}
      className="border-bordure-vive bg-panneau/80 relative overflow-hidden rounded-2xl border shadow-2xl shadow-black/60 backdrop-blur-xl"
    >
      {/* Le liseré clair du haut : la lumière tombe d'en haut, comme sur une
          fenêtre de macOS. */}
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/20 to-transparent" />

      {/* Deux faisceaux décalés d'un demi-tour : le cadre n'est jamais tout à
          fait éteint, sans pour autant clignoter. */}
      <FaisceauBordure duree={10} taille={340} epaisseur={2} />
      <FaisceauBordure
        duree={10}
        taille={340}
        epaisseur={2}
        retard={5}
        depuis="var(--color-menthe)"
        vers="var(--color-accent)"
      />

      {/* ------------------------------------------------ Barre de la fenêtre */}
      <div className="border-bordure flex items-center gap-2.5 border-b px-3 py-3 sm:gap-3 sm:px-4">
        <div aria-hidden="true" className="flex shrink-0 gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full bg-[#ff5f57]" />
          <span className="h-2.5 w-2.5 rounded-full bg-[#febc2e]" />
          <span className="h-2.5 w-2.5 rounded-full bg-[#28c840]" />
        </div>
        <p className="text-discret truncate font-mono text-xs">{CHEMIN}</p>
        <span className="border-bordure-vive text-attenue ml-auto shrink-0 rounded-md border px-2 py-0.5 font-mono text-[0.65rem]">
          TSX
        </span>
      </div>

      {/* ------------------------------------------------------------- Code */}
      <div className="text-encre relative flex px-3 py-4 font-mono text-[0.65rem] leading-[1.75] sm:px-4 sm:text-[0.8rem]">
        <div
          aria-hidden="true"
          className="text-discret/50 mr-3 shrink-0 text-right tabular-nums select-none sm:mr-4"
        >
          {LIGNES.map((_, index) => (
            <div key={index} className="min-h-[1.75em]">
              {index + 1}
            </div>
          ))}
        </div>

        {/* Chaque ligne réserve sa hauteur, vide ou frappée à moitié : la boîte
            garde la même taille du premier caractère à la dernière carte. */}
        <div className="min-w-0 flex-1 overflow-hidden">
          {LIGNES.map((ligne, index) => (
            <div
              key={index}
              className={`min-h-[1.75em] rounded-sm whitespace-pre transition-colors duration-500 ${teinteLigne(index)}`}
            >
              <SegmentsColores
                segments={ligne.segments}
                visibles={
                  tempsVu === "code"
                    ? Math.max(tapesVus - ligne.debut, 0)
                    : undefined
                }
              />
              {tempsVu === "code" && index === ligneFrappee ? (
                <span className="bg-accent anime-curseur ml-px inline-block h-[1em] w-[0.5em] translate-y-[0.15em]" />
              ) : null}
            </div>
          ))}
        </div>
      </div>

      {/* ----------------------------------------------------------- Carte */}
      <div className="border-bordure grid border-t px-3 pt-3 pb-4 sm:px-4">
        {/* Toutes les cartes sont aussi posées en double invisible, à leur état
            le plus haut : sans elles, la boîte grandirait d'une carte à
            l'autre et la page sauterait. */}
        {CARTES.map((autre, index) => (
          <div
            key={autre.forme}
            aria-hidden="true"
            className="invisible [grid-area:1/1]"
          >
            <CorpsCarte carte={autre} numero={index + 1} temps="pourquoi" />
          </div>
        ))}

        <div className="[grid-area:1/1]">
          {tempsVu === "code" ? (
            <>
              <p className="text-discret font-mono text-[0.65rem] tracking-[0.14em] uppercase">
                Série du jour · {CARTES.length} cartes
              </p>
              <p className="text-discret mt-1.5 text-[0.88rem] leading-snug">
                Une question arrive…
              </p>
              <Pourquoi />
            </>
          ) : (
            <CorpsCarte carte={enCours} numero={carteVue + 1} temps={tempsVu} />
          )}
        </div>
      </div>

      {/* -------------------------------------------------- Rail de la série */}
      <div className="border-bordure bg-fond/40 flex flex-wrap items-center gap-x-3 gap-y-1.5 border-t px-3 py-2.5 sm:gap-x-4 sm:px-4">
        {CARTES.map((autre, index) => {
          const atteinte = tempsVu !== "code" && index <= carteVue;
          return (
            <div key={autre.forme} className="flex items-center gap-2">
              <span
                aria-hidden="true"
                className={`h-1.5 w-1.5 rounded-full transition-colors duration-300 ${
                  atteinte ? "bg-accent" : "bg-bordure-vive"
                }`}
              />
              <span
                className={`font-mono text-[0.65rem] transition-colors duration-300 ${
                  index === carteVue && tempsVu !== "code"
                    ? "text-attenue"
                    : "text-discret/60"
                }`}
              >
                {autre.forme}
              </span>
            </div>
          );
        })}

        <span className="text-menthe/80 ml-auto shrink-0 font-mono text-[0.65rem]">
          Série · 12 jours
        </span>
      </div>
    </div>
  );
}

type ProprietesCorps = {
  carte: Carte;
  numero: number;
  temps: Exclude<Temps, "code">;
};

/** Le corps d'une carte : la question, ce qu'on peut répondre, et
 *  l'explication qui suit. */
function CorpsCarte({ carte, numero, temps }: ProprietesCorps) {
  return (
    <>
      <p className="text-discret font-mono text-[0.65rem] tracking-[0.14em] uppercase">
        {carte.forme} · {numero} sur {CARTES.length}
      </p>
      <p className="text-encre mt-1.5 text-[0.88rem] leading-snug">
        {carte.question}
      </p>

      {carte.genre === "options" ? (
        <ul className="mt-3 grid gap-1.5 sm:grid-cols-2">
          {carte.options.map((option, index) => (
            <li
              key={option}
              className={`rounded-lg border px-2.5 py-1.5 text-[0.78rem] transition-colors duration-300 ${teinteOption(carte, temps, index)}`}
            >
              {option}
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-discret mt-3 font-mono text-[0.68rem]">
          {temps === "enonce"
            ? "Cliquez la ligne dans le code."
            : `Ligne ${carte.jouee + 1}`}
        </p>
      )}

      <Pourquoi carte={temps === "pourquoi" ? carte : undefined} />
    </>
  );
}

/**
 * L'explication, et la case qu'elle occupe avant d'arriver.
 *
 * Elle est là dès la question posée : c'est la promesse de l'exercice, et une
 * case qui surgirait ferait sauter la boîte à chaque réponse.
 */
function Pourquoi({ carte }: { carte?: Carte }) {
  return (
    <div className="border-bordure bg-fond/60 mt-3 rounded-lg border px-3 py-2.5">
      <p
        className={`font-mono text-[0.65rem] tracking-[0.14em] uppercase transition-colors duration-300 ${
          !carte ? "text-discret" : carte.juste ? "text-menthe" : "text-ambre"
        }`}
      >
        {!carte ? "Pourquoi" : carte.juste ? "Juste" : "Presque"}
      </p>
      {carte ? (
        <p className="text-attenue anime-montee mt-2 text-[0.8rem] leading-relaxed">
          {carte.pourquoi}
        </p>
      ) : (
        <p className="text-discret mt-2 text-[0.8rem] leading-relaxed">
          Juste ou faux, l&apos;explication vient toujours.
        </p>
      )}
    </div>
  );
}

/** L'état d'une option : au repos, choisie, puis corrigée. La bonne réponse
 *  s'allume dans tous les cas — on ne laisse jamais quelqu'un repartir avec
 *  sa fausse idée. */
function teinteOption(
  carte: CarteOptions,
  temps: Exclude<Temps, "code">,
  index: number,
): string {
  const repos = "border-bordure-vive text-attenue";

  if (temps === "choix" && index === carte.jouee) {
    return "border-accent/50 bg-accent/10 text-encre";
  }

  if (temps === "pourquoi") {
    if (index === carte.bonne)
      return "border-menthe/50 bg-menthe/10 text-encre";
    if (index === carte.jouee) return "border-ambre/50 bg-ambre/10 text-encre";
  }

  return repos;
}
