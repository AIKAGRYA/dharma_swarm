import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { PublicShell } from "@/components/livelihood-loom/public/PublicShell";
import { SectionHeader } from "@/components/livelihood-loom/public/SectionHeader";
import { PacketCard } from "@/components/livelihood-loom/public/PacketCard";
import { SafetyBar } from "@/components/livelihood-loom/public/SafetyBar";
import { ProofLink } from "@/components/livelihood-loom/public/ProofLink";
import { loadLivelihoodLoomPackets, loadLivelihoodLoomDashboard } from "@/lib/livelihoodLoom";

export const metadata: Metadata = {
  title: "Livelihood Loom | Proof packet",
  description:
    "Methodology, safety review summary, and enablement packets for public-source informal-economy partner diligence.",
  openGraph: {
    title: "Livelihood Loom | Proof packet",
    description:
      "Capital-grade maps for the informal economy, grounded in public-source evidence and human-governed action gates.",
    images: ["/livelihood-loom/hero-market-network.png"],
  },
};

export default function ProofPacketPage() {
  const packets = loadLivelihoodLoomPackets();
  const dashboard = loadLivelihoodLoomDashboard();
  const safety = dashboard.safety;

  return (
    <PublicShell>
      <div className="mx-auto max-w-7xl px-5 py-24 sm:px-8">
        <SectionHeader
          eyebrow="Proof packet"
          title="Methodology, safety review, and enablement packets"
          subtitle="The current packet is built from local reports. Each candidate was ranked from public-source data, grouped into wedges, and red-teamed for safety before being packaged for sponsor review."
          align="center"
          className="mx-auto max-w-3xl"
        />

        <section className="mt-12 grid gap-6 lg:grid-cols-[1fr_0.85fr]">
          <div className="rounded-lg border border-[#181a20]/10 bg-white p-6 sm:p-8">
            <h2 className="font-heading text-2xl font-semibold text-[#181a20]">Methodology</h2>
            <ol className="mt-5 list-decimal space-y-3 pl-5 text-sm leading-7 text-[#4e5060]">
              <li>
                <strong>Source aggregation:</strong> Collect public enabler records describing livelihood
                infrastructure across payment, logistics, demand, and finance.
              </li>
              <li>
                <strong>Scoring:</strong> Rank candidates by capital relevance, welfare impact, and evidence
                strength using transparent score components.
              </li>
              <li>
                <strong>Wedge formation:</strong> Group the Top 50 into ROI wedges by shared sponsor value
                and market function.
              </li>
              <li>
                <strong>Safety review:</strong> Flag exploitation, compliance, and reputational risks to
                produce allowed / needs review / blocked statuses.
              </li>
              <li>
                <strong>Packet packaging:</strong> Build sponsor-ready enablement briefs with candidate
                partners, welfare metrics, and next safe actions.
              </li>
            </ol>
            <div className="mt-8 flex flex-wrap gap-3">
              <ProofLink href="/api/livelihood-loom" label="View JSON proof" variant="api" />
              <ProofLink href="/dashboard/livelihood-loom" label="Internal desk" variant="desk" />
            </div>
          </div>

          <div className="rounded-lg border border-[#181a20]/10 bg-white p-6 sm:p-8">
            <h2 className="font-heading text-2xl font-semibold text-[#181a20]">Safety summary</h2>
            <p className="mt-3 text-sm leading-6 text-[#4e5060]">
              Safety statuses are assigned from a structured review of public-source signals. Blocked candidates remain
              visible by design so sponsors can see the full diligence posture.
            </p>
            <div className="mt-6">
              <SafetyBar
                allowed={safety.allowed}
                needs_review={safety.needs_review}
                blocked={safety.blocked}
                total={safety.total}
              />
            </div>
            <div className="mt-6">
              <h3 className="text-sm font-semibold text-[#181a20]">Policy flag counts</h3>
              <ul className="mt-3 grid gap-2 sm:grid-cols-2">
                {Object.entries(safety.flag_counts).map(([flag, count]) => (
                  <li
                    key={flag}
                    className="flex items-center justify-between rounded-md bg-[#f9f7f1] px-3 py-2 text-sm"
                  >
                    <span className="text-[#5d5f68]">{flag}</span>
                    <span className="font-mono font-semibold text-[#181a20]">{count}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </section>

        <section className="mt-16">
          <SectionHeader eyebrow="Enablement packets" title="Draft packets ready for review" />
          {packets.length > 0 ? (
            <div className="mt-8 grid gap-6 lg:grid-cols-3">
              {packets.map((packet) => (
                <PacketCard key={packet.packet_id} packet={packet} />
              ))}
            </div>
          ) : (
            <div className="mt-8 rounded-lg border border-[#181a20]/10 bg-white p-8 text-center">
              <p className="text-sm text-[#5d5f68]">No enablement packets are available in the current report.</p>
            </div>
          )}
        </section>

        <div className="mt-12 flex flex-wrap gap-3">
          <Link
            href="/livelihood-loom/market-map"
            className="inline-flex items-center gap-2 rounded-lg bg-[#181a20] px-4 py-3 text-sm font-semibold text-white transition hover:bg-[#2c303a]"
          >
            Explore market map
            <ArrowRight size={16} />
          </Link>
          <Link
            href="/livelihood-loom/investor-brief"
            className="inline-flex items-center gap-2 rounded-lg border border-[#181a20]/15 px-4 py-3 text-sm font-semibold text-[#181a20] transition hover:bg-[#181a20]/5"
          >
            Investor brief
            <ArrowRight size={16} />
          </Link>
        </div>
      </div>
    </PublicShell>
  );
}
