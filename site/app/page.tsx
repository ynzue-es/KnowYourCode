import type { ReactNode } from "react";

import { BlocCode, Commande } from "@/components/BlocCode";
import { Carte } from "@/components/Carte";
import { DemoExercice } from "@/components/DemoExercice";
import { DonneesStructurees } from "@/components/DonneesStructurees";
import { Entete } from "@/components/Entete";
import { FaisceauBordure } from "@/components/FaisceauBordure";
import { LigneSpinner } from "@/components/LigneSpinner";
import { Logo } from "@/components/Logo";
import { Revelation } from "@/components/Revelation";
import { Section } from "@/components/Section";
import {
  dateEnFrancais,
  dernierePublication,
  URL_DEPOT,
  URL_LICENCE,
  URL_PUBLICATIONS,
} from "@/lib/release";
import { URL_AUTEUR } from "@/lib/site";

/** La page est reconstruite toutes les cinq minutes, le temps de voir passer
 *  une nouvelle version sans redéployer. Next exige ici une valeur littérale :
 *  la même durée est nommée `DUREE_CACHE` dans `lib/release.ts`. */
export const revalidate = 300;

const LIEN_TELECHARGEMENT = "/api/telecharger";

export default async function Accueil() {
  const publication = await dernierePublication();
  const publieeLe = dateEnFrancais(publication?.publieeLe ?? null);

  const precisions = [
    publication?.version ? `Version ${publication.version}` : null,
    publication?.tailleMo ? `${publication.tailleMo} Mo` : null,
    "macOS 12 ou plus récent",
  ]
    .filter((precision): precision is string => precision !== null)
    .join(" · ");

  return (
    <>
      <DonneesStructurees publication={publication} />

      <Entete lienTelechargement={LIEN_TELECHARGEMENT} />

      <main id="haut" className="flex-1">
        {/* --------------------------------------------------------- Hero */}
        <div className="px-5 pt-14 pb-20 sm:px-6 sm:pt-24 sm:pb-32">
          <div className="mx-auto grid w-full max-w-5xl items-center gap-14 lg:grid-cols-[minmax(0,0.95fr)_minmax(0,1.05fr)] lg:gap-12">
            <Revelation>
              <span className="border-bordure-vive bg-panneau/60 text-attenue inline-flex items-center gap-2 rounded-full border px-3 py-1 font-mono text-xs backdrop-blur">
                <span
                  aria-hidden="true"
                  className="bg-menthe anime-pulsation h-1.5 w-1.5 rounded-full"
                />
                Barre de menus · macOS · Open source
              </span>

              <h1 className="text-encre mt-6 text-[1.8rem] leading-[1.15] font-semibold tracking-[-0.005em] text-balance sm:text-[2.5rem] sm:leading-[1.1]">
                On délègue le code.
                <span className="text-attenue block">
                  Pas la compréhension.
                </span>
              </h1>

              <p className="text-attenue mt-5 max-w-lg text-[0.92rem] leading-relaxed sm:text-base">
                Un utilitaire de barre de menus pour macOS. Trois questions
                rapides sur une fonction du projet en cours : vous répondez
                d&apos;un clic, il vous explique pourquoi ce code est écrit
                comme ça.
              </p>

              <div className="mt-9 flex flex-col gap-3 sm:flex-row sm:items-center sm:gap-4">
                <a
                  href={LIEN_TELECHARGEMENT}
                  className="bg-encre hover:bg-encre/90 inline-flex items-center justify-center gap-2.5 rounded-xl px-5 py-3 text-[0.92rem] font-medium text-[#0b0c0e] transition-all duration-200 hover:shadow-[0_0_36px_-8px] hover:shadow-white/40"
                >
                  <IconePomme />
                  Télécharger pour macOS
                </a>

                <a
                  href={URL_DEPOT}
                  className="border-bordure-vive bg-panneau/60 text-encre hover:border-discret hover:bg-panneau inline-flex items-center justify-center gap-2.5 rounded-xl border px-5 py-3 text-[0.92rem] font-medium backdrop-blur transition-colors"
                >
                  <IconeGitHub />
                  Voir sur GitHub
                </a>
              </div>

              <p className="text-discret mt-6 font-mono text-[0.7rem]">
                {precisions}
              </p>

              <p className="text-discret mt-1.5 font-mono text-[0.7rem]">
                Libre sous licence{" "}
                <a
                  href={URL_LICENCE}
                  className="hover:text-attenue underline underline-offset-4 transition-colors"
                >
                  MIT
                </a>
                , écrit par{" "}
                <a
                  href={URL_AUTEUR}
                  className="hover:text-attenue underline underline-offset-4 transition-colors"
                >
                  Yannis Nzue Essono
                </a>
              </p>

              {publieeLe ? (
                <p className="text-discret mt-1.5 font-mono text-[0.7rem]">
                  Publiée le {publieeLe} ·{" "}
                  <a
                    href={publication?.urlPublication ?? URL_PUBLICATIONS}
                    className="hover:text-attenue underline underline-offset-4 transition-colors"
                  >
                    notes de version
                  </a>
                </p>
              ) : (
                <p className="text-discret mt-1.5 font-mono text-xs">
                  Le lien mène toujours à la{" "}
                  <a
                    href={URL_PUBLICATIONS}
                    className="hover:text-attenue underline underline-offset-4 transition-colors"
                  >
                    dernière version publiée
                  </a>
                  .
                </p>
              )}
            </Revelation>

            <Revelation retard={160}>
              <DemoExercice />
            </Revelation>
          </div>
        </div>

        {/* ----------------------------------------------------- Principe */}
        <Section
          id="principe"
          surtitre="Le principe"
          titre="Vous répondez court. L'application explique long."
          chapeau={
            <>
              <p>
                Un projet grossit, on délègue une partie de son code, on relit
                le reste en diagonale. Quelques semaines plus tard, des pans
                entiers du dépôt ne sont plus que des noms de fichiers dont on
                devine la fonction.
              </p>
              <p>
                Trois ou quatre questions, un geste chacune. Puis un texte qui
                dit pourquoi ce code est écrit comme ça.
              </p>
            </>
          }
        >
          <figure className="border-bordure bg-panneau/60 relative overflow-hidden rounded-2xl border p-6 backdrop-blur-sm sm:p-10">
            <div
              aria-hidden="true"
              className="bg-accent/40 absolute inset-y-8 left-0 w-px"
            />
            <blockquote className="text-encre text-lg leading-snug font-medium text-balance sm:text-xl">
              « Le même “pourquoi” sur React, il y en a mille en ligne. Celui
              qui parle de votre <Mono>ListeFiltrable</Mono>, il n&apos;y en a
              qu&apos;un. »
            </blockquote>
            <figcaption className="text-attenue mt-3 max-w-2xl text-[0.88rem] leading-relaxed">
              L&apos;explication nomme vos variables, pas celles d&apos;un
              tutoriel. Juste ou faux, elle vient toujours.
            </figcaption>
          </figure>
        </Section>

        {/* ---------------------------------------------------- Les formes */}
        <Section
          id="questions"
          surtitre="Les questions"
          titre="Deux formes, un clic chacune"
          chapeau={
            <p>
              Rien à taper. La correction est locale : elle tombe à
              l&apos;instant du clic, sans rien attendre du réseau.
            </p>
          }
        >
          <ul className="grid gap-4 sm:grid-cols-2">
            <Forme nom="QCM">
              Que fait cette ligne ? Quatre options, dont trois qu&apos;on
              donnerait vraiment en lisant trop vite.
            </Forme>
            <Forme nom="Vrai / faux">
              Une idée fausse répandue, tranchée en deux secondes.
            </Forme>
          </ul>
        </Section>

        {/* ----------------------------------------------------- Surfaces */}
        <Section
          id="surfaces"
          surtitre="Les deux surfaces"
          titre="Un panneau pour répondre, une fenêtre pour prendre du recul"
          chapeau={
            <p>
              L&apos;application n&apos;apparaît pas dans le Dock, et rien ne
              s&apos;ouvre au lancement : elle pose son icône dans la barre de
              menus, en haut à droite, et attend. Rien ne s&apos;ouvre tout
              seul, jamais ; c&apos;est vous qui décidez du moment.
            </p>
          }
        >
          <div className="grid gap-4 sm:grid-cols-2">
            <Carte titre="Le panneau" marque="01">
              <p>
                Sous l&apos;icône, il ne contient que la série : le code, la
                question, l&apos;explication. Une minute, et on retourne
                travailler.
              </p>
            </Carte>

            <Carte titre="La grande fenêtre" marque="02">
              <p>
                Au centre de l&apos;écran, ce qu&apos;on consulte en
                s&apos;arrêtant : la progression et les réglages. Jours
                d&apos;affilée, réussite par forme de question, notions qui
                résistent, répartition par langage.
              </p>
            </Carte>
          </div>
        </Section>

        {/* ------------------------------------------------------- Rappel */}
        <Section
          id="rappel"
          surtitre="Le rappel dans Claude Code"
          titre="Là où le regard se pose déjà"
          chapeau={
            <p>
              Une notification suppose une autorisation du système et disparaît
              en trois secondes. Le compteur d&apos;attente de Claude Code, lui,
              est déjà sous les yeux à chaque tour. C&apos;est là que le rappel
              se glisse.
            </p>
          }
        >
          <LigneSpinner />

          <div className="text-attenue mt-8 grid gap-6 text-[0.88rem] leading-relaxed lg:grid-cols-2">
            <p>
              Un interrupteur dans les réglages écrit un bloc{" "}
              <Mono>spinnerVerbs</Mono> dans{" "}
              <Mono>~/.claude/settings.json</Mono>. L&apos;éteindre rend à
              Claude Code ses propres verbes.
            </p>
            <p>
              Pour écrire les vôtres, posez un tableau JSON dans{" "}
              <Mono>~/.knowyourcode/phrases.json</Mono> — sans la balise, elle
              est ajoutée à la pose.
            </p>
          </div>

          <div className="mt-6">
            <BlocCode intitule="~/.knowyourcode/phrases.json">
              <span className="text-[var(--color-syntaxe-signe)]">[</span>
              <span className="text-[var(--color-syntaxe-chaine)]">
                &quot;Relis avant de valider&quot;
              </span>
              <span className="text-[var(--color-syntaxe-signe)]">, </span>
              <span className="text-[var(--color-syntaxe-chaine)]">
                &quot;Tu saurais réécrire ça sans moi ?&quot;
              </span>
              <span className="text-[var(--color-syntaxe-signe)]">]</span>
            </BlocCode>
          </div>
        </Section>

        {/* ------------------------------------------------ Fonctionnement */}
        <Section
          id="fonctionnement"
          surtitre="Comment ça marche"
          titre="Du projet en cours aux questions"
        >
          <div className="grid gap-4 sm:grid-cols-2">
            <Carte titre="Le projet en cours" marque="01">
              <p>
                Il se lit dans les transcripts JSONL de Claude Code, sous{" "}
                <Mono>~/.claude/projects/</Mono>. Le transcript modifié en
                dernier désigne la session la plus récente, et son champ{" "}
                <Mono>cwd</Mono> donne le dossier de travail.
              </p>
            </Carte>

            <Carte titre="La sélection" marque="02">
              <p>
                Une fonction de 4 à 60 lignes, tirée au hasard — et non « la
                plus récente » : le code qu&apos;on ne comprend plus n&apos;est
                pas toujours celui qu&apos;on vient d&apos;écrire.
              </p>
            </Carte>

            <Carte titre="Les cartes" marque="03">
              <p>
                Le code part chez <Mono>mistral-small-latest</Mono>, qui en tire
                trois ou quatre questions, leurs réponses et leurs explications.
                Un modèle tiers plutôt que celui qui a écrit le code : on ne
                fait pas passer l&apos;interrogation à qui a dicté la copie.
              </p>
            </Carte>

            <Carte titre="La correction, sur place" marque="04">
              <p>
                Tout arrive avant la première question : pendant la série, plus
                rien n&apos;attend le réseau. Le reste vit en clair sur la
                machine, dans <Mono>~/.knowyourcode/</Mono>, et rien n&apos;en
                sort que la fonction tirée, le temps de fabriquer les cartes.
              </p>
            </Carte>
          </div>
        </Section>

        {/* -------------------------------------------------- Installation */}
        <Section
          id="installation"
          surtitre="Installation"
          titre="Trois étapes, dont une facultative"
        >
          <ol className="space-y-10">
            <Etape numero={1} titre="Glisser dans Applications">
              <p>
                Ouvrez le DMG téléchargé et faites glisser{" "}
                <Mono>KnowYourCode</Mono> dans le dossier Applications.
              </p>
            </Etape>

            <Etape numero={2} titre="Fournir une clé d'API Mistral">
              <p>Les cartes sont fabriquées par l&apos;API Mistral.</p>
              <div className="mt-4 grid gap-3 lg:grid-cols-2">
                <BlocCode intitule="Variable d'environnement">
                  <Commande>
                    export MISTRAL_API_KEY=&quot;votre-clé&quot;
                  </Commande>
                </BlocCode>
                <BlocCode intitule="Fichier dédié">
                  <Commande>mkdir -p ~/.knowyourcode</Commande>
                  <Commande>
                    echo &quot;votre-clé&quot; &gt; ~/.knowyourcode/cle_mistral
                  </Commande>
                  <Commande>chmod 600 ~/.knowyourcode/cle_mistral</Commande>
                </BlocCode>
              </div>
              <p className="mt-4">
                La seconde ne dépend pas du terminal : c&apos;est celle à
                préférer pour une application lancée depuis le Finder.
              </p>
            </Etape>

            <Etape numero={3} titre="Ouvrir l'application">
              <p>
                L&apos;icône se pose dans la barre de menus, en haut à droite.
                Rien n&apos;apparaît dans le Dock. Un clic ouvre le panneau, et
                vous réclamez une série quand vous le voulez.
              </p>
            </Etape>
          </ol>

          <div className="border-bordure bg-panneau/60 text-attenue mt-12 rounded-2xl border p-6 text-[0.88rem] leading-relaxed backdrop-blur-sm sm:p-8">
            <p>
              <span className="text-encre font-medium">
                Sans clé, l&apos;application démarre quand même
              </span>{" "}
              et pose des cartes factices : tout le reste fonctionne, il
              n&apos;y a que les questions qui sont creuses. De quoi faire le
              tour de l&apos;interface avant de décider.
            </p>
            <p className="mt-3">
              L&apos;installation depuis les sources est décrite dans le{" "}
              <a
                href={URL_DEPOT}
                className="text-encre hover:text-accent underline underline-offset-4 transition-colors"
              >
                dépôt
              </a>
              .
            </p>
          </div>
        </Section>

        {/* --------------------------------------------------- Fin de page */}
        <section
          aria-labelledby="fin-titre"
          className="border-bordure/60 border-t px-5 py-20 sm:px-6 sm:py-28"
        >
          <Revelation className="mx-auto w-full max-w-5xl">
            <div className="border-bordure-vive bg-panneau/70 relative flex flex-col items-start gap-6 overflow-hidden rounded-3xl border p-6 backdrop-blur-sm sm:flex-row sm:items-center sm:justify-between sm:p-12">
              <div
                aria-hidden="true"
                className="halo bg-accent absolute -top-24 -left-16 h-56 w-56 rounded-full opacity-20"
              />
              <FaisceauBordure duree={14} taille={420} epaisseur={2} />
              <div className="relative">
                <h2
                  id="fin-titre"
                  className="text-encre text-lg font-semibold text-balance sm:text-2xl"
                >
                  Trois questions quand vous avez une minute.
                </h2>
                <p className="text-attenue mt-2 font-mono text-[0.7rem] sm:text-xs">
                  {precisions}
                </p>
              </div>
              <a
                href={LIEN_TELECHARGEMENT}
                className="bg-encre hover:bg-encre/90 relative inline-flex shrink-0 items-center justify-center gap-2.5 rounded-xl px-5 py-3 text-[0.92rem] font-medium text-[#0b0c0e] transition-all duration-200 hover:shadow-[0_0_36px_-8px] hover:shadow-white/40"
              >
                <IconePomme />
                Télécharger pour macOS
              </a>
            </div>
          </Revelation>
        </section>
      </main>

      <footer className="border-bordure/60 border-t px-5 py-12 sm:px-6">
        <div className="mx-auto flex w-full max-w-5xl flex-col gap-6 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <Logo taille={28} className="rounded-[8px]" />
            <div>
              <p className="text-encre text-sm font-medium">KnowYourCode</p>
              <p className="text-discret text-sm">
                Yannis Nzue Essono · licence{" "}
                <a
                  href={URL_LICENCE}
                  className="hover:text-attenue underline underline-offset-4 transition-colors"
                >
                  MIT
                </a>
              </p>
            </div>
          </div>

          <nav aria-label="Liens du pied de page">
            <ul className="text-attenue flex flex-wrap items-center gap-x-6 gap-y-2 text-sm">
              <li>
                <a
                  href={URL_DEPOT}
                  className="hover:text-encre inline-flex items-center gap-2 transition-colors"
                >
                  <IconeGitHub />
                  Dépôt
                </a>
              </li>
              <li>
                <a
                  href={URL_PUBLICATIONS}
                  className="hover:text-encre transition-colors"
                >
                  Versions
                </a>
              </li>
              <li>
                <a
                  href={LIEN_TELECHARGEMENT}
                  className="hover:text-encre transition-colors"
                >
                  Télécharger
                </a>
              </li>
            </ul>
          </nav>
        </div>
      </footer>
    </>
  );
}

/** Un chemin, un nom de clé ou de module, dans le fil du texte. */
function Mono({ children }: { children: ReactNode }) {
  return (
    <code className="bg-panneau-clair border-bordure text-encre rounded-md border px-1.5 py-0.5 font-mono text-[0.85em] whitespace-nowrap">
      {children}
    </code>
  );
}

/** Une forme de question : son nom, et ce qu'elle demande. */
function Forme({ nom, children }: { nom: string; children: ReactNode }) {
  return (
    <li className="border-bordure bg-panneau/60 rounded-xl border px-4 py-3">
      <p className="text-accent/80 font-mono text-[0.68rem] tracking-[0.14em] uppercase">
        {nom}
      </p>
      <p className="text-attenue mt-1 text-[0.88rem] leading-relaxed">
        {children}
      </p>
    </li>
  );
}

type ProprietesEtape = {
  numero: number;
  titre: string;
  children: ReactNode;
};

function Etape({ numero, titre, children }: ProprietesEtape) {
  return (
    <li className="flex gap-5">
      <span
        aria-hidden="true"
        className="border-bordure-vive bg-panneau text-accent mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full border font-mono text-sm"
      >
        {numero}
      </span>
      <div className="min-w-0 flex-1">
        <h3 className="text-encre text-[0.95rem] font-semibold">{titre}</h3>
        <div className="text-attenue mt-2 max-w-3xl text-[0.88rem] leading-relaxed">
          {children}
        </div>
      </div>
    </li>
  );
}

function IconePomme() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 384 512"
      className="h-[1.15em] w-[1.15em] fill-current"
    >
      <path d="M318.7 268.7c-.2-36.7 16.4-64.4 50-84.8-18.8-26.9-47.2-41.7-84.7-44.6-35.5-2.8-74.3 20.7-88.5 20.7-15 0-49.4-19.7-76.4-19.7C63.3 141.2 4 184.8 4 273.5q0 39.3 14.4 81.2c12.8 36.7 59 126.7 107.2 125.2 25.2-.6 43-17.9 75.8-17.9 31.8 0 48.3 17.9 76.4 17.9 48.6-.7 90.4-82.5 102.6-119.3-65.2-30.7-61.7-90-61.7-91.9zm-56.6-164.2c27.3-32.4 24.8-61.9 24-72.5-24.1 1.4-52 16.4-67.9 34.9-17.5 19.8-27.8 44.3-25.6 71.9 26.1 2 49.9-11.4 69.5-34.3z" />
    </svg>
  );
}

function IconeGitHub() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 16 16"
      className="h-[1.1em] w-[1.1em] fill-current"
    >
      <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27s1.36.09 2 .27c1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8z" />
    </svg>
  );
}
