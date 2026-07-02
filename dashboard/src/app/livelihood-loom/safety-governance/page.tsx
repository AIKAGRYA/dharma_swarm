import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight, FileCheck2, LockKeyhole, ShieldCheck } from "lucide-react";
import { PublicShell } from "@/components/livelihood-loom/public/PublicShell";
import { SectionHeader } from "@/components/livelihood-loom/public/SectionHeader";
import { SafetyBar } from "@/components/livelihood-loom/public/SafetyBar";
import { TruthGate } from "@/components/livelihood-loom/public/TruthGate";
import { ProofLink } from "@/components/livelihood-loom/public/ProofLink";
import {
  loadLivelihoodLoomDashboard,
  loadLivelihoodLoomStatusGates,
} from "@/lib/livelihoodLoom";

export const metadata: Metadata = {
  title: "Livelihood Loom | Safety and governance",
  description:
    "Safety posture, policy flags, human-governed action gates, and the no-fabrication statement behind Livelihood Loom.",
  openGraph: {
    title: "Livelihood Loom | Safety and governance",
    description:
      "Capital-grade maps for the informal economy, grounded in public-source evidence and human-governed action gates.",
    images: ["/livelihood-loom/hero-market-network.png"],
  },
};

export default function SafetyGovernancePage() {
  const dashboard = loadLivelihoodLoomDashboard();
  const gates = loadLivelihoodLoomStatusGates();
  const safety = dashboard.safety;

  return (
    <PublicShell>
      <div className="mx-auto max-w-7xl px-5 py-24 sm:px-8">
        <SectionHeader
          eyebrow="Safety and governance"
          title="Evidence-first, human-governed, never autonomous outreach"
          subtitle="All claims are gated. Safety flags are visible. External action requires human approval and a real acted receipt."
          align="center"
          className="mx-auto max-w-3xl"
        />

        <section className="mt-12 grid gap-6 lg:grid-cols-2">
          <div className="rounded-lg border border-[#181a20]/10 bg-white p-6 sm:p-8">
            <div className="flex items-center gap-3">
              <span className="flex h-11 w-11 items-center justify-center rounded-lg bg-[#0d615f]/10 text-[#0d615f]">
                <ShieldCheck size={21} aria-hidden="true" />
              </span>
              <div>
                <h2 className="font-heading text-2xl font-semibold text-[#181a20]">Safety posture</h2>
                <p className="text-sm text-[#5d5f68]">Current review summary</p>
              </div>
            </div>
            <div className="mt-6">
              <SafetyBar
                allowed={safety.allowed}
                needs_review={safety.needs_review}
                blocked={safety.blocked}
                total={safety.total}
              />
            </div>
            <p className="mt-5 text-sm leading-6 text-[#4e5060]">
              {safety.allowed} candidates are allowed for sponsor consideration, {safety.needs_review} require further
              human review, and {safety.blocked} are blocked. These statuses are derived from public-source signals and
              remain subject to final human judgment before any action.
            </p>
          </div>

          <div className="rounded-lg border border-[#181a20]/10 bg-white p-6 sm:p-8">
            <div className="flex items-center gap-3">
              <span className="flex h-11 w-11 items-center justify-center rounded-lg bg-[#d4a855]/16 text-[#9c6f16]">
                <LockKeyhole size={21} aria-hidden="true" />
              </span>
              <div>
                <h2 className="font-heading text-2xl font-semibold text-[#181a20]">Human-governed action</h2>
                <p className="text-sm text-[#5d5f68]">No autonomous external contact</p>
              </div>
            </div>
            <ul className="mt-6 list-disc space-y-2 pl-5 text-sm leading-6 text-[#4e5060]">
              <li>No outreach is sent without explicit human approval.</li>
              <li>No provider-green claim is made before the provider readiness gate is green.</li>
              <li>No revenue, partnership, or fundraising claim is published without acted receipts.</li>
              <li>All public pages are local drafts until an operator explicitly approves deployment.</li>
            </ul>
          </div>
        </section>

        <section className="mt-12 rounded-2xl bg-[#181a20] px-6 py-12 text-white sm:px-12">
          <div className="mx-auto max-w-3xl text-center">
            <div className="flex items-center justify-center gap-2 text-[#4fd1d9]">
              <FileCheck2 size={20} aria-hidden="true" />
              <span className="text-sm font-semibold uppercase">No-fabrication statement</span>
            </div>
            <p className="mt-4 text-lg leading-8 text-white/80">
              This site contains no fake testimonials, logos, investors, revenue, partnerships, or external action
              claims. All numbers come from local reports. All provider-green, outreach, publication, and revenue claims
              are explicitly gated.
            </p>
          </div>
        </section>

        <section className="mt-16">
          <SectionHeader eyebrow="Policy flags" title="What the safety review is watching" />
          <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {Object.entries(safety.flag_counts).map(([flag, count]) => (
              <article
                key={flag}
                className="rounded-lg border border-[#181a20]/10 bg-white p-5"
              >
                <p className="text-xs font-semibold uppercase text-[#60736b]">{flag}</p>
                <p className="mt-3 font-heading text-4xl font-semibold text-[#181a20]">{count}</p>
                <p className="mt-2 text-sm text-[#5d5f68]">candidates flagged</p>
              </article>
            ))}
          </div>
        </section>

        <section className="mt-16">
          <SectionHeader eyebrow="Readiness gates" title="Governance gates before action" />
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
