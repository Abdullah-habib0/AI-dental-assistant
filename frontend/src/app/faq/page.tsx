import type { Metadata } from "next";
import { Suspense } from "react";

import { OpenChatButton } from "@/components/chat/chat-context";
import { PageHeader } from "@/components/site/page-header";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Skeleton } from "@/components/ui/skeleton";
import { getFaqs, type Faq } from "@/lib/api";

export const metadata: Metadata = {
  title: "Frequently asked questions",
  description: "Answers about appointments, payment, treatments and the practice.",
};

export default function FaqPage() {
  return (
    <>
      <PageHeader eyebrow="FAQ" title="Frequently asked questions">
        Can&apos;t find your question? The assistant can answer from all of the clinic&apos;s guides and policies.
      </PageHeader>
      <div className="mx-auto mt-12 max-w-3xl px-4 sm:px-6">
        <Suspense fallback={<FaqSkeleton />}>
          <Faqs />
        </Suspense>
        <div className="mt-14 flex flex-col items-start gap-4 rounded-2xl bg-secondary p-6 sm:flex-row sm:items-center sm:justify-between">
          <p className="font-heading text-xl font-semibold">Still wondering about something?</p>
          <OpenChatButton size="default">Ask the assistant</OpenChatButton>
        </div>
      </div>
    </>
  );
}

async function Faqs() {
  const faqs = await getFaqs();
  // Keep the categories in the order the clinic listed them.
  const groups = new Map<string, Faq[]>();
  for (const faq of faqs) groups.set(faq.category, [...(groups.get(faq.category) ?? []), faq]);

  return (
    <div className="space-y-12">
      {[...groups].map(([category, items]) => (
        <section key={category}>
          <h2 className="text-2xl font-semibold">{category}</h2>
          <Accordion className="mt-4 rounded-2xl border bg-card px-5">
            {items.map((faq) => (
              <AccordionItem key={faq.question} value={faq.question}>
                <AccordionTrigger className="py-4 text-base">{faq.question}</AccordionTrigger>
                <AccordionContent className="text-base leading-relaxed text-muted-foreground">
                  {faq.answer}
                </AccordionContent>
              </AccordionItem>
            ))}
          </Accordion>
        </section>
      ))}
    </div>
  );
}

function FaqSkeleton() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-7 w-40" />
      {Array.from({ length: 5 }, (_, i) => (
        <Skeleton key={i} className="h-12 w-full" />
      ))}
    </div>
  );
}
