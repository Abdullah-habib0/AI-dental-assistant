import Link from "next/link";
import { Suspense } from "react";
import { Accessibility, CalendarCheck, HeartHandshake, MessageCircle, ReceiptText, ShieldCheck } from "lucide-react";

import { OpenChatButton } from "@/components/chat/chat-context";
import { CardGridSkeleton, DentistCard, ServiceCard } from "@/components/site/cards";
import { buttonVariants } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { getClinicInfo, getDentists, getFaqs, getServices } from "@/lib/api";
import { hour, openDays, telHref } from "@/lib/format";
import { cn } from "@/lib/utils";

export default function HomePage() {
  return (
    <>
      <Hero />
      <Reasons />
      <Section
        eyebrow="Treatments"
        title="Everything from a check-up to a new tooth"
        link={{ href: "/services", label: "All treatments and prices" }}
      >
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          <Suspense fallback={<CardGridSkeleton count={6} />}>
            <Services />
          </Suspense>
        </div>
      </Section>
      <HowBookingWorks />
      <Section eyebrow="Our team" title="Three dentists, each with a speciality" link={{ href: "/dentists", label: "Meet the team" }}>
        <div className="grid gap-5 md:grid-cols-3">
          <Suspense fallback={<CardGridSkeleton count={3} />}>
            <Team />
          </Suspense>
        </div>
      </Section>
      <Section eyebrow="Questions" title="Things patients often ask" link={{ href: "/faq", label: "All questions" }}>
        <Suspense fallback={<CardGridSkeleton count={4} />}>
          <FaqPreview />
        </Suspense>
      </Section>
      <Suspense fallback={null}>
        <ContactBand />
      </Suspense>
    </>
  );
}

function Hero() {
  return (
    <section className="relative overflow-hidden border-b">
      <div
        aria-hidden="true"
        className="absolute inset-0 -z-10 bg-[radial-gradient(60rem_30rem_at_85%_-10%,var(--color-secondary),transparent_60%),radial-gradient(40rem_20rem_at_0%_110%,var(--color-sand),transparent_60%)]"
      />
      <div className="mx-auto grid max-w-6xl items-center gap-14 px-4 py-16 sm:px-6 lg:grid-cols-[1.1fr_0.9fr] lg:py-24">
        <div>
          <p className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-card/70 px-3 py-1 text-sm text-secondary-foreground">
            <span className="size-1.5 rounded-full bg-primary" /> Welcoming new patients of all ages
          </p>
          <h1 className="mt-6 text-5xl leading-[1.05] font-semibold sm:text-6xl">
            Dental care that fits <span className="text-primary italic">around your life</span>
          </h1>
          <p className="mt-6 max-w-xl text-lg leading-relaxed text-muted-foreground">
            Check-ups, fillings, whitening, root canal treatment and implants on the High Street - and an
            assistant that answers your questions and books you in, whenever suits you.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <OpenChatButton message="I'd like to book an appointment">Book with our assistant</OpenChatButton>
            <Link href="/services" className={cn(buttonVariants({ variant: "outline", size: "xl" }), "border-primary/30 bg-card/70")}>
              See treatments and prices
            </Link>
          </div>
          <Suspense fallback={<Skeleton className="mt-8 h-4 w-72" />}>
            <OpeningLine />
          </Suspense>
        </div>
        <ChatPreview />
      </div>
    </section>
  );
}

async function OpeningLine() {
  const clinic = await getClinicInfo();
  return (
    <p className="mt-8 flex items-center gap-2 text-sm text-muted-foreground">
      <CalendarCheck className="size-4 text-primary" />
      Open {openDays(clinic)}, {hour(clinic.opening_hour)}-{hour(clinic.closing_hour)} · the assistant takes bookings any time
    </p>
  );
}

/** An illustration of the chat - a fixed example, not a live conversation. */
function ChatPreview() {
  const lines = [
    { from: "patient", text: "Do you have any whitening appointments next week?" },
    { from: "assistant", text: "Yes - Dr Omar Haddad has Tuesday at 10:00 or 14:30. Would either suit you?" },
    { from: "patient", text: "14:30 please. I'm Priya Shah, 07700 900321." },
    { from: "assistant", text: "Teeth Whitening with Dr Omar Haddad, Tuesday at 14:30, for Priya Shah. Shall I book it?" },
  ];
  return (
    <div aria-hidden="true" className="relative mx-auto w-full max-w-md lg:mx-0">
      <div className="absolute -inset-4 -z-10 rounded-[2rem] bg-primary/5 blur-2xl" />
      <div className="rotate-1 rounded-3xl border bg-card p-5 shadow-2xl shadow-primary/10">
        <div className="flex items-center gap-2.5 border-b pb-4">
          <span className="flex size-8 items-center justify-center rounded-full bg-primary text-primary-foreground">
            <MessageCircle className="size-4" />
          </span>
          <div className="leading-tight">
            <p className="text-sm font-medium">Bright Smile assistant</p>
            <p className="text-xs text-muted-foreground">Checks real availability</p>
          </div>
        </div>
        <div className="space-y-3 pt-4 text-sm">
          {lines.map((line, i) => (
            <p
              key={i}
              className={cn(
                "w-fit max-w-[85%] rounded-2xl px-3.5 py-2.5 leading-relaxed",
                line.from === "patient"
                  ? "ml-auto rounded-tr-md bg-primary text-primary-foreground"
                  : "rounded-tl-md bg-secondary text-secondary-foreground",
              )}
            >
              {line.text}
            </p>
          ))}
        </div>
      </div>
    </div>
  );
}

function Reasons() {
  const reasons = [
    { icon: CalendarCheck, title: "Book any time", text: "The assistant checks the real diary and reads every booking back before confirming it." },
    { icon: ReceiptText, title: "Clear prices", text: "Every treatment's price is on the site, and anything beyond a check-up comes with a written plan first." },
    { icon: HeartHandshake, title: "Nervous patients welcome", text: "Longer appointments, a stop signal, and a dentist who explains each step first." },
    { icon: Accessibility, title: "Step-free access", text: "A ground-floor surgery and accessible toilet, five minutes' walk from the station." },
  ];
  return (
    <section className="border-b bg-card">
      <div className="mx-auto grid max-w-6xl gap-8 px-4 py-12 sm:grid-cols-2 sm:px-6 lg:grid-cols-4">
        {reasons.map(({ icon: Icon, title, text }) => (
          <div key={title}>
            <Icon className="size-6 text-primary" />
            <h2 className="mt-3 text-lg font-semibold">{title}</h2>
            <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">{text}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

function HowBookingWorks() {
  const steps = [
    { title: "Tell the assistant what you need", text: "A treatment, a dentist if you have a preference, and roughly when." },
    { title: "Pick from real free times", text: "It only ever offers times that are actually free in the diary." },
    { title: "Check the details, then confirm", text: "Nothing is booked until you've seen the summary and said yes." },
  ];
  return (
    <section className="mt-24 bg-primary text-primary-foreground">
      <div className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
        <p className="text-sm font-medium tracking-wide text-primary-foreground/70 uppercase">Booking</p>
        <h2 className="mt-3 max-w-2xl text-4xl font-semibold">Book in three steps, at any hour</h2>
        <ol className="mt-10 grid gap-8 md:grid-cols-3">
          {steps.map((step, i) => (
            <li key={step.title} className="border-t border-primary-foreground/20 pt-5">
              <span className="font-heading text-3xl text-primary-foreground/60">0{i + 1}</span>
              <h3 className="mt-2 text-xl font-semibold">{step.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-primary-foreground/80">{step.text}</p>
            </li>
          ))}
        </ol>
        <div className="mt-10 flex flex-wrap items-center gap-4">
          <OpenChatButton variant="secondary" message="I'd like to book an appointment">
            Start booking
          </OpenChatButton>
          <p className="flex items-center gap-2 text-sm text-primary-foreground/80">
            <ShieldCheck className="size-4" /> Urgent problem? Call us - urgent same-day appointments are given by phone.
          </p>
        </div>
      </div>
    </section>
  );
}

async function Services() {
  const services = await getServices();
  return services.map((service) => <ServiceCard key={service.slug} service={service} />);
}

async function Team() {
  const dentists = await getDentists();
  return dentists.map((dentist) => <DentistCard key={dentist.slug} dentist={dentist} />);
}

async function FaqPreview() {
  const faqs = (await getFaqs()).slice(0, 4);
  return (
    <dl className="grid gap-5 md:grid-cols-2">
      {faqs.map((faq) => (
        <div key={faq.question} className="rounded-2xl border bg-card p-6">
          <dt className="font-heading text-lg font-semibold">{faq.question}</dt>
          <dd className="mt-2 text-sm leading-relaxed text-muted-foreground">{faq.answer}</dd>
        </div>
      ))}
    </dl>
  );
}

async function ContactBand() {
  const clinic = await getClinicInfo();
  return (
    <section className="mx-auto mt-24 max-w-6xl px-4 sm:px-6">
      <div className="flex flex-col items-start justify-between gap-6 rounded-3xl bg-sand px-8 py-10 md:flex-row md:items-center">
        <div>
          <h2 className="text-3xl font-semibold">Still have a question?</h2>
          <p className="mt-2 text-muted-foreground">
            Ask the assistant, or call us on{" "}
            <a href={telHref(clinic.phone)} className="font-medium text-foreground underline-offset-4 hover:underline">
              {clinic.phone}
            </a>
            .
          </p>
        </div>
        <OpenChatButton>Ask the assistant</OpenChatButton>
      </div>
    </section>
  );
}

function Section({
  eyebrow,
  title,
  link,
  children,
}: {
  eyebrow: string;
  title: string;
  link: { href: string; label: string };
  children: React.ReactNode;
}) {
  return (
    <section className="mx-auto mt-24 max-w-6xl px-4 sm:px-6">
      <div className="mb-10 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <p className="text-sm font-medium tracking-wide text-primary uppercase">{eyebrow}</p>
          <h2 className="mt-3 max-w-xl text-4xl font-semibold">{title}</h2>
        </div>
        <Link href={link.href} className={cn(buttonVariants({ variant: "link" }), "px-0")}>
          {link.label} →
        </Link>
      </div>
      {children}
    </section>
  );
}
