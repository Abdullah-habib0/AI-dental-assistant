import Link from "next/link";

import { site } from "@/lib/site";
import { cn } from "@/lib/utils";

/** A simple mark: a rounded square with a smile. */
export function Logo({ className }: { className?: string }) {
  return (
    <Link href="/" className={cn("flex items-center gap-2.5 font-heading text-lg font-semibold", className)}>
      <svg viewBox="0 0 32 32" aria-hidden="true" className="size-8 shrink-0">
        <rect width="32" height="32" rx="9" className="fill-primary" />
        <path
          d="M9.5 14.5c1.2 4.2 3.7 6.3 6.5 6.3s5.3-2.1 6.5-6.3"
          className="stroke-primary-foreground"
          strokeWidth="2.6"
          strokeLinecap="round"
          fill="none"
        />
        <circle cx="11.5" cy="10.5" r="1.6" className="fill-primary-foreground" />
        <circle cx="20.5" cy="10.5" r="1.6" className="fill-primary-foreground" />
      </svg>
      <span>{site.name}</span>
    </Link>
  );
}
