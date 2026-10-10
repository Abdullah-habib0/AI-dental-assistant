import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { cache, Suspense } from "react";
import { ArrowLeft, Clock, PoundSterling } from "lucide-react";

import { OpenChatButton } from "@/components/chat/chat-context";
import { Skeleton } from "@/components/ui/skeleton";
import { getService, NotFoundError, type ServiceDetail } from "@/lib/api";
import { duration, price } from "@/lib/format";

export async function generateMetadata(props: PageProps<"/services/[slug]">): Promise<Metadata> {
  const { slug } = await props.params;
  const service = await findService(slug);
  return service ? { title: service.name, description: service.summary } : { title: "Treatment not found" };
}

// An unknown treatment shows the "not found" page, but with a 200 status, not 404: the
// root layout streams (the footer loads clinic details), and once a response starts
// streaming its status can't change. Next.js adds <meta name="robots" content="noindex">
// instead, which keeps the missing page out of search results.
export default function ServicePage(props: PageProps<"/services/[slug]">) {
  return (
    <Suspense fallback={<ServiceSkeleton />}>
      <Service params={props.params} />
    </Suspense>
  );
}

async function Service({ params }: { params: PageProps<"/services/[slug]">["params"] }) {
  const { slug } = await params;
  const service = await findService(slug);
  if (!service) notFound();

  return (
    <article>
      <div className="border-b bg-gradient-to-b from-secondary/70 to-background">
        <div className="mx-auto max-w-6xl px-4 pt-10 pb-12 sm:px-6">
          <Link href="/services" className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground">
            <ArrowLeft className="size-3.5" /> All treatments
          </Link>
          <h1 className="mt-6 max-w-3xl text-4xl font-semibold sm:text-5xl">{service.name}</h1>
          <p className="mt-4 max-w-2xl text-lg leading-relaxed text-muted-foreground">{service.summary}</p>
        </div>
      </div>

      <div className="mx-auto grid max-w-6xl gap-12 px-4 py-12 sm:px-6 lg:grid-cols-[1fr_340px]">
        <div className="max-w-2xl space-y-4 text-base leading-relaxed">
          <h2 className="text-2xl font-semibold">What to expect</h2>
          <p className="text-muted-foreground">{service.description}</p>
          <p className="text-muted-foreground">
            Have a question about this treatment, or about aftercare? Ask the assistant - it answers from the
            clinic&apos;s own treatment and aftercare guides.
          </p>
          <OpenChatButton
            variant="outline"
            size="default"
            message={`I have a question about ${service.name.toLowerCase()}`}
          >
            Ask about {service.name.toLowerCase()}
          </OpenChatButton>
        </div>

        <aside className="h-fit rounded-2xl border bg-card p-6 lg:sticky lg:top-24">
          <dl className="space-y-4">
            <div className="flex items-center justify-between">
              <dt className="flex items-center gap-2 text-sm text-muted-foreground">
                <PoundSterling className="size-4" /> Price
              </dt>
              <dd className="font-heading text-2xl font-semibold">{price(service.price_cents)}</dd>
            </div>
            <div className="flex items-center justify-between border-t pt-4">
              <dt className="flex items-center gap-2 text-sm text-muted-foreground">
                <Clock className="size-4" /> Appointment
              </dt>
              <dd className="font-medium">{duration(service.duration_minutes)}</dd>
            </div>
          </dl>
          <OpenChatButton className="mt-6 w-full" message={`I'd like to book ${service.name.toLowerCase()}`}>
            Book this treatment
          </OpenChatButton>
          <p className="mt-3 text-xs leading-relaxed text-muted-foreground">
            Free to cancel or move with 24 hours&apos; notice.
          </p>
        </aside>
      </div>
    </article>
  );
}

/**
 * The service, or null if there's no such slug. Other errors still go to the error page.
 *
 * Wrapped in React's cache() so the page title and the page body share one request to
 * the backend per visit, instead of each fetching it. (This lasts for one request only;
 * nothing is kept between visits - see lib/api.ts.)
 */
const findService = cache(async (slug: string): Promise<ServiceDetail | null> => {
  try {
    return await getService(slug);
  } catch (error) {
    if (error instanceof NotFoundError) return null;
    throw error;
  }
});

function ServiceSkeleton() {
  return (
    <div className="mx-auto max-w-6xl px-4 pt-10 sm:px-6">
      <Skeleton className="h-4 w-28" />
      <Skeleton className="mt-6 h-12 w-2/3" />
      <Skeleton className="mt-4 h-5 w-1/2" />
      <Skeleton className="mt-16 h-40 w-full max-w-2xl" />
    </div>
  );
}
