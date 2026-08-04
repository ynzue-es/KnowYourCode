import type { ReactNode } from "react";

type ProprietesBlocCode = {
  /** L'intitulé de la barre du haut : un nom de fichier, « Terminal »… */
  intitule?: string;
  children: ReactNode;
};

/**
 * Un bloc de code encadré. Il défile horizontalement pour lui-même : sur un
 * téléphone, une ligne longue ne doit pas emporter la page avec elle.
 */
export function BlocCode({ intitule, children }: ProprietesBlocCode) {
  return (
    <div className="overflow-hidden rounded-xl border border-bordure bg-panneau-clair">
      {intitule ? (
        <div className="border-b border-bordure px-4 py-2 font-mono text-xs text-discret">
          {intitule}
        </div>
      ) : null}
      <pre className="overflow-x-auto px-4 py-4 font-mono text-[0.8rem] leading-relaxed text-encre sm:text-[0.85rem]">
        <code>{children}</code>
      </pre>
    </div>
  );
}

/** Une ligne de commande, précédée de son invite. */
export function Commande({ children }: { children: ReactNode }) {
  return (
    <>
      <span aria-hidden="true" className="mr-2 text-discret select-none">
        $
      </span>
      {children}
      {"\n"}
    </>
  );
}

/** Un commentaire de shell, en retrait de ton. */
export function Note({ children }: { children: ReactNode }) {
  return <span className="text-discret">{children}</span>;
}
