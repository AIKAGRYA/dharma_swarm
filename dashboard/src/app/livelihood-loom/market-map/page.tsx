import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { PublicShell } from "@/components/livelihood-loom/public/PublicShell";
import { SectionHeader } from "@/components/livelihood-loom/public/SectionHeader";
import { WedgeCard } from "@/components/livelihood-loom/public/WedgeCard";
import { StatCard } from "@/components/livelihood-loom/public/StatCard";
import { loadLivelihoodLoomWedges, loadLivelihoodLoomDashboard } from "@/lib/livelihoodLoom";

export const metadata: Metadata = {
  title: "Livelihood Loom | Market map",
  description:
    "Explore the ranked ROI wedges, candidate concentrations, and country coverage for public-source informal-economy enablement.",
  openGraph: {
    title: "Livelihood Loom | Market map",
    description:
      "Capital-grade maps for the informal economy, grounded in public-source evidence and human-governed action gates.",
    images: ["/livelihood-loom/hero-market-network.png"],
  },
};

export default function MarketMapPage() {
  const wedges = loadLivelihoodLoomWedges();
  const dashboard = loadLivelihoodLoomDashboard();

  const totalCountries = wedges.reduce((sum, wedge) => sum + (wedge.country_count ?? 0), 0);
  const totalTopCandidates = wedges.reduce(
    (sum, wedge) => sum + wedge.candidate_count_in_top_50,
    0,
  );

  return (
    <PublicShell>
      <div className="mx-auto max-w-7xl px-5 py-24 sm:px-8">
        <SectionHeader
          eyebrow="Market map"
          title="Ranked sponsor lanes by candidate signal"
          subtitle="Each wedge groups public-source candidates by capital relevance and welfare impact. Country counts and candidate concentrations are computed from the current local report."
          align="center"
          className="mx-auto max-w-3xl"
        />

        <div className="mt-12 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard label="Source rows" value={dashboard.candidateCount.toLocaleString()} detail="public-source enabler records" />
          <StatCard label="Prioritized" value={dashboard.topCount.toLocaleString()} detail="highest-signal candidates" />
          <StatCard label="Countries" value={totalCountries.toLocaleString()} detail="across all wedges" />
          <StatCard
            label="Top 50 coverage"
            value={totalTopCandidates.toLocaleString()}
            detail="candidates in mapped wedges"
          />
        </div>

        <div className="mt-12 grid gap-6 lg:grid-cols-3">
          {wedges.map((wedge) => (
            <WedgeCard key={wedge.wedge_id} wedge={wedge} />
          ))}
        </div>

        <div className="mt-12 rounded-lg border border-[#181a20]/10 bg-white p-6">
          <h3 className="font-heading text-lg font-semibold text-[#181a20]">Concentration notes</h3>
          <ul className="mt-4 list-disc space-y-2 pl-5 text-sm leading-6 text-[#4e5060]">
            <li>
              The map is derived from public-source records only; coverage reflects available data, not a claim of
              market completeness.
            </li>
            <li>
              Candidate counts within each wedge show concentration inside the Top 50, not the total addressable
              market.
            </li>
            <li>Country counts are unique countries represented by candidates in each wedge.</li>
          </ul>
        </div>

        <div className="mt-12 flex flex-wrap gap-3">
          <Link
            href="/livelihood-loom/proof-packet"
            className="inline-flex items-center gap-2 rounded-lg bg-[#181a20] px-4 py-3 text-sm font-semibold text-white transition hover:bg-[#2c303a]"
          >
            Review proof packet
            <ArrowRight size={16} />
          </Link>
          <Link
            href="/livelihood-loom/thesis"
            className="inline-flex items-center gap-2 rounded-lg border border-[#181a20]/15 px-4 py-3 text-sm font-semibold text-[#181a20] transition hover:bg-[#181a20]/5"
          >
            Read the thesis
            <ArrowRight size={16} />
          </Link>
        </div>
      </div>
    </PublicShell>
  );
}
