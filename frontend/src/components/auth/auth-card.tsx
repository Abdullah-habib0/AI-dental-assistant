import type { ReactNode } from "react";

/** The frame around the login and register forms. */
export function AuthCard({ title, intro, children }: { title: string; intro: string; children: ReactNode }) {
  return (
    <div className="relative">
      <div
        aria-hidden="true"
        className="absolute inset-x-0 top-0 -z-10 h-80 bg-[radial-gradient(40rem_18rem_at_50%_0%,var(--color-secondary),transparent_70%)]"
      />
      <div className="mx-auto max-w-md px-4 pt-16 sm:px-6">
        <h1 className="text-center text-4xl font-semibold">{title}</h1>
        <p className="mt-3 text-center text-muted-foreground">{intro}</p>
        <div className="mt-10 rounded-2xl border bg-card p-6 shadow-sm sm:p-8">{children}</div>
        <p className="mt-6 text-center text-xs leading-relaxed text-muted-foreground">
          You don&apos;t need an account to book - the assistant works for everyone. An account just keeps all your
          appointments in one place.
        </p>
      </div>
    </div>
  );
}
