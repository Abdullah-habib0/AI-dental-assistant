import type { Metadata } from "next";
import { Suspense } from "react";
import { Accessibility, Clock, Mail, MapPin, Phone, TrainFront } from "lucide-react";

import { OpenChatButton } from "@/components/chat/chat-context";
import { PageHeader } from "@/components/site/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { getClinicInfo } from "@/lib/api";
import { hour, openDays, telHref } from "@/lib/format";

export const metadata: Metadata = {
  title: "Contact and opening hours",
  description: "How to reach Bright Smile Dental, when we're open, and how to find us.",
};

export default function ContactPage() {
  return (
    <>
      <PageHeader eyebrow="Contact" title="Get in touch">
        The quickest way to book, move or cancel is the assistant - any time of day. For anything urgent, please
        phone.
      </PageHeader>
      <div className="mx-auto mt-12 grid max-w-6xl gap-6 px-4 sm:px-6 lg:grid-cols-2">
        <Suspense fallback={<Skeleton className="h-80 rounded-2xl" />}>
          <Details />
        </Suspense>
        {/* No live map on purpose: the practice is fictional, and its address belongs to a
            real building that a map pin would point at. */}
        <div className="space-y-6 rounded-2xl border bg-card p-6">
          <Info icon={TrainFront} title="Getting here">
            About a five-minute walk from the station. There&apos;s paid street parking directly outside, and a
            public car park behind the library - allow extra time to find a space in the morning.
          </Info>
          <Info icon={Accessibility} title="Accessibility">
            Step-free access from the street, a ground-floor surgery and an accessible toilet. Assistance dogs are
            welcome. Mention any access needs when you book and we&apos;ll plan ahead.
          </Info>
        </div>
      </div>
      <div className="mx-auto mt-6 max-w-6xl px-4 sm:px-6">
        <div className="rounded-2xl border border-destructive/25 bg-destructive/5 p-6">
          <p className="font-heading text-lg font-semibold">Urgent or out of hours?</p>
          <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
            During opening hours, call us - urgent same-day appointments are given by phone. When we&apos;re closed,
            call <strong className="text-foreground">NHS 111</strong>. If swelling affects your breathing or
            swallowing, or bleeding won&apos;t stop, call <strong className="text-foreground">999</strong> or go to A&amp;E.
          </p>
        </div>
      </div>
    </>
  );
}

async function Details() {
  const clinic = await getClinicInfo();
  return (
    <div className="space-y-6 rounded-2xl border bg-card p-6">
      <Info icon={MapPin} title="Address">
        {clinic.address}
      </Info>
      <Info icon={Phone} title="Phone">
        <a href={telHref(clinic.phone)} className="font-medium text-foreground underline-offset-4 hover:underline">
          {clinic.phone}
        </a>
      </Info>
      <Info icon={Mail} title="Email">
        <a href={`mailto:${clinic.email}`} className="font-medium text-foreground underline-offset-4 hover:underline">
          {clinic.email}
        </a>{" "}
        - answered within one working day. Please don&apos;t email about anything urgent.
      </Info>
      <Info icon={Clock} title="Opening hours">
        {openDays(clinic)}, {hour(clinic.opening_hour)} to {hour(clinic.closing_hour)}. Closed at weekends and on
        bank holidays.
      </Info>
      <OpenChatButton size="default">Book or ask a question</OpenChatButton>
    </div>
  );
}

function Info({ icon: Icon, title, children }: { icon: React.ElementType; title: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-4">
      <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-secondary text-primary">
        <Icon className="size-5" />
      </span>
      <div>
        <h2 className="font-sans text-sm font-semibold tracking-normal">{title}</h2>
        <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{children}</p>
      </div>
    </div>
  );
}
