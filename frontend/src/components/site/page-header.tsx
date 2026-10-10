import type { ReactNode } from "react";

/** The title block at the top of every inner page. */
export function PageHeader({ eyebrow, title, children }: { eyebrow: string; title: string; children?: ReactNode }) {
  return (
    <div className="border-b bg-gradient-to-b from-secondary/70 to-background">
      <div className="mx-auto max-w-6xl px-4 pt-16 pb-12 sm:px-6">
        <p className="text-sm font-medium tracking-wide text-primary uppercase">{eyebrow}</p>
        <h1 className="mt-3 max-w-3xl text-4xl font-semibold sm:text-5xl">{title}</h1>
        {children && <div className="mt-4 max-w-2xl text-lg leading-relaxed text-muted-foreground">{children}</div>}
      </div>
    </div>
  );
}
