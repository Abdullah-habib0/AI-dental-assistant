"use client";

import { Button } from "@/components/ui/button";

/** Shown when a page can't load its data - usually because the backend isn't reachable. */
export default function ErrorPage({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <div className="mx-auto max-w-xl px-4 py-24 text-center sm:px-6">
      <p className="text-sm font-medium tracking-wide text-primary uppercase">Something went wrong</p>
      <h1 className="mt-3 text-4xl font-semibold">This page didn&apos;t load</h1>
      <p className="mt-4 text-muted-foreground">
        We couldn&apos;t reach the clinic&apos;s system just now. Please try again in a moment.
      </p>
      <Button size="xl" className="mt-8" onClick={reset}>
        Try again
      </Button>
    </div>
  );
}
