import type { Metadata } from "next";
import { Suspense } from "react";

import { CardGridSkeleton, ServiceCard } from "@/components/site/cards";
import { PageHeader } from "@/components/site/page-header";
import { getServices } from "@/lib/api";

export const metadata: Metadata = {
  title: "Treatments and prices",
  description: "Every treatment we offer, with its price and appointment length.",
};

export default function ServicesPage() {
  return (
    <>
      <PageHeader eyebrow="Treatments" title="Treatments and prices">
        Clear prices, set appointment lengths, and a written plan before anything beyond a check-up.
      </PageHeader>
      <div className="mx-auto mt-12 grid max-w-6xl gap-5 px-4 sm:grid-cols-2 sm:px-6 lg:grid-cols-3">
        <Suspense fallback={<CardGridSkeleton count={6} />}>
          <AllServices />
        </Suspense>
      </div>
    </>
  );
}

async function AllServices() {
  const services = await getServices();
  return services.map((service) => <ServiceCard key={service.slug} service={service} />);
}
