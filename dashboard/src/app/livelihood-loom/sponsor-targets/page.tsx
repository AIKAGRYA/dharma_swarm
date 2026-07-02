import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { PublicShell } from "@/components/livelihood-loom/public/PublicShell";
import { SectionHeader } from "@/components/livelihood-loom/public/SectionHeader";
import { SponsorTargetCard } from "@/components/livelihood-loom/public/SponsorTargetCard";
import { loadLivelihoodLoomSponsorTarget } from "@/lib/livelihoodLoom";

export const metadata: Metadata = {
  title: "Sponsor Target | Livelihood Loom",
  description:
    "Draft sponsor target, fit thesis, safety basis, and selected wedge for human-governed review.",
  openGraph: {
    title: "Sponsor Target | Livelihood Loom",
    description:
      "Draft sponsor target, fit thesis, safety basis, and selected wedge for human-governed review.",
    images: ["/livelihood-loom/hero-market-network.png"],
  },
};

export default function SponsorTargetsPage() {
  const target = loadLivelihoodLoomSponsorTarget();

  if (!target) {
    notFound();
  }

  return (
    <PublicShell>
      <section className="mx-auto max-w-7xl px-5 py-24 sm:px-8">
        <SectionHeader
          eyebrow="Investor brief"
          title="Draft sponsor target"
          subtitle="A human-review-only target selected from public-source evidence. No outreach, publication, or fundraising claim is made here."
        />
        <div className="mt-12">
          <SponsorTargetCard target={target} />
        </div>
      </section>
    </PublicShell>
  );
}
