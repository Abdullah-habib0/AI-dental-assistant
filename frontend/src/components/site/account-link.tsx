import Link from "next/link";
import { UserRound } from "lucide-react";

import { hasSession } from "@/lib/session";
import { cn } from "@/lib/utils";

/**
 * "Log in" or "My appointments". Runs on the server, because only the server can see
 * the httpOnly login cookie - and it only checks the cookie is there, without a call to
 * the backend, so it's quick on every page.
 */
export async function AccountLink({ className }: { className?: string }) {
  const loggedIn = await hasSession();
  return (
    <Link href={loggedIn ? "/account" : "/login"} className={cn("inline-flex items-center gap-1.5", className)}>
      <UserRound className="size-4" />
      {loggedIn ? "My appointments" : "Log in"}
    </Link>
  );
}

/** Holds the space while the link streams in, so the header doesn't jump. */
export function AccountLinkPlaceholder({ className }: { className?: string }) {
  return <span aria-hidden="true" className={cn("inline-block w-32", className)} />;
}
