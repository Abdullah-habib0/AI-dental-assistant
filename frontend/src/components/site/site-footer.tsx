import Link from "next/link";

import { Logo } from "@/components/site/logo";
import { Skeleton } from "@/components/ui/skeleton";
import { getClinicInfo } from "@/lib/api";
import { hour, openDays, telHref } from "@/lib/format";
import { site } from "@/lib/site";

export async function SiteFooter() {
  const clinic = await getClinicInfo();
  return (
    <FooterFrame>
      <div className="space-y-1.5 text-sm">
        <p className="font-medium text-foreground">Visit us</p>
        <p>{clinic.address}</p>
        <p>
          <a href={telHref(clinic.phone)} className="hover:text-foreground">
            {clinic.phone}
          </a>
        </p>
        <p>
          <a href={`mailto:${clinic.email}`} className="hover:text-foreground">
            {clinic.email}
          </a>
        </p>
      </div>
      <div className="space-y-1.5 text-sm">
        <p className="font-medium text-foreground">Opening hours</p>
        <p>
          {openDays(clinic)}, {hour(clinic.opening_hour)} to {hour(clinic.closing_hour)}
        </p>
        <p>Closed at weekends and on bank holidays</p>
        <p className="pt-1">Out of hours: call NHS 111. Emergency: 999.</p>
      </div>
    </FooterFrame>
  );
}

export function SiteFooterSkeleton() {
  return (
    <FooterFrame>
      {[0, 1].map((i) => (
        <div key={i} className="space-y-2.5">
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-3.5 w-48" />
          <Skeleton className="h-3.5 w-36" />
          <Skeleton className="h-3.5 w-40" />
        </div>
      ))}
    </FooterFrame>
  );
}

function FooterFrame({ children }: { children: React.ReactNode }) {
  return (
    <footer className="mt-24 border-t bg-card text-muted-foreground">
      <div className="mx-auto grid max-w-6xl gap-10 px-4 py-12 sm:px-6 md:grid-cols-[1.4fr_1fr_1fr_0.8fr]">
        <div className="space-y-3">
          <Logo className="text-foreground" />
          <p className="max-w-xs text-sm">{site.tagline}.</p>
        </div>
        {children}
        <nav aria-label="Footer" className="flex flex-col gap-1.5 text-sm">
          <p className="font-medium text-foreground">Explore</p>
          {site.nav.map((item) => (
            <Link key={item.href} href={item.href} className="hover:text-foreground">
              {item.label}
            </Link>
          ))}
        </nav>
      </div>
      <div className="border-t">
        <p className="mx-auto max-w-6xl px-4 py-5 text-xs sm:px-6">
          {site.name} is a fictional practice, built as a software portfolio project. Nothing on this site is
          medical advice.
        </p>
      </div>
    </footer>
  );
}
