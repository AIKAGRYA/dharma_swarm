import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight, FileCheck2, TrendingUp } from "lucide-react";
import { PublicShell } from "@/components/livelihood-loom/public/PublicShell";
import { SectionHeader } from "@/components/livelihood-loom/public/SectionHeader";
import { SponsorTargetCard } from "@/components/livelihood-loom/public/SponsorTargetCard";
import { TruthGate } from "@/components/livelihood-loom/public/TruthGate";
import { ProofLink } from "@/components/livelihood-loom/public/ProofLink";
import {
  loadLivelihoodLoomDashboard,
  loadLivelihoodLoomSponsorTarget,
  loadLivelihoodLoomStatusGates,
} from "@/lib/livelihoodLoom";

export const metadata: Metadata = {
  title: "Livelihood Loom | Investor brief",
  description:
    "Operating loop, current status, sponsor target, and readiness gates for Livelihood Loom.",
  openGraph: {
    title: "Livelihood Loom | Investor brief",
    description:
      "Capital-grade maps for the informal economy, grounded in public-source evidence and human-governed action gates.",
    images: ["/livelihood-loom/hero-market-network.png"],
  },
};

const operatingLoop = [
  { title: "Map", body: "Ingest public livelihood infrastructure records and normalize them into candidates." },
  { title: "Prioritize", body: "Score candidates by capital relevance, welfare impact, and evidence strength." },
  { title: "Red-team", body: "Run a structured safety review and flag exploitation or compliance risks." },
  { title: "Package", body: "Group candidates into ROI wedges and build sponsor-ready enablement briefs." },
  { title: "Approve", body: "Queue every external action behind a human-governed gate with acted receipts." },
];

export default function InvestorBriefPage() {
  const dashboard = loadLivelihoodLoomDashboard();
  const sponsorTarget = loadLivelihoodLoomSponsorTarget();
  const gates = loadLivelihoodLoomStatusGates();

  const greenGates = gates.filter((gate) => gate.status === "green" || gate.complete).length;

  return (
    <PublicShell>
      <div className="mx-auto max-w-7xl px-5 py-24 sm:px-8">
        <SectionHeader
          eyebrow="Investor brief"
          title="A fundable wedge with visible gates"
          subtitle="Current operating status, draft sponsor target, and readiness gates. All external action claims are explicitly gated and not claimed as completed."
          align="center"
          className="mx-auto max-w-3xl"
        />

        <section className="mt-12">
          <SectionHeader eyebrow="Operating loop" title="From raw data to governed action" />
          <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            {operatingLoop.map((step, index) => (
              <article
                key={step.title}
                className="rounded-lg border border-[#181a20]/10 bg-white p-5"
              >
                <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#d47db5]/15 font-mono text-sm font-semibold text-[#9b477d]">
                  {index + 1}
                </span>
                <h3 className="mt-4 font-heading text-lg font-semibold text-[#181a20]">{step.title}</h3>
                <p className="mt-2 text-sm leading-6 text-[#5d5f68]">{step.body}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="mt-16 grid gap-8 lg:grid-cols-[1fr_0.6fr]">
          <div>
            {sponsorTarget ? (
              <SponsorTargetCard target={sponsorTarget} />
            ) : (
              <div className="rounded-lg border border-[#181a20]/10 bg-white p-8">
                <p className="text-sm font-semibold uppercase text-[#60736b]">Draft sponsor target</p>
                <h1 className="mt-2 font-heading text-3xl font-semibold text-[#181a20]">{dashboard.promotion.sponsorTarget}</h1>
                <p className="mt-4 text-sm leading-6 text-[#4e5060]">
                  The first sponsor target is pending selection. No outreach has been drafted and no external action has
                  been taken.
                </p>
              </div>
            )}
          </div>

          <aside className="space-y-6">
            <div className="rounded-lg border border-[#181a20]/10 bg-white p-6">
              <div className="flex items-center gap-3">
                <span className="flex h-11 w-11 items-center justify-center rounded-lg bg-[#d4a855]/16 text-[#9c6f16]">
                  <TrendingUp size={21} aria-hidden="true" />
                </span>
                <div>
                  <h3 className="font-heading text-xl font-semibold text-[#181a20]">Current status</h3>
                  <p className="text-sm text-[#5d5f68]">Truthful readiness signal</p>
                </div>
              </div>              <div className="mt-6 space-y-3">
                <StatusRow label="Provider proof" value={dashboard.providerGreen ? "Green" : "Pending"} />
                <StatusRow label="Outreach status" value={dashboard.promotion.outreachStatus} />
                <StatusRow label="Acted receipt" value={dashboard.promotion.actedReceiptStatus} />
                <StatusRow label="Gates green/complete" value={`${greenGates} of ${gates.length}`} />
              </div>
            </div>

            <div className="rounded-lg bg-[#181a20] p-6 text-white">
              <div className="flex items-center gap-2 text-[#4fd1d9]">
                <FileCheck2 size={18} aria-hidden="true" />
                <span className="text-sm font-semibold uppercase">Diligence posture</span>
              </div>
              <p className="mt-3 text-sm leading-7 text-white/68">
                This site is a local draft and not a securities offering. External publication, outreach, and fundraising
                claims require human approval and a real acted receipt.
              </p>
            </div>
          </aside>
        </section>

        <section className="mt-16">
          <SectionHeader eyebrow="Readiness gates" title="Status gates before external action" />
          <div className="mt-8 grid gap-4">
            {gates.map((gate) => (
              <TruthGate key={gate.name} gate={gate} />
            ))}
          </div>
        </section>

        <div className="mt-12 flex flex-wrap gap-3">
          <Link
            href="/livelihood-loom/proof-packet"
            className="inline-flex items-center gap-2 rounded-lg bg-[#181a20] px-4 py-3 text-sm font-semibold text-white transition hover:bg-[#2c303a]"
          >
            Review proof packet
            <ArrowRight size={16} />
          </Link>
          <ProofLink href="/api/livelihood-loom" label="View JSON proof" variant="api" />
          <ProofLink href="/dashboard/livelihood-loom" label="Internal desk" variant="desk" />
        </div>
      </div>
    </PublicShell>
  );
}

function StatusRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between rounded-lg bg-[#f9f7f1] p-3">
      <span className="text-sm font-semibold text-[#60736b]">{label}</span>
      <span className="text-sm font-medium text-[#181a20]">{value}</span>
    </div>
  );
}
