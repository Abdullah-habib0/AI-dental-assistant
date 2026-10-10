import type { Metadata } from "next";
import { Suspense } from "react";

import { CardGridSkeleton, DentistCard } from "@/components/site/cards";
import { PageHeader } from "@/components/site/page-header";
import { getDentists } from "@/lib/api";

export const metadata: Metadata = {
  title: "Our team",
  description: "Meet the dentists at Bright Smile Dental.",
};

export default function DentistsPage() {
  return (
    <>
      <PageHeader eyebrow="Our team" title="The people who'll look after you">
        Every dentist sees general patients, and each has an area they specialise in. Ask for anyone by name when
        you book, or take the first available appointment.
      </PageHeader>
      <div className="mx-auto mt-12 grid max-w-6xl gap-5 px-4 sm:px-6 md:grid-cols-3">
        <Suspense fallback={<CardGridSkeleton count={3} tall />}>
          <Team />
        </Suspense>
      </div>
    </>
  );
}

async function Team() {
  const dentists = await getDentists();
  return dentists.map((dentist) => <DentistCard key={dentist.slug} dentist={dentist} full />);
}
