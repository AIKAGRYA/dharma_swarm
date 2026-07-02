import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { PublicShell } from "@/components/livelihood-loom/public/PublicShell";
import { CandidateCard } from "@/components/livelihood-loom/public/CandidateCard";
import {
  loadLivelihoodLoomCandidates,
  loadLivelihoodLoomCandidateById,
} from "@/lib/livelihoodLoom";

export async function generateStaticParams(): Promise<{ company_id: string }[]> {
  const candidates = loadLivelihoodLoomCandidates();
  return candidates.map((candidate) => ({ company_id: candidate.company_id }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ company_id: string }>;
}): Promise<Metadata> {
  const { company_id } = await params;
  const candidate = loadLivelihoodLoomCandidateById(company_id);
  const title = candidate
    ? `${candidate.name} | Livelihood Loom Candidate`
    : "Candidate | Livelihood Loom";

  return {
    title,
    description:
      candidate?.description ??
      "Public-source informal-economy enablement candidate detail.",
    openGraph: {
      title,
      description:
        candidate?.description ??
        "Public-source informal-economy enablement candidate detail.",
      images: ["/livelihood-loom/hero-market-network.png"],
    },
  };
}

export default async function CandidateDetailPage({
  params,
}: {
  params: Promise<{ company_id: string }>;
}) {
  const { company_id } = await params;
  const candidate = loadLivelihoodLoomCandidateById(company_id);

  if (!candidate) {
    notFound();
  }

  return (
    <PublicShell>
      <section className="mx-auto max-w-7xl px-5 py-24 sm:px-8">
        <CandidateCard candidate={candidate} />
      </section>
    </PublicShell>
  );
}
