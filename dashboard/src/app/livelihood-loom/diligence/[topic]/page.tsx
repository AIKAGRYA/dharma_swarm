import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight, FileJson, LayoutDashboard } from "lucide-react";
import { PublicShell } from "@/components/livelihood-loom/public/PublicShell";
import { SectionHeader } from "@/components/livelihood-loom/public/SectionHeader";
import { TruthGate } from "@/components/livelihood-loom/public/TruthGate";
import { DataRoomFileList } from "@/components/livelihood-loom/public/DataRoomFileList";
import {
  loadLivelihoodLoomDataRoom,
  loadLivelihoodLoomStatusGates,
  loadLivelihoodLoomDashboard,
} from "@/lib/livelihoodLoom";

export const dynamicParams = false;

const TOPICS = ["methodology", "safety", "provider-readiness", "external-action"] as const;

type Topic = (typeof TOPICS)[number];

interface TopicContent {
  title: string;
  eyebrow: string;
  subtitle: string;
  body: React.ReactNode;
  files: Record<string, string>;
  gateNames?: string[];
  ctas: { label: string; href: string; external?: boolean }[];
}

export function generateStaticParams(): Array<{ topic: Topic }> {
  return TOPICS.map((topic) => ({ topic }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ topic: string }> | { topic: string };
}): Promise<Metadata> {
  const { topic } = await params;
  const title = `${topicLabel(topic)} | Diligence | Livelihood Loom`;
  return {
    title,
    description: `Diligence note on ${topicLabel(topic)} for the Livelihood Loom informal-economy intelligence packet.`,
    openGraph: {
      title,
      description: `Diligence note on ${topicLabel(topic)} for the Livelihood Loom informal-economy intelligence packet.`,
      images: ["/livelihood-loom/hero-market-network.png"],
    },
  };
}

function topicLabel(topic: string): string {
  switch (topic) {
    case "methodology":
      return "Methodology";
    case "safety":
      return "Safety review";
    case "provider-readiness":
      return "Provider readiness";
    case "external-action":
      return "External action";
    default:
      return "Diligence";
  }
}

function getTopicContent(topic: Topic, dataRoom: ReturnType<typeof loadLivelihoodLoomDataRoom>): TopicContent {
  const { files } = dataRoom;

  switch (topic) {
    case "methodology":
      return {
        title: "Methodology",
        eyebrow: "How the map is built",
        subtitle:
          "Candidate discovery, scoring, wedge grouping, and prioritization are driven by local public-source data and explicit scoring components.",
        body: (
          <>
            <p className="text-[#4e5060]">
              Livelihood Loom starts from aggregate public records of livelihood enablers—payment
              rails, merchant demand platforms, logistics providers, and responsible finance
              actors—not from private worker surveillance or scraped individual records.
            </p>
            <p className="text-[#4e5060]">
              Each candidate carries a prioritization score built from scoring components (signal
              strength, geographic relevance, wedge fit, evidence quality). Wedges are formed by
              clustering high-scoring candidates into sponsor-readable market lanes and ranking each
              lane by an ROI score derived from concentration, country coverage, and enablement
              thesis.
            </p>
            <p className="text-[#4e5060]">
              The methodology is reproducible from the cycle receipt and the cultivation files. No
              model output is treated as ground truth; every score is paired with evidence
              references and a safety review before it can enter a sponsor-facing packet.
            </p>
          </>
        ),
        files: {
          cycle: files.cycle,
          top50: files.top50,
          wedges: files.wedges,
        },
        gateNames: ["methodology_complete", "data_quality"],
        ctas: [
          { label: "Explore market map", href: "/livelihood-loom/market-map" },
          { label: "View data room", href: "/livelihood-loom/data-room" },
          { label: "Review proof", href: "/api/livelihood-loom", external: true },
        ],
      };

    case "safety":
      return {
        title: "Safety review",
        eyebrow: "Red-team before action",
        subtitle:
          "Every Top 50 candidate is reviewed for exploitation risk, consumer harm, regulatory exposure, and model-confidence caveats.",
        body: (
          <>
            <p className="text-[#4e5060]">
              The safety review flags candidates as allowed, needs_review, or blocked. A blocked
              candidate is not included in any sponsor-facing packet. A needs_review candidate
              requires additional human scrutiny before it can be promoted.
            </p>
            <p className="text-[#4e5060]">
              Flags cover consumer harm, labor exploitation, regulatory risk, data-privacy concerns,
              and model-confidence gaps. Notes and evidence references are attached to each review
              entry so the reasoning is inspectable.
            </p>
            <p className="text-[#4e5060]">
              Safety is a gate, not a one-time check. Any change to candidate data, scoring, or
              wedge membership triggers a re-review before external action is allowed.
            </p>
          </>
        ),
        files: {
          safety: files.safety,
          top50: files.top50,
        },
        gateNames: ["safety_review_complete", "blocked_candidate_handling"],
        ctas: [
          { label: "Safety and governance", href: "/livelihood-loom/safety-governance" },
          { label: "View data room", href: "/livelihood-loom/data-room" },
          { label: "Review proof", href: "/api/livelihood-loom", external: true },
        ],
      };

    case "provider-readiness":
      return {
        title: "Provider readiness",
        eyebrow: "Before any provider-green claim",
        subtitle:
          "Provider readiness is a hard gate. The system does not claim a provider is green until the provider proof file passes explicit checks.",
        body: (
          <>
            <p className="text-[#4e5060]">
              A provider-green status means the selected sponsor target or infrastructure partner
              has passed a documented readiness review: public terms exist, a partner path is
              identifiable, and no blocking safety flags are present.
            </p>
            <p className="text-[#4e5060]">
              Until the provider readiness gate is green, all provider-green claims on public pages
              are suppressed and any outreach remains draft-only. The current status is derived
              from the promotion boundary files, not from a counterparty confirmation.
            </p>
            <p className="text-[#4e5060]">
              Do not treat a selected wedge or sponsor target as a committed partnership. It is a
              draft candidate awaiting final verification and human approval.
            </p>
          </>
        ),
        files: {
          promotion: files.promotion,
          demand: files.demand,
        },
        gateNames: ["Provider readiness"],
        ctas: [
          { label: "Investor brief", href: "/livelihood-loom/investor-brief" },
          { label: "View data room", href: "/livelihood-loom/data-room" },
          { label: "Internal desk", href: "/dashboard/livelihood-loom" },
        ],
      };

    case "external-action":
      return {
        title: "External action",
        eyebrow: "No outreach without receipts",
        subtitle:
          "External contact, publication, payment, and fundraising claims are gated by human approval and a real acted receipt.",
        body: (
          <>
            <p className="text-[#4e5060]">
              Livelihood Loom separates drafted action from acted action. Sponsor briefs and
              enablement packets can be prepared internally, but no email, proposal, publication,
              or payment may be sent without explicit human governor approval.
            </p>
            <p className="text-[#4e5060]">
              After approval, a real counterparty action must occur before the external acted
              receipt gate can advance. The system does not fabricate receipts or simulate
              counterparty responses.
            </p>
            <p className="text-[#4e5060]">
              Public pages therefore describe readiness posture only. Any claim of outreach sent,
              partnership formed, or revenue secured is false unless backed by the acted receipt
              gate and operator confirmation.
            </p>
          </>
        ),
        files: {
          demand: files.demand,
          promotion: files.promotion,
        },
        gateNames: ["External acted receipt"],
        ctas: [
          { label: "Investor brief", href: "/livelihood-loom/investor-brief" },
          { label: "View data room", href: "/livelihood-loom/data-room" },
          { label: "Internal desk", href: "/dashboard/livelihood-loom" },
        ],
      };
  }
}

export default async function DiligenceTopicPage({
  params,
}: {
  params: Promise<{ topic: string }> | { topic: string };
}) {
  const { topic } = await params;
  const dataRoom = loadLivelihoodLoomDataRoom();
  const dashboard = loadLivelihoodLoomDashboard();
  const gates = loadLivelihoodLoomStatusGates();
  const content = getTopicContent(topic as Topic, dataRoom);

  const relevantGates = content.gateNames
    ? gates.filter((gate) => content.gateNames?.includes(gate.name))
    : [];

  return (
    <PublicShell className="pb-20">
      <section className="px-5 pt-28 sm:px-8">
        <div className="mx-auto max-w-7xl">
          <SectionHeader
            eyebrow={content.eyebrow}
            title={content.title}
            subtitle={content.subtitle}
          />

          <div className="mt-10 flex flex-wrap gap-3">
            {content.ctas.map((cta) =>
              cta.external ? (
                <a
                  key={cta.href}
                  href={cta.href}
                  className="inline-flex items-center gap-2 rounded-lg bg-[#181a20] px-4 py-3 text-sm font-semibold text-white transition hover:bg-[#2c303a]"
                >
                  <FileJson size={16} aria-hidden="true" />
                  {cta.label}
                  <ArrowRight size={16} />
                </a>
              ) : (
                <Link
                  key={cta.href}
                  href={cta.href}
                  className={`inline-flex items-center gap-2 rounded-lg px-4 py-3 text-sm font-semibold transition ${
                    cta.href === "/livelihood-loom/data-room"
                      ? "border border-[#181a20]/15 text-[#181a20] hover:bg-[#181a20]/5"
                      : "border border-[#181a20]/15 text-[#181a20] hover:bg-[#181a20]/5"
                  }`}
                >
                  {cta.href === "/dashboard/livelihood-loom" && (
                    <LayoutDashboard size={16} aria-hidden="true" />
                  )}
                  {cta.label}
                  <ArrowRight size={16} />
                </Link>
              ),
            )}
          </div>
        </div>
      </section>

      <section className="px-5 py-16 sm:px-8">
        <div className="mx-auto max-w-7xl">
          <div className="grid gap-10 lg:grid-cols-[1fr_0.45fr]">
            <div className="space-y-10">
              <div className="space-y-5 text-base leading-7">{content.body}</div>

              <div className="rounded-lg border border-[#181a20]/10 bg-white p-5">
                <h3 className="font-heading text-lg font-semibold text-[#181a20]">Relevant files</h3>
                <DataRoomFileList files={content.files} />
              </div>

              {(topic === "provider-readiness" || topic === "external-action") && (
                <div className="rounded-lg border border-[#181a20]/10 bg-white p-5">
                  <h3 className="font-heading text-lg font-semibold text-[#181a20]">Current promotion boundary</h3>
                  <div className="mt-4 grid gap-3 sm:grid-cols-2">
                    <BoundaryItem label="Provider green" value={dashboard.providerGreen ? "Yes" : "No"} />
                    <BoundaryItem label="Provider gate status" value={dashboard.promotion.providerGateStatus} />
                    <BoundaryItem label="External action status" value={dashboard.demand.external_action_status} />
                    <BoundaryItem label="Acted receipt status" value={dashboard.promotion.actedReceiptStatus} />
                  </div>
                </div>
              )}
            </div>

            <aside className="space-y-8">
              {relevantGates.length > 0 && (
                <div className="rounded-lg border border-[#181a20]/10 bg-white p-5">
                  <h3 className="font-heading text-lg font-semibold text-[#181a20]">Truth gates</h3>
                  <p className="mt-2 text-sm leading-6 text-[#4e5060]">
                    Live status from the latest run for gates related to this diligence topic.
                  </p>
                  <div className="mt-5 space-y-4">
                    {relevantGates.map((gate) => (
                      <TruthGate key={gate.name} gate={gate} />
                    ))}
                  </div>
                </div>
              )}

              <div className="rounded-lg border border-[#181a20]/10 bg-white p-5">
                <h3 className="font-heading text-lg font-semibold text-[#181a20]">Other diligence topics</h3>
                <ul className="mt-4 space-y-2">
                  {TOPICS.filter((t) => t !== topic).map((t) => (
                    <li key={t}>
                      <Link
                        href={`/livelihood-loom/diligence/${t}`}
                        className="flex items-center justify-between rounded-lg border border-[#181a20]/10 px-4 py-3 text-sm font-semibold text-[#181a20] transition hover:bg-[#f4f1ea]"
                      >
                        {topicLabel(t)}
                        <ArrowRight size={14} />
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>

              <div className="rounded-lg bg-[#181a20] p-5 text-white">
                <h3 className="font-heading text-lg font-semibold">Diligence standard</h3>
                <p className="mt-3 text-sm leading-6 text-white/68">
                  Claims on these pages are tied to local report files and explicit gates. We do not
                  state provider-green status, sent outreach, formed partnerships, or generated
                  revenue unless the corresponding gate and acted receipt support it.
                </p>
              </div>
            </aside>
          </div>
        </div>
      </section>
    </PublicShell>
  );
}

function BoundaryItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-[#181a20]/10 bg-[#f9f7f1] p-3">
      <p className="text-xs font-semibold uppercase text-[#60736b]">{label}</p>
      <p className="mt-1 text-sm font-semibold text-[#181a20]">{value}</p>
    </div>
  );
}
