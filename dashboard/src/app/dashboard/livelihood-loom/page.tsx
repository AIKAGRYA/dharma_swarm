import {
  BadgeCheck,
  FileText,
  Handshake,
  ShieldAlert,
  ShieldCheck,
  Target,
} from "lucide-react";
import { loadLivelihoodLoomDashboard } from "@/lib/livelihoodLoom";
import { colors } from "@/lib/theme";

function StatusPill({ label, tone }: { label: string; tone: "ok" | "warn" | "error" | "info" }) {
  const color = {
    ok: colors.rokusho,
    warn: colors.kinpaku,
    error: colors.bengara,
    info: colors.aozora,
  }[tone];
  return (
    <span
      className="inline-flex items-center rounded-lg border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em]"
      style={{
        borderColor: `color-mix(in srgb, ${color} 34%, transparent)`,
        backgroundColor: `color-mix(in srgb, ${color} 10%, transparent)`,
        color,
      }}
    >
      {label}
    </span>
  );
}

function Metric({ label, value, detail }: { label: string; value: string | number; detail: string }) {
  return (
    <div className="min-w-0 rounded-lg border border-sumi-700/40 bg-sumi-900/50 px-4 py-3">
      <div className="font-mono text-xl font-semibold text-torinoko">{value}</div>
      <div className="mt-1 text-[10px] uppercase tracking-[0.12em] text-sumi-600">{label}</div>
      <div className="mt-2 break-words text-xs leading-5 text-sumi-600">{detail}</div>
    </div>
  );
}

export default function LivelihoodLoomPage() {
  const data = loadLivelihoodLoomDashboard();
  const providerTone = data.providerGreen ? "ok" : "error";
  const outreachTone = data.promotion.outreachStatus === "risk_reviewed" ? "warn" : "info";

  return (
    <main className="space-y-6">
      <section className="glass-panel p-5">
        <div className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
          <div className="space-y-3">
            <div className="flex items-center gap-3">
              <div className="flex h-11 w-11 items-center justify-center rounded-lg border border-rokusho/30 bg-rokusho/10 text-rokusho">
                <Handshake size={22} />
              </div>
              <div>
                <h1 className="font-heading text-2xl font-bold tracking-tight text-rokusho">
                  Livelihood Loom
                </h1>
                <p className="mt-1 max-w-3xl text-sm leading-6 text-sumi-600">
                  Sponsor-readiness desk for public-source informal-economy enablement.
                </p>
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <StatusPill label={data.status} tone="warn" />
              <StatusPill label={`provider ${data.providerStatus}`} tone={providerTone} />
              <StatusPill label={`outreach ${data.promotion.outreachStatus}`} tone={outreachTone} />
              <StatusPill label="internal only" tone="info" />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Metric label="Top List" value={data.topCount} detail={`${data.candidateCount} source rows`} />
            <Metric label="Wedges" value={data.wedges.length} detail="ROI-ranked sponsor lanes" />
            <Metric label="Packets" value={data.packets.packet_count} detail="Enablement packets" />
            <Metric label="Blocked" value={data.safety.blocked} detail="Safety exclusions" />
          </div>
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-[1.15fr_0.85fr]">
        <div className="glass-panel p-5">
          <div className="mb-4 flex items-center justify-between gap-4">
            <div className="flex items-center gap-2">
              <Target size={18} className="text-kinpaku" />
              <h2 className="font-heading text-lg font-semibold text-torinoko">ROI Wedges</h2>
            </div>
            <StatusPill label="3 selected" tone="ok" />
          </div>
          <div className="grid gap-3 lg:grid-cols-3">
            {data.wedges.map((wedge) => (
              <article key={wedge.wedge_id} className="rounded-lg border border-sumi-700/35 bg-sumi-900/45 p-4">
                <div className="mb-3 flex items-center justify-between gap-2">
                  <span className="font-mono text-xs text-sumi-600">0{wedge.rank}</span>
                  <span className="font-mono text-xs text-kinpaku">{wedge.roi_score.toFixed(3)}</span>
                </div>
                <h3 className="font-heading text-sm font-semibold text-torinoko">{wedge.label}</h3>
                <p className="mt-2 text-xs leading-5 text-sumi-600">{wedge.roi_thesis}</p>
                <div className="mt-3 text-[11px] uppercase tracking-[0.12em] text-sumi-600">
                  {wedge.candidate_count_in_top_50} candidates
                </div>
              </article>
            ))}
          </div>
        </div>

        <div className="glass-panel p-5">
          <div className="mb-4 flex items-center gap-2">
            <ShieldCheck size={18} className="text-rokusho" />
            <h2 className="font-heading text-lg font-semibold text-torinoko">Safety Review</h2>
          </div>
          <div className="grid grid-cols-3 gap-3 text-center">
            <Metric label="Allowed" value={data.safety.allowed} detail="No red-team flag" />
            <Metric label="Review" value={data.safety.needs_review} detail="Human review" />
            <Metric label="Blocked" value={data.safety.blocked} detail="Excluded" />
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            {Object.entries(data.safety.flag_counts).map(([flag, count]) => (
              <span
                key={flag}
                className="rounded-lg border border-sumi-700/35 bg-sumi-900/45 px-2.5 py-1.5 text-xs text-sumi-600"
              >
                {flag}: {count}
              </span>
            ))}
          </div>
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-[0.9fr_1.1fr]">
        <div className="glass-panel p-5">
          <div className="mb-4 flex items-center gap-2">
            <FileText size={18} className="text-botan" />
            <h2 className="font-heading text-lg font-semibold text-torinoko">Sponsor Desk</h2>
          </div>
          <div className="space-y-3 text-sm leading-6 text-sumi-600">
            <div className="rounded-lg border border-sumi-700/35 bg-sumi-900/45 p-4">
              <div className="text-[10px] uppercase tracking-[0.12em] text-sumi-600">First target</div>
              <div className="mt-1 font-heading text-lg text-torinoko">{data.promotion.sponsorTarget}</div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Metric label="Offer" value={data.demand.draft_only ? "draft" : "live"} detail="First paid offer draft" />
              <Metric label="Briefs" value={data.demand.sponsor_briefs.length} detail="Sponsor draft set" />
            </div>
            <div className="rounded-lg border border-kinpaku/25 bg-kinpaku/10 p-4 text-kinpaku">
              External acted receipt: {data.promotion.actedReceiptStatus}
            </div>
          </div>
        </div>

        <div className="glass-panel p-5">
          <div className="mb-4 flex items-center gap-2">
            <BadgeCheck size={18} className="text-aozora" />
            <h2 className="font-heading text-lg font-semibold text-torinoko">Top Candidates</h2>
          </div>
          <div className="overflow-hidden rounded-lg border border-sumi-700/35">
            <table className="w-full text-left text-sm">
              <thead className="bg-sumi-900/70 text-[10px] uppercase tracking-[0.12em] text-sumi-600">
                <tr>
                  <th className="px-3 py-2">Rank</th>
                  <th className="px-3 py-2">Candidate</th>
                  <th className="px-3 py-2">Country</th>
                  <th className="px-3 py-2">Score</th>
                  <th className="px-3 py-2">Safety</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-sumi-700/35">
                {data.topCandidates.map((candidate) => (
                  <tr key={candidate.name} className="bg-sumi-900/35">
                    <td className="px-3 py-2 font-mono text-xs text-sumi-600">{candidate.rank}</td>
                    <td className="px-3 py-2 text-torinoko">{candidate.name}</td>
                    <td className="px-3 py-2 text-sumi-600">{candidate.country || "unknown"}</td>
                    <td className="px-3 py-2 font-mono text-xs text-kinpaku">
                      {candidate.prioritization_score.toFixed(3)}
                    </td>
                    <td className="px-3 py-2 text-sumi-600">{candidate.safety_status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <section className="glass-panel p-5">
        <div className="mb-4 flex items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <ShieldAlert size={18} className="text-bengara" />
            <h2 className="font-heading text-lg font-semibold text-torinoko">Gates</h2>
          </div>
          <StatusPill label={data.receiptId || "no receipt"} tone="info" />
        </div>
        <div className="grid gap-3 md:grid-cols-3">
          <Metric label="Provider" value={data.providerStatus} detail="ProviderProof remains incomplete" />
          <Metric label="Outreach" value={data.promotion.outreachStatus} detail="Drafted and risk-reviewed only" />
          <Metric label="Publication" value={data.demand.sent ? "sent" : "not sent"} detail="Human approval required" />
        </div>
        <div className="mt-4 grid gap-2 md:grid-cols-2">
          {Object.entries(data.files).map(([name, file]) => (
            <div key={name} className="rounded-lg border border-sumi-700/30 bg-sumi-900/35 px-3 py-2">
              <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-sumi-600">{name}</span>
              <div className="mt-1 break-words font-mono text-[11px] leading-4 text-torinoko/80">{file}</div>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}
