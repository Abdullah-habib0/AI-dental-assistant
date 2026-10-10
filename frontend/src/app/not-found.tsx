import Link from "next/link";

import { buttonVariants } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="mx-auto max-w-xl px-4 py-24 text-center sm:px-6">
      <p className="text-sm font-medium tracking-wide text-primary uppercase">Page not found</p>
      <h1 className="mt-3 text-4xl font-semibold">We couldn&apos;t find that page</h1>
      <p className="mt-4 text-muted-foreground">It may have moved, or the link may be mistyped.</p>
      <Link href="/" className={buttonVariants({ size: "xl", className: "mt-8" })}>
        Back to the home page
      </Link>
    </div>
  );
}
