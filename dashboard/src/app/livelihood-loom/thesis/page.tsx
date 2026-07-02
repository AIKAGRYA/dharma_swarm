import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight, Map, SearchCheck, ShieldCheck, Target } from "lucide-react";
import { PublicShell } from "@/components/livelihood-loom/public/PublicShell";
import { SectionHeader } from "@/components/livelihood-loom/public/SectionHeader";
import { loadLivelihoodLoomDashboard } from "@/lib/livelihoodLoom";

export const metadata: Metadata = {
  title: "Livelihood Loom | Investment thesis",
  description:
    "Why the informal economy needs a capital map: the problem, opportunity, approach, and differentiation behind Livelihood Loom.",
  openGraph: {
    title: "Livelihood Loom | Investment thesis",
    description:
      "Capital-grade maps for the informal economy, grounded in public-source evidence and human-governed action gates.",
    images: ["/livelihood-loom/hero-market-network.png"],
  },
};

export default function ThesisPage() {
  const data = loadLivelihoodLoomDashboard();
  const topWedge = data.wedges[0];

  return (
    <PublicShell>
      <div className="mx-auto max-w-7xl px-5 py-24 sm:px-8">
        <SectionHeader
          eyebrow="Investment thesis"
          title="The informal economy has rails. It needs a capital map."
          subtitle="Livelihood Loom turns fragmented public livelihood infrastructure into sponsor-readable markets with evidence, safety gates, and clear next actions."
          align="center"
          className="mx-auto max-w-3xl"
        />

        <div className="mt-16 grid gap-6 md:grid-cols-2">
          <ThesisCard
            icon={SearchCheck}
            eyebrow="Problem"
            title="Capital cannot see where to enter"
            paragraphs={[
              "The informal economy is not invisible — it is fragmented. Payment acceptance, logistics, merchant demand, and responsible finance exist in disconnected pockets across markets and datasets.",
              "Sponsors and investors therefore face a search problem: high-friction due diligence, unclear counterparty quality, and no standardized way to compare livelihood enablement opportunities.",
            ]}
          />

          <ThesisCard
            icon={Target}
            eyebrow="Opportunity"
            title="Public data can become a market map"
            paragraphs={[
              "Millions of public-source enabler records describe who provides the rails for earning, payment, demand, and logistics. Those records can be ranked, grouped, and safety-reviewed into investable wedges.",
              topWedge
              ? `The current map surfaces ${data.candidateCount.toLocaleString()} candidates and prioritizes ${data.topCount} into ${data.wedges.length} ROI wedges, led by ${topWedge.label}.`
              : "The current map surfaces thousands of candidates and prioritizes them into ranked ROI wedges.",
            ]}
          />

          <ThesisCard
            icon={Map}
            eyebrow="Approach"
            title="Map, prioritize, red-team, package, approve"
            paragraphs={[
              "Livelihood Loom reads public-source data, scores candidates by capital relevance and welfare impact, groups them into wedges, and runs a structured safety review before any sponsor-facing action.",
              "Each wedge becomes a sponsor lane. Each candidate gets a safety status. Each external action is queued behind a human-governed gate.",
            ]}
          />

          <ThesisCard
            icon={ShieldCheck}
            eyebrow="Differentiation"
            title="Evidence-first, not surveillance-first"
            paragraphs={[
              "We do not scrape private worker behavior or claim proprietary ground truth. We start from public enabler data, publish methodology, expose safety flags, and keep all outreach draft-only until a human approves a real counterparty action.",
              "The result is a diligence-ready map, not an automation fantasy.",
            ]}
          />
        </div>

        <section className="mt-20 rounded-2xl bg-[#181a20] px-6 py-16 text-white sm:px-12">
          <SectionHeader
            eyebrow="Capital map narrative"
            title="Wedges are sponsor lanes, not sectors"
            subtitle="Each wedge is a concentrated market where public-source candidates cluster, scored by ROI potential and reviewed for safety before any capital recommendation."
            dark
            align="center"
            className="mx-auto max-w-3xl"
          />
          <div className="mt-10 grid gap-4 sm:grid-cols-3">
            {data.wedges.map((wedge) => (
              <div
                key={wedge.wedge_id}
                className="rounded-lg border border-white/10 bg-white/[0.05] p-5"
              >
                <div className="flex items-center justify-between gap-3">
                  <span className="text-xs font-semibold uppercase text-white/48">
                    Wedge 0{wedge.rank}
                  </span>
                  <span className="rounded-lg bg-[#d4a855]/14 px-2.5 py-1 font-mono text-sm text-[#f2cf87]">
                    {wedge.roi_score.toFixed(3)}
                  </span>
                </div>
                <h3 className="mt-5 font-heading text-xl font-semibold text-white">{wedge.label}</h3>
                <p className="mt-3 text-sm leading-7 text-white/62">{wedge.roi_thesis}</p>
                <p className="mt-5 text-xs font-semibold uppercase text-[#8fa89b]">
                  {wedge.candidate_count_in_top_50} Top 50 candidates
                </p>
              </div>
            ))}
          </div>
          <div className="mt-10 flex justify-center">
            <Link
              href="/livelihood-loom/market-map"
              className="inline-flex items-center gap-2 rounded-lg bg-[#4fd1d9] px-5 py-3 text-sm font-semibold text-[#071013] transition hover:bg-[#7be8ee]"
            >
              Explore market map
              <ArrowRight size={17} />
            </Link>
          </div>
        </section>
      </div>
    </PublicShell>
  );
}

function ThesisCard({
  icon: Icon,
  eyebrow,
  title,
  paragraphs,
}: {
  icon: React.ElementType;
  eyebrow: string;
  title: string;
  paragraphs: string[];
}) {
  return (
    <article className="rounded-lg border border-[#181a20]/10 bg-white p-6 sm:p-8">
      <span className="flex h-11 w-11 items-center justify-center rounded-lg bg-[#0d615f]/10 text-[#0d615f]">
        <Icon size={20} aria-hidden="true" />
      </span>
      <p className="mt-5 text-xs font-semibold uppercase text-[#60736b]">{eyebrow}</p>
      <h2 className="mt-2 font-heading text-2xl font-semibold text-[#181a20]">{title}</h2>
      <div className="mt-4 space-y-4">
        {paragraphs.map((paragraph, index) => (
          <p key={index} className="text-sm leading-7 text-[#4e5060]">{paragraph}</p>
        ))}
      </div>
    </article>
  );
}
