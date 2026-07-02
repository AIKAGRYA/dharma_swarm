import type { Metadata } from "next";
import Link from "next/link";
import {
  ArrowRight,
  BadgeCheck,
  CircleDollarSign,
  FileCheck2,
  LockKeyhole,
  ShieldCheck,
  TrendingUp,
} from "lucide-react";
import { PublicShell } from "@/components/livelihood-loom/public/PublicShell";
import { PublicHero } from "@/components/livelihood-loom/public/PublicHero";
import { SectionHeader } from "@/components/livelihood-loom/public/SectionHeader";
import { StatCard } from "@/components/livelihood-loom/public/StatCard";
import { WedgeCard } from "@/components/livelihood-loom/public/WedgeCard";
import { CandidateTable } from "@/components/livelihood-loom/public/CandidateTable";
import { ProofLink } from "@/components/livelihood-loom/public/ProofLink";
import { loadLivelihoodLoomPublicSite } from "@/lib/livelihoodLoomPublic";
import { loadLivelihoodLoomCandidates, loadLivelihoodLoomWedges } from "@/lib/livelihoodLoom";

export const metadata: Metadata = {
  title: "Livelihood Loom | Capital-grade maps for the informal economy",
  description:
    "Investor and sponsor intelligence for public-source informal-economy enablement, safety-reviewed partner packets, and approval-ready action queues.",
  openGraph: {
    title: "Livelihood Loom",
    description:
      "Capital-grade maps for the informal economy, grounded in public-source evidence and human-governed action gates.",
    images: ["/livelihood-loom/hero-market-network.png"],
  },
};

const principles = [
  {
    title: "Public-source intelligence",
    body: "Starts from aggregate public enabler data, not private worker surveillance.",
    icon: ShieldCheck,
  },
  {
    title: "Capital allocation clarity",
    body: "Ranks markets by where sponsors can fund practical rails for earning, payment, demand, and logistics.",
    icon: CircleDollarSign,
  },
  {
    title: "Human-governed action",
    body: "Every external contact, publication, payment, and provider claim stays behind an approval gate.",
    icon: LockKeyhole,
  },
];

const operatingLoop = [
  "Map public livelihood infrastructure",
  "Prioritize high-signal markets",
  "Red-team safety and exploitation risks",
  "Package sponsor-ready enablement briefs",
  "Queue human-approved external action",
];

export default function LivelihoodLoomPublicPage() {
  const site = loadLivelihoodLoomPublicSite();
  const candidates = loadLivelihoodLoomCandidates().slice(0, 8);
  const wedges = loadLivelihoodLoomWedges();

  return (
    <PublicShell hero>
      <PublicHero
        eyebrow="Sponsor and investor intelligence"
        title={site.brand}
        subtitle={site.headline}
        image="/livelihood-loom/hero-market-network.png"
        imageAlt="A micro-merchant payment and logistics market scene with aggregate network intelligence"
        ctas={[
          { label: "Open investor brief", href: "/livelihood-loom/investor-brief", variant: "primary" },
          { label: "Review proof packet", href: "/livelihood-loom/proof-packet", variant: "secondary" },
        ]}
      />

      <section className="-mt-16 px-5 sm:px-8 relative z-20">
        <div className="mx-auto grid max-w-7xl gap-3 md:grid-cols-4">
          {site.heroStats.map((stat) => (
            <StatCard key={stat.label} label={stat.label} value={stat.value} detail={stat.detail} />
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-5 py-24 sm:px-8">
        <div className="grid gap-10 lg:grid-cols-[0.95fr_1.05fr]">
          <div>
            <SectionHeader
              eyebrow="Why now"
              title="The informal economy has rails. It needs a capital map."
              subtitle={site.subheadline}
            />
            <div className="mt-8">
              <Link
                href="/livelihood-loom/thesis"
                className="inline-flex items-center gap-2 text-sm font-semibold text-[#0d615f] transition hover:text-[#181a20]"
              >
                Read the thesis
                <ArrowRight size={16} />
              </Link>
            </div>
          </div>
          <div className="grid gap-4">
            {principles.map((item) => {
              const Icon = item.icon;
              return (
                <article
                  key={item.title}
                  className="rounded-lg border border-[#181a20]/10 bg-white p-5 shadow-sm"
                >
                  <div className="flex items-start gap-4">
                    <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-[#0d615f] text-white">
                      <Icon size={20} aria-hidden="true" />
                    </span>
                    <div>
                      <h3 className="font-heading text-lg font-semibold text-[#181a20]">{item.title}</h3>
                      <p className="mt-2 text-sm leading-6 text-[#5d5f68]">{item.body}</p>
                    </div>
                  </div>
                </article>
              );
            })}
          </div>
        </div>
      </section>

      <section className="bg-[#181a20] px-5 py-24 text-white sm:px-8">
        <div className="mx-auto max-w-7xl">
          <SectionHeader
            eyebrow="Evidence packet"
            title="Built from local reports, not pitch-deck fiction."
            subtitle="The current packet prioritizes public-source candidates, groups them into ROI wedges, and red-teams each candidate before any sponsor-facing action is allowed."
            dark
            align="center"
            className="mx-auto max-w-3xl"
          />

          <div className="mt-12 grid gap-4 sm:grid-cols-3">
            {site.investorSignals.map((signal) => (
              <StatCard
                key={signal.label}
                label={signal.label}
                value={signal.value}
                detail={signal.detail}
                variant="dark"
              />
            ))}
          </div>

          <div className="mt-12 grid gap-4 lg:grid-cols-3">
            {wedges.map((wedge) => (
              <WedgeCard key={wedge.wedge_id} wedge={wedge} />
            ))}
          </div>

          <div className="mt-10 flex flex-wrap justify-center gap-3">
            <ProofLink href="/api/livelihood-loom" label="View JSON proof" variant="api" />
            <ProofLink href="/dashboard/livelihood-loom" label="Internal desk" variant="desk" />
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-5 py-24 sm:px-8">
        <div className="grid gap-10 lg:grid-cols-[1.1fr_0.9fr]">
          <div>
            <SectionHeader
              eyebrow="Investor brief"
              title="A fundable wedge with visible gates."
            />
            <p className="mt-5 text-lg leading-8 text-[#4e5060]">
              The first sponsor lane is <strong>{site.sponsorTarget}</strong> as a draft target, paired with the
              highest-ranked market wedge and a human review packet. The system is ready for review, not autonomous
              outreach.
            </p>
            <div className="mt-8 grid gap-3">
              {operatingLoop.map((item, index) => (
                <div
                  key={item}
                  className="flex items-center gap-4 rounded-lg border border-[#181a20]/10 bg-white p-4"
                >
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[#d47db5]/15 font-mono text-sm font-semibold text-[#9b477d]">
                    {index + 1}
                  </span>
                  <span className="text-sm font-medium text-[#181a20]">{item}</span>
                </div>
              ))}
            </div>
          </div>

          <aside>
            <div className="flex items-center gap-3">
              <span className="flex h-11 w-11 items-center justify-center rounded-lg bg-[#d4a855]/16 text-[#9c6f16]">
                <TrendingUp size={21} aria-hidden="true" />
              </span>
              <div>
                <h3 className="font-heading text-xl font-semibold text-[#181a20]">Current status</h3>
                <p className="text-sm text-[#5d5f68]">Truthful readiness signal</p>
              </div>
            </div>
            <div className="mt-6 space-y-4">
              <StatusRow label="Safety review" value={site.safetySummary} />
              <StatusRow label="Provider proof" value={site.statusNote} />
              <StatusRow label="External action" value={site.proofBoundary} />
            </div>
            <div className="mt-6 rounded-lg bg-[#181a20] p-5 text-white shadow-xl shadow-black/10">
              <div className="flex items-center gap-2 text-[#4fd1d9]">
                <BadgeCheck size={18} aria-hidden="true" />
                <span className="text-sm font-semibold uppercase">Diligence posture</span>
              </div>
              <p className="mt-3 text-sm leading-7 text-white/68">
                This page is a local draft website and not a securities offering. External publication, outreach, and
                fundraising claims require human approval and a real acted receipt.
              </p>
            </div>
            <div className="mt-6 flex flex-wrap gap-3">
              <Link
                href="/livelihood-loom/investor-brief"
                className="inline-flex items-center gap-2 rounded-lg bg-[#181a20] px-4 py-3 text-sm font-semibold text-white transition hover:bg-[#2c303a]"
              >
                Full investor brief
                <ArrowRight size={16} />
              </Link>
              <Link
                href="/livelihood-loom/proof-packet"
                className="inline-flex items-center gap-2 rounded-lg border border-[#181a20]/15 px-4 py-3 text-sm font-semibold text-[#181a20] transition hover:bg-[#181a20]/5"
              >
                Proof packet
                <FileCheck2 size={16} />
              </Link>
            </div>
          </aside>
        </div>
      </section>

      <section className="bg-white px-5 py-20 sm:px-8">
        <div className="mx-auto max-w-7xl">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
            <SectionHeader eyebrow="Top candidates" title="The first visible shortlist." />
            <p className="max-w-xl text-sm leading-6 text-[#5d5f68]">
              Public-source candidate names are shown for diligence orientation only. Blocked and review statuses remain
              visible by design.
            </p>
          </div>
          <div className="mt-8">
            <CandidateTable candidates={candidates} />
          </div>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link
              href="/livelihood-loom/market-map"
              className="inline-flex items-center gap-2 rounded-lg bg-[#181a20] px-4 py-3 text-sm font-semibold text-white transition hover:bg-[#2c303a]"
            >
              Explore market map
              <ArrowRight size={16} />
            </Link>
            <ProofLink href="/api/livelihood-loom" label="View JSON proof" variant="api" />
          </div>
        </div>
      </section>
    </PublicShell>
  );
}

function StatusRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-[#181a20]/10 bg-[#f9f7f1] p-4">
      <p className="text-xs font-semibold uppercase text-[#60736b]">{label}</p>
      <p className="mt-2 text-sm leading-6 text-[#181a20]">{value}</p>
    </div>
  );
}
