import type { ReactNode } from "react";

import { BlocCode, Commande, Note } from "@/components/BlocCode";
import { Logo } from "@/components/Logo";
import { Carte, Section } from "@/components/Section";
import {
  dateEnFrancais,
  dernierePublication,
  URL_DEPOT,
  URL_LICENCE,
  URL_PUBLICATIONS,
} from "@/lib/release";

/** La page est reconstruite toutes les cinq minutes, le temps de voir passer
 *  une nouvelle version sans redéployer. Next exige ici une valeur littérale :
 *  la même durée est nommée `DUREE_CACHE` dans `lib/release.ts`. */
export const revalidate = 300;

const LIEN_TELECHARGEMENT = "/api/telecharger";

const NAVIGATION = [
  { href: "#principe", intitule: "Le principe" },
  { href: "#rappel", intitule: "Le rappel" },
  { href: "#fonctionnement", intitule: "Fonctionnement" },
  { href: "#installation", intitule: "Installation" },
];

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
      <header className="border-bordure/70 bg-fond/85 sticky top-0 z-20 border-b backdrop-blur">
        <div className="mx-auto flex h-14 w-full max-w-4xl items-center justify-between gap-6 px-6">
          <a
            href="#haut"
            className="flex shrink-0 items-center gap-2.5 rounded-md"
          >
            <Logo taille={24} className="rounded-[7px]" />
            <span className="text-encre text-sm font-semibold tracking-tight">
              KnowYourCode
            </span>
          </a>

          <nav aria-label="Sections de la page" className="hidden md:block">
            <ul className="flex items-center gap-7 text-sm">
              {NAVIGATION.map((lien) => (
                <li key={lien.href}>
                  <a
                    href={lien.href}
                    className="text-attenue hover:text-encre rounded-md transition-colors"
                  >
                    {lien.intitule}
                  </a>
                </li>
              ))}
            </ul>
          </nav>

          <a
            href={LIEN_TELECHARGEMENT}
            className="bg-encre hover:bg-encre/90 shrink-0 rounded-full px-4 py-1.5 text-sm font-medium text-[#0b0c0e] transition-colors"
          >
            Télécharger
          </a>
        </div>
      </header>

      <main id="haut" className="flex-1">
        {/* --------------------------------------------------------- Hero */}
        <div className="px-6 pt-20 pb-20 sm:pt-28 sm:pb-28">
          <div className="mx-auto w-full max-w-4xl">
            <Logo taille={72} className="rounded-[20px]" />

            <h1 className="text-encre mt-8 text-4xl font-semibold tracking-tight sm:text-5xl">
              KnowYourCode
            </h1>

            <p className="text-attenue mt-4 max-w-2xl text-lg sm:text-xl">
              Clin d&apos;œil au KYC bancaire : connaître son code plutôt que
              son client.
            </p>

            <p className="text-attenue mt-6 max-w-2xl text-base leading-relaxed sm:text-lg">
              Un utilitaire de barre de menus pour macOS. Quand vous avez un
              moment, vous ouvrez son panneau : il tire au hasard une fonction
              du projet en cours et vous demande de l&apos;expliquer. Un modèle
              tiers compare votre explication au code et vous dit ce que vous
              avez oublié.
            </p>

            <div className="mt-10 flex flex-col gap-3 sm:flex-row sm:items-center sm:gap-4">
              <a
                href={LIEN_TELECHARGEMENT}
                className="bg-encre hover:bg-encre/90 inline-flex items-center justify-center gap-2.5 rounded-xl px-6 py-3.5 text-base font-medium text-[#0b0c0e] transition-colors"
              >
                <IconePomme />
                Télécharger pour macOS
              </a>

              <a
                href={URL_DEPOT}
                className="border-bordure-vive bg-panneau text-encre hover:border-discret inline-flex items-center justify-center gap-2.5 rounded-xl border px-6 py-3.5 text-base font-medium transition-colors"
              >
                <IconeGitHub />
                Voir sur GitHub
              </a>
            </div>

            <p className="text-discret mt-5 text-sm">{precisions}</p>

            {publieeLe ? (
              <p className="text-discret mt-1 text-sm">
                Publiée le {publieeLe} ·{" "}
                <a
                  href={publication?.urlPublication ?? URL_PUBLICATIONS}
                  className="hover:text-attenue underline underline-offset-4 transition-colors"
                >
                  notes de version
                </a>
              </p>
            ) : (
              <p className="text-discret mt-1 text-sm">
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
          </div>
        </div>

        {/* ----------------------------------------------------- Principe */}
        <Section
          id="principe"
          surtitre="Le principe"
          titre="Garder la maîtrise d'un code qu'on ne relit plus"
          chapeau={
            <>
              <p>
                Un projet grossit, on délègue une partie de son code, on relit
                le reste en diagonale. Quelques semaines plus tard, des pans
                entiers du dépôt ne sont plus que des noms de fichiers dont on
                devine la fonction.
              </p>
              <p>
                Le but n&apos;est pas de noter. C&apos;est de remettre une
                fonction sous les yeux, à froid, et de demander de
                l&apos;expliquer avec ses mots — en s&apos;entraînant au
                passage sur Python et TypeScript.
              </p>
            </>
          }
        >
          <figure className="border-bordure bg-panneau rounded-2xl border p-6 sm:p-8">
            <blockquote className="text-encre text-xl leading-snug font-medium sm:text-2xl">
              « Rien ne s&apos;ouvre tout seul, jamais. C&apos;est vous qui
              décidez du moment. »
            </blockquote>
            <figcaption className="text-attenue mt-4 text-[0.95rem] leading-relaxed">
              Pas de notification à l&apos;heure dite, pas de fenêtre qui
              surgit au milieu d&apos;une phrase. L&apos;icône attend dans la
              barre de menus. Vous cliquez quand vous avez deux minutes, et
              vous refermez quand vous n&apos;en avez plus.
            </figcaption>
          </figure>
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
              menus, en haut à droite, et attend.
            </p>
          }
        >
          <div className="grid gap-4 sm:grid-cols-2">
            <Carte titre="Le panneau">
              <p>
                Sous l&apos;icône, il ne contient que l&apos;exercice : le
                chemin du fichier, le nom de la fonction, le code coloré, une
                zone de saisie, le verdict. On y répond en trente secondes et
                on retourne travailler.
              </p>
              <p>
                Vous répondez avec Cmd+Entrée, ou vous passez.
                L&apos;évaluation part hors du fil de l&apos;interface : le
                panneau reste utilisable pendant l&apos;attente.
              </p>
            </Carte>

            <Carte titre="La grande fenêtre">
              <p>
                Au centre de l&apos;écran, une fenêtre ordinaire avec sa barre
                latérale, elle porte ce qu&apos;on consulte en s&apos;arrêtant :
                la progression et les réglages. Elle s&apos;ouvre par
                l&apos;icône en bas à gauche du panneau, et se ferme d&apos;un
                Esc.
              </p>
              <p>
                La progression montre le nombre de réponses, le score moyen et
                le score récent, la courbe des vingt derniers scores, ce qui
                revient le plus souvent dans les oublis, les fonctions les
                moins bien expliquées et la répartition par langage.
              </p>
            </Carte>
          </div>

          <p className="text-discret mt-6 text-sm leading-relaxed">
            La grande fenêtre ne touche pas au cycle de l&apos;exercice : on
            peut la consulter pendant qu&apos;une question attend sa réponse.
            Tant que rien n&apos;a été répondu, la progression dit simplement
            qu&apos;il n&apos;y a encore rien à montrer, plutôt que
            d&apos;afficher des zéros qui ne diraient rien.
          </p>
        </Section>

        {/* ------------------------------------------------------- Rappel */}
        <Section
          id="rappel"
          surtitre="Le rappel dans Claude Code"
          titre="Là où le regard se pose déjà"
          chapeau={
            <p>
              Une notification suppose une autorisation du système et disparaît
              en trois secondes. Le compteur d&apos;attente de Claude Code,
              lui, est déjà sous les yeux à chaque tour. C&apos;est là que le
              rappel se glisse.
            </p>
          }
        >
          <BlocCode intitule="Terminal">
            <span className="text-accent">✳</span>{" "}
            <span className="text-encre">
              {"<kyc>🧠 Révise pendant que je travaille</kyc>"}
            </span>
            <Note>… (12s · esc to interrupt)</Note>
          </BlocCode>

          <div className="text-attenue mt-6 space-y-4 text-[0.95rem] leading-relaxed">
            <p>
              L&apos;interrupteur des réglages, dans la grande fenêtre, écrit
              un bloc{" "}
              <Mono>spinnerVerbs</Mono> dans{" "}
              <Mono>~/.claude/settings.json</Mono>, avec une quinzaine de
              phrases. L&apos;éteindre retire le bloc et rend à Claude Code ses
              propres verbes. Dans les deux sens, le reste du fichier est
              conservé, et il faut redémarrer Claude Code pour voir le
              changement.
            </p>
            <p>
              Pour écrire les vôtres, posez un tableau JSON dans{" "}
              <Mono>~/.knowyourcode/phrases.json</Mono>. Elles s&apos;écrivent
              nues : la balise est ajoutée à la pose, et toute phrase dépassant
              soixante caractères une fois habillée est écartée — Claude Code
              la couperait au milieu d&apos;un mot.
            </p>
          </div>

          <div className="mt-5">
            <BlocCode intitule="~/.knowyourcode/phrases.json">
              {'["Relis avant de valider", "Tu saurais réécrire ça sans moi ?"]'}
            </BlocCode>
          </div>
        </Section>

        {/* ------------------------------------------------ Fonctionnement */}
        <Section
          id="fonctionnement"
          surtitre="Comment ça marche"
          titre="Du projet en cours au verdict"
          chapeau={
            <p>
              Quatre briques, chacune doublée d&apos;une version factice dont
              se sert la vérification automatique du dépôt.
            </p>
          }
        >
          <div className="grid gap-4 sm:grid-cols-2">
            <Carte titre="Le projet en cours">
              <p>
                Il se lit dans les transcripts JSONL de Claude Code, sous{" "}
                <Mono>~/.claude/projects/</Mono>. Le transcript modifié en
                dernier désigne la session la plus récente, et son champ{" "}
                <Mono>cwd</Mono> donne le dossier de travail.
              </p>
            </Carte>

            <Carte titre="La sélection">
              <p>
                Une fonction de 4 à 60 lignes, tirée au hasard dans ce projet.
                Les fonctions Python sont repérées avec <Mono>ast</Mono>, les
                fonctions TypeScript et TSX par un comptage d&apos;accolades
                qui saute les chaînes et les commentaires.
              </p>
              <p>
                Au hasard, et non « la plus récente » : le code qu&apos;on ne
                comprend plus n&apos;est pas toujours celui qu&apos;on vient
                d&apos;écrire.
              </p>
            </Carte>

            <Carte titre="L'évaluation">
              <p>
                Le code et votre explication partent chez{" "}
                <Mono>mistral-small-latest</Mono>, qui rend un verdict, une
                note et la liste de ce que vous n&apos;avez pas mentionné.
              </p>
              <p>
                Un modèle tiers plutôt que celui qui a écrit le code : on ne
                demande pas à quelqu&apos;un de corriger la copie qu&apos;il a
                dictée.
              </p>
            </Carte>

            <Carte titre="Les données locales">
              <p>
                Tout reste sur la machine, en clair, dans{" "}
                <Mono>~/.knowyourcode/</Mono>. L&apos;historique garde les
                questions posées, la réponse donnée, l&apos;évaluation et la
                date : de quoi ne pas reposer deux fois la même question, et
                mesurer la progression.
              </p>
              <p>
                Rien d&apos;autre ne quitte la machine que la fonction tirée et
                votre explication, le temps de l&apos;évaluation.
              </p>
            </Carte>
          </div>
        </Section>

        {/* -------------------------------------------------- Installation */}
        <Section
          id="installation"
          surtitre="Installation"
          titre="Quatre étapes, dont une facultative"
        >
          <ol className="space-y-8">
            <Etape numero={1} titre="Glisser dans Applications">
              <p>
                Ouvrez le DMG téléchargé et faites glisser{" "}
                <Mono>KnowYourCode</Mono> dans le dossier Applications.
              </p>
            </Etape>

            {/* À retirer le jour où l'application est notarisée. */}
            <Etape numero={2} titre="Autoriser la première ouverture">
              <p>
                Cette version n&apos;est pas notarisée par Apple. Au premier
                double-clic, macOS annoncera que l&apos;application est
                endommagée : elle ne l&apos;est pas, il lui manque un tampon.
              </p>
              <p className="mt-3">
                Fermez le message, puis ouvrez Réglages Système →{" "}
                <span className="text-encre">Confidentialité et sécurité</span>{" "}
                et descendez tout en bas : un bouton{" "}
                <span className="text-encre">« Ouvrir quand même »</span> vous
                attend. C&apos;est à faire une seule fois.
              </p>
            </Etape>

            <Etape numero={3} titre="Fournir une clé d'API Mistral">
              <p>
                L&apos;évaluation passe par l&apos;API Mistral. Deux façons de
                donner la clé, au choix.
              </p>
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
                La seconde ne dépend pas de l&apos;environnement du terminal :
                c&apos;est celle à préférer pour une application lancée depuis
                le Finder.
              </p>
            </Etape>

            <Etape numero={4} titre="Ouvrir l'application">
              <p>
                L&apos;icône se pose dans la barre de menus, en haut à droite.
                Rien n&apos;apparaît dans le Dock. Un clic ouvre le panneau, et
                vous réclamez une question quand vous le voulez.
              </p>
            </Etape>
          </ol>

          <div className="border-bordure bg-panneau text-attenue mt-10 rounded-2xl border p-6 text-[0.95rem] leading-relaxed">
            <p>
              <span className="text-encre font-medium">
                Sans clé, l&apos;application démarre quand même
              </span>{" "}
              et rend une évaluation factice : tout le reste fonctionne, il
              n&apos;y a que le verdict qui est faux. De quoi faire le tour de
              l&apos;interface avant de décider.
            </p>
            <p className="mt-3">
              L&apos;installation depuis les sources est décrite dans le{" "}
              <a
                href={URL_DEPOT}
                className="text-encre hover:text-accent underline underline-offset-4 transition-colors"
              >
                dépôt
              </a>{" "}
              : Python 3.10 ou plus récent, et une commande.
            </p>
          </div>
        </Section>

        {/* --------------------------------------------------- Fin de page */}
        <section
          aria-labelledby="fin-titre"
          className="border-bordure/70 border-t px-6 py-20 sm:py-24"
        >
          <div className="border-bordure bg-panneau mx-auto flex w-full max-w-4xl flex-col items-start gap-6 rounded-2xl border p-8 sm:flex-row sm:items-center sm:justify-between sm:p-10">
            <div>
              <h2
                id="fin-titre"
                className="text-encre text-xl font-semibold tracking-tight sm:text-2xl"
              >
                Prenez une question quand vous avez deux minutes.
              </h2>
              <p className="text-attenue mt-2 text-[0.95rem]">{precisions}</p>
            </div>
            <a
              href={LIEN_TELECHARGEMENT}
              className="bg-encre hover:bg-encre/90 inline-flex shrink-0 items-center justify-center gap-2.5 rounded-xl px-6 py-3.5 text-base font-medium text-[#0b0c0e] transition-colors"
            >
              <IconePomme />
              Télécharger pour macOS
            </a>
          </div>
        </section>
      </main>

      <footer className="border-bordure/70 border-t px-6 py-12">
        <div className="mx-auto flex w-full max-w-4xl flex-col gap-6 sm:flex-row sm:items-center sm:justify-between">
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
        className="border-bordure-vive bg-panneau text-attenue mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border font-mono text-sm"
      >
        {numero}
      </span>
      <div className="min-w-0 flex-1">
        <h3 className="text-encre text-base font-semibold">{titre}</h3>
        <div className="text-attenue mt-2 text-[0.95rem] leading-relaxed">
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
