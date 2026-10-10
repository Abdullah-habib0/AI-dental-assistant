"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Suspense, useState } from "react";
import { Menu } from "lucide-react";

import { OpenChatButton } from "@/components/chat/chat-context";
import { Logo } from "@/components/site/logo";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { site } from "@/lib/site";
import { cn } from "@/lib/utils";

export function SiteHeader() {
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <header className="sticky top-0 z-30 border-b border-border/60 bg-background/85 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-6xl items-center gap-6 px-4 sm:px-6">
        <Logo />

        <nav aria-label="Main" className="ml-auto hidden items-center gap-1 md:flex">
          <NavLinks
            className="rounded-lg px-3 py-2 text-sm text-muted-foreground transition hover:text-foreground aria-[current=page]:font-medium aria-[current=page]:text-foreground"
          />
        </nav>
        <OpenChatButton size="default" className="hidden md:inline-flex">
          Book online
        </OpenChatButton>

        <Sheet open={menuOpen} onOpenChange={setMenuOpen}>
          <SheetTrigger render={<Button variant="ghost" size="icon" className="ml-auto md:hidden" />}>
            <Menu />
            <span className="sr-only">Open menu</span>
          </SheetTrigger>
          <SheetContent side="right" className="gap-0 p-6">
            <SheetTitle className="sr-only">Menu</SheetTitle>
            <Logo className="mb-8" />
            <nav aria-label="Main" className="flex flex-col">
              <NavLinks
                onNavigate={() => setMenuOpen(false)}
                className="border-b py-3.5 text-base aria-[current=page]:font-medium aria-[current=page]:text-primary"
              />
            </nav>
            <div className="mt-8" onClick={() => setMenuOpen(false)}>
              <OpenChatButton className="w-full">Book online</OpenChatButton>
            </div>
          </SheetContent>
        </Sheet>
      </div>
    </header>
  );
}

type NavLinksProps = { className: string; onNavigate?: () => void };

/**
 * The links, with the current page marked. Reading the current address only works once
 * someone actually visits, so the marked version streams in inside <Suspense>; until
 * then the same links show, just unmarked. Without this, pages like /services/[slug]
 * can't be partly built ahead of time.
 */
function NavLinks(props: NavLinksProps) {
  return (
    <Suspense fallback={<Links {...props} current={null} />}>
      <MarkedLinks {...props} />
    </Suspense>
  );
}

function MarkedLinks(props: NavLinksProps) {
  return <Links {...props} current={usePathname()} />;
}

function Links({ className, onNavigate, current }: NavLinksProps & { current: string | null }) {
  const isCurrent = (href: string) => current !== null && (current === href || current.startsWith(`${href}/`));
  return site.nav.map((item) => (
    <Link
      key={item.href}
      href={item.href}
      onClick={onNavigate}
      aria-current={isCurrent(item.href) ? "page" : undefined}
      className={cn(className)}
    >
      {item.label}
    </Link>
  ));
}
