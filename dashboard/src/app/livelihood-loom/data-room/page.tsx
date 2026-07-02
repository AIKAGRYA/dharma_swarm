import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight, FileJson, LayoutDashboard, ShieldCheck } from "lucide-react";
import { PublicShell } from "@/components/livelihood-loom/public/PublicShell";
import { SectionHeader } from "@/components/livelihood-loom/public/SectionHeader";
import { DataRoomFileList } from "@/components/livelihood-loom/public/DataRoomFileList";
import { TruthGate } from "@/components/livelihood-loom/public/TruthGate";
import { SafetyBar } from "@/components/livelihood-loom/public/SafetyBar";
import { loadLivelihoodLoomDataRoom, loadLivelihoodLoomStatusGates } from "@/lib/livelihoodLoom";

export const metadata: Metadata = {
  title: "Data Room | Livelihood Loom",
  description:
    "Download receipts, JSON proof, safety review, and governance gates for the Livelihood Loom informal-economy intelligence packet.",
  openGraph: {
    title: "Data Room | Livelihood Loom",
    description:
      "Download receipts, JSON proof, safety review, and governance gates for the Livelihood Loom informal-economy intelligence packet.",
    images: ["/livelihood-loom/hero-market-network.png"],
  },
};

const TOPIC_LINKS = [
  { label: "Methodology", href: "/livelihood-loom/diligence/methodology" },
  { label: "Safety", href: "/livelihood-loom/diligence/safety" },
  { label: "Provider readiness", href: "/livelihood-loom/diligence/provider-readiness" },
  { label: "External action", href: "/livelihood-loom/diligence/external-action" },
];

export default function DataRoomPage() {
  const dataRoom = loadLivelihoodLoomDataRoom();
  const gates = loadLivelihoodLoomStatusGates();

  const groupedFiles = {
    cycle: Object.fromEntries(
      Object.entries(dataRoom.files).filter(([key]) => key === "cycle"),
    ),
    cultivation: Object.fromEntries(
      Object.entries(dataRoom.files).filter(([key]) => ["top50", "wedges"].includes(key)),
    ),
    safety: Object.fromEntries(
      Object.entries(dataRoom.files).filter(([key]) => key === "safety"),
    ),
    enablement: Object.fromEntries(
      Object.entries(dataRoom.files).filter(([key]) => key === "packets"),
    ),
    demand: Object.fromEntries(
      Object.entries(dataRoom.files).filter(([key]) => key === "demand"),
    ),
    promotion: Object.fromEntries(
      Object.entries(dataRoom.files).filter(([key]) => key === "promotion"),
    ),
  };

  return (
    <PublicShell className="pb-20">
      <section className="px-5 pt-28 sm:px-8">
        <div className="mx-auto max-w-7xl">
          <SectionHeader
            eyebrow="Investor and sponsor diligence"
            title="Data room"
            subtitle="Every receipt, report file, safety review, and governance gate behind the current Livelihood Loom packet. All source data is local to this repository."
          />

          <div className="mt-10 flex flex-wrap gap-3">
            <a
              href="/api/livelihood-loom"
              className="inline-flex items-center gap-2 rounded-lg bg-[#181a20] px-4 py-3 text-sm font-semibold text-white transition hover:bg-[#2c303a]"
            >
              <FileJson size={16} aria-hidden="true" />
              Review proof
              <ArrowRight size={16} />
            </a>
            <Link
              href="/livelihood-loom/investor-brief"
              className="inline-flex items-center gap-2 rounded-lg border border-[#181a20]/15 px-4 py-3 text-sm font-semibold text-[#181a20] transition hover:bg-[#181a20]/5"
            >
              Open investor brief
              <ArrowRight size={16} />
            </Link>
            <Link
              href="/dashboard/livelihood-loom"
              className="inline-flex items-center gap-2 rounded-lg border border-[#181a20]/15 px-4 py-3 text-sm font-semibold text-[#181a20] transition hover:bg-[#181a20]/5"
            >
              <LayoutDashboard size={16} aria-hidden="true" />
              Internal desk
            </Link>
          </div>
        </div>
      </section>

      <section className="px-5 py-16 sm:px-8">
        <div className="mx-auto max-w-7xl">
          <div className="grid grid-cols-1 gap-10 lg:grid-cols-[1fr_0.45fr]">
            <div className="space-y-12">
              <FileGroup title="Cycle receipts" files={groupedFiles.cycle}>
                <p className="mt-3 text-sm leading-6 text-[#4e5060]">
                  The latest run receipt. Status reflects the most recent generation cycle, not a
                  live external signal.
                </p>
              </FileGroup>

              <FileGroup title="Cultivation" files={groupedFiles.cultivation}>
                <p className="mt-3 text-sm leading-6 text-[#4e5060]">
                  Top 50 candidates and the wedge map derived from public-source data. These are
                  draft prioritizations, not investment recommendations.
                </p>
                <div className="mt-4 flex flex-wrap gap-3">
                  <Link
                    href="/livelihood-loom/market-map"
                    className="inline-flex items-center gap-1.5 text-sm font-semibold text-[#0d615f] transition hover:text-[#181a20]"
                  >
                    Explore market map
                    <ArrowRight size={14} />
                  </Link>
                </div>
              </FileGroup>

              <FileGroup title="Safety" files={groupedFiles.safety}>
                <div className="mt-4 rounded-lg border border-[#181a20]/10 bg-white p-5">
                  <div className="flex items-center gap-2">
                    <ShieldCheck size={18} className="text-rokusho" aria-hidden="true" />
                    <h4 className="font-heading text-sm font-semibold text-[#181a20]">
                      Safety posture
                    </h4>
                  </div>
                  <SafetyBar
                    allowed={dataRoom.safety.allowed}
                    needs_review={dataRoom.safety.needs_review}
                    blocked={dataRoom.safety.blocked}
                    total={dataRoom.safety.total}
                    className="mt-4"
                  />
                </div>
                <div className="mt-4 flex flex-wrap gap-3">
                  <Link
                    href="/livelihood-loom/safety-governance"
                    className="inline-flex items-center gap-1.5 text-sm font-semibold text-[#0d615f] transition hover:text-[#181a20]"
                  >
                    Safety and governance
                    <ArrowRight size={14} />
                  </Link>
                  <Link
                    href="/livelihood-loom/diligence/safety"
                    className="inline-flex items-center gap-1.5 text-sm font-semibold text-[#0d615f] transition hover:text-[#181a20]"
                  >
                    Safety diligence
                    <ArrowRight size={14} />
                  </Link>
                </div>
              </FileGroup>

              <FileGroup title="Enablement packets" files={groupedFiles.enablement}>
                <p className="mt-3 text-sm leading-6 text-[#4e5060]">
                  Sponsor-facing packet index. Each packet links to a wedge, beneficiary profile,
                  candidate partners, and next safe action.
                </p>
                <div className="mt-4 flex flex-wrap gap-3">
                  <Link
                    href="/livelihood-loom/proof-packet"
                    className="inline-flex items-center gap-1.5 text-sm font-semibold text-[#0d615f] transition hover:text-[#181a20]"
                  >
                    Proof packet overview
                    <ArrowRight size={14} />
                  </Link>
                </div>
              </FileGroup>

              <FileGroup title="Demand" files={groupedFiles.demand}>
                <p className="mt-3 text-sm leading-6 text-[#4e5060]">
                  Sponsor briefs and external action status. Outreach is draft-only until a human
                  governor approves and a real counterparty acts.
                </p>
                <div className="mt-4">
                  <span className="inline-flex items-center rounded-md bg-[#f4f1ea] px-2.5 py-1 text-xs font-semibold uppercase text-[#60736b]">
                    External action status: {dataRoom.demand.external_action_status}
                  </span>
                </div>
              </FileGroup>

              <FileGroup title="Promotion" files={groupedFiles.promotion}>
                <p className="mt-3 text-sm leading-6 text-[#4e5060]">
                  Sponsor one-pager and human review packet artifacts. Present flag indicates whether
                  promotion metadata was found in the latest run.
                </p>
                <div className="mt-4 grid gap-3 sm:grid-cols-2">
                  <StatusItem label="Promotion present" value={dataRoom.promotion.present ? "Yes" : "No"} />
                  <StatusItem label="Sponsor target" value={dataRoom.promotion.sponsorTarget} />
                  <StatusItem label="Provider gate" value={dataRoom.promotion.providerGateStatus} />
                  <StatusItem label="Outreach status" value={dataRoom.promotion.outreachStatus} />
                </div>
              </FileGroup>

              <div>
                <h3 className="font-heading text-xl font-semibold text-[#181a20]">Receipt index</h3>
                <DataRoomFileList files={dataRoom.files} receipts={dataRoom.receipts} className="mt-5" />
              </div>
            </div>

            <aside className="space-y-8">
              <div className="rounded-lg border border-[#181a20]/10 bg-white p-5">
                <h3 className="font-heading text-lg font-semibold text-[#181a20]">Governance gates</h3>
                <p className="mt-2 text-sm leading-6 text-[#4e5060]">
                  Current status gates from the latest cycle and promotion boundary checks.
                </p>
                <div className="mt-5 space-y-4">
                  {gates.map((gate) => (
                    <TruthGate key={gate.name} gate={gate} />
                  ))}
                </div>
              </div>

              <div className="rounded-lg border border-[#181a20]/10 bg-white p-5">
                <h3 className="font-heading text-lg font-semibold text-[#181a20]">Diligence topics</h3>
                <ul className="mt-4 space-y-2">
                  {TOPIC_LINKS.map((link) => (
                    <li key={link.href}>
                      <Link
                        href={link.href}
                        className="flex items-center justify-between rounded-lg border border-[#181a20]/10 px-4 py-3 text-sm font-semibold text-[#181a20] transition hover:bg-[#f4f1ea]"
                      >
                        {link.label}
                        <ArrowRight size={14} />
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>

              <div className="rounded-lg bg-[#181a20] p-5 text-white">
                <h3 className="font-heading text-lg font-semibold">Use of this data</h3>
                <p className="mt-3 text-sm leading-6 text-white/68">
                  This data room is a local diligence aid. It is not a securities offering,
                  prospectus, or investment recommendation. Provider-green claims, external
                  outreach, and revenue claims are explicitly gated and require human approval and
                  acted receipts before they can be asserted publicly.
                </p>
              </div>
            </aside>
          </div>
        </div>
      </section>
    </PublicShell>
  );
}

function FileGroup({
  title,
  files,
  children,
}: {
  title: string;
  files: Record<string, string>;
  children?: React.ReactNode;
}) {
  return (
    <div>
      <h3 className="font-heading text-xl font-semibold text-[#181a20]">{title}</h3>
      <DataRoomFileList files={files} />
      {children}
    </div>
  );
}

function StatusItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-[#181a20]/10 bg-[#f9f7f1] p-3">
      <p className="text-xs font-semibold uppercase text-[#60736b]">{label}</p>
      <p className="mt-1 text-sm font-semibold text-[#181a20]">{value}</p>
    </div>
  );
}
