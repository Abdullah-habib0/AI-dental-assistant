import Link from "next/link";
import { ArrowRight, Clock } from "lucide-react";

import { OpenChatButton } from "@/components/chat/chat-context";
import { Skeleton } from "@/components/ui/skeleton";
import type { Dentist, Service } from "@/lib/api";
import { duration, initials, price } from "@/lib/format";

export function ServiceCard({ service }: { service: Service }) {
  return (
    <Link
      href={`/services/${service.slug}`}
      className="group flex flex-col rounded-2xl border bg-card p-6 transition hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-lg hover:shadow-primary/5"
    >
      <h3 className="text-xl font-semibold">{service.name}</h3>
      <p className="mt-2 flex-1 text-sm leading-relaxed text-muted-foreground">{service.summary}</p>
      <div className="mt-6 flex items-center justify-between border-t pt-4 text-sm">
        <span className="font-medium text-foreground">{price(service.price_cents)}</span>
        <span className="flex items-center gap-1.5 text-muted-foreground">
          <Clock className="size-3.5" />
          {duration(service.duration_minutes)}
        </span>
      </div>
      <span className="mt-4 flex items-center gap-1 text-sm font-medium text-primary">
        Learn more <ArrowRight className="size-3.5 transition group-hover:translate-x-0.5" />
      </span>
    </Link>
  );
}

export function DentistCard({ dentist, full = false }: { dentist: Dentist; full?: boolean }) {
  return (
    <article className="flex flex-col rounded-2xl border bg-card p-6">
      {/* Initials rather than stock photos: these are fictional dentists, and a photo of a
          real stranger would suggest otherwise. */}
      <div
        aria-hidden="true"
        className="flex size-16 items-center justify-center rounded-full bg-secondary font-heading text-xl font-semibold text-secondary-foreground"
      >
        {initials(dentist.name)}
      </div>
      <h3 className="mt-5 text-xl font-semibold">{dentist.name}</h3>
      <p className="text-sm text-muted-foreground">{dentist.qualifications}</p>
      <p className="mt-3 text-sm font-medium text-primary">{dentist.speciality}</p>
      {full && <p className="mt-3 flex-1 text-sm leading-relaxed text-muted-foreground">{dentist.bio}</p>}
      {full && (
        <OpenChatButton
          variant="outline"
          size="default"
          className="mt-6 self-start"
          message={`I'd like to book an appointment with ${dentist.name}`}
        >
          Book with Dr {dentist.name.split(" ").at(-1)}
        </OpenChatButton>
      )}
    </article>
  );
}

export function CardGridSkeleton({ count = 3, tall = false }: { count?: number; tall?: boolean }) {
  return (
    <>
      {Array.from({ length: count }, (_, i) => (
        <div key={i} className="rounded-2xl border bg-card p-6">
          <Skeleton className="h-6 w-2/3" />
          <Skeleton className="mt-4 h-4 w-full" />
          <Skeleton className="mt-2 h-4 w-5/6" />
          {tall && <Skeleton className="mt-2 h-4 w-4/6" />}
          <Skeleton className="mt-8 h-4 w-1/3" />
        </div>
      ))}
    </>
  );
}
