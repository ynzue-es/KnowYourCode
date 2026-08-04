import type { ReactNode } from "react";

import { Code } from "@/components/Code";

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
    <div className="border-bordure bg-panneau-clair/70 relative overflow-hidden rounded-xl border backdrop-blur">
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/10 to-transparent" />

      {intitule ? (
        <div className="border-bordure text-discret flex items-center gap-2 border-b px-4 py-2 font-mono text-xs">
          <span aria-hidden="true" className="flex gap-1.5">
            <span className="h-2 w-2 rounded-full bg-[#ff5f57]/70" />
            <span className="h-2 w-2 rounded-full bg-[#febc2e]/70" />
            <span className="h-2 w-2 rounded-full bg-[#28c840]/70" />
          </span>
          {intitule}
        </div>
      ) : null}

      <pre className="text-encre overflow-x-auto px-4 py-4 font-mono text-[0.8rem] leading-relaxed sm:text-[0.85rem]">
        <code>{children}</code>
      </pre>
    </div>
  );
}

/** Une ligne de commande, précédée de son invite. */
export function Commande({ children }: { children: ReactNode }) {
  return (
    <>
      <span aria-hidden="true" className="text-menthe mr-2 select-none">
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

/** Un extrait coloré, dans un bloc du même cadre que les autres. */
export function BlocSource({
  intitule,
  source,
}: {
  intitule?: string;
  source: string;
}) {
  return (
    <BlocCode intitule={intitule}>
      <Code source={source} />
    </BlocCode>
  );
}
