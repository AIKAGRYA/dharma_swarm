import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { PublicShell } from "@/components/livelihood-loom/public/PublicShell";
import { WedgeDetailCard } from "@/components/livelihood-loom/public/WedgeDetailCard";
import {
  loadLivelihoodLoomWedges,
  loadLivelihoodLoomWedgeById,
} from "@/lib/livelihoodLoom";

export async function generateStaticParams(): Promise<{ wedge_id: string }[]> {
  const wedges = loadLivelihoodLoomWedges();
  return wedges.map((wedge) => ({ wedge_id: wedge.wedge_id }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ wedge_id: string }>;
}): Promise<Metadata> {
  const { wedge_id } = await params;
  const wedge = loadLivelihoodLoomWedgeById(wedge_id);
  const title = wedge
    ? `${wedge.label} | Livelihood Loom Market Map`
    : "Wedge | Livelihood Loom";

  return {
    title,
    description:
      wedge?.roi_thesis ??
      "Capital-grade market wedge detail for the informal economy.",
    openGraph: {
      title,
      description:
        wedge?.roi_thesis ??
        "Capital-grade market wedge detail for the informal economy.",
      images: ["/livelihood-loom/hero-market-network.png"],
    },
  };
}

export default async function WedgeDetailPage({
  params,
}: {
  params: Promise<{ wedge_id: string }>;
}) {
  const { wedge_id } = await params;
  const wedge = loadLivelihoodLoomWedgeById(wedge_id);

  if (!wedge) {
    notFound();
  }

  return (
    <PublicShell>
      <section className="mx-auto max-w-7xl px-5 py-24 sm:px-8">
        <WedgeDetailCard wedge={wedge} />
      </section>
    </PublicShell>
  );
}
