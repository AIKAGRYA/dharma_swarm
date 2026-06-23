"use client";

import type { CoherenceCard, OperatorCoherenceReport } from "@/lib/operatorCoherence";
import { CoherenceCardView } from "./CoherenceCardView";

function asString(value: unknown): string {
  if (value == null || value === "") return "—";
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return JSON.stringify(value);
}

function CardList({ cards, empty }: { cards: CoherenceCard[]; empty: string }) {
  if (!cards.length) {
    return <div className="rounded border border-dashed border-sumi-800/70 p-3 text-xs text-sumi-600">{empty}</div>;
  }
  return (
    <div className="grid gap-2 lg:grid-cols-2">
      {cards.slice(0, 8).map((card) => (
        <CoherenceCardView key={card.id} card={card} />
      ))}
    </div>
  );
}

export function TrackPortfolioSection({ report }: { report: OperatorCoherenceReport }) {
  const tracks = report.track_portfolio.tracks ?? [];
  return (
    <section className="rounded-xl border border-sumi-800/60 bg-sumi-950/50 p-4">
      <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-sumi-500">
        Track Portfolio
      </div>
      <h2 className="mt-1 text-lg font-semibold text-torinoko">
        {report.track_portfolio.active_count} active · {report.track_portfolio.closed_count} closed/archived ·{" "}
        {report.track_portfolio.proposed_tracks?.length ?? 0} proposed
      </h2>
      <div className="mt-4 overflow-x-auto">
        <table className="min-w-full text-left text-xs">
          <thead className="text-[10px] uppercase tracking-[0.12em] text-sumi-500">
            <tr>
              <th className="px-2 py-2">Track</th>
              <th className="px-2 py-2">Lifecycle</th>
              <th className="px-2 py-2">Readiness</th>
              <th className="px-2 py-2">Evidence</th>
              <th className="px-2 py-2">Owned surfaces</th>
            </tr>
          </thead>
          <tbody>
            {tracks.map((track, index) => (
              <tr key={asString(track.id) || index} className="border-t border-sumi-800/40">
                <td className="max-w-[260px] px-2 py-2 font-medium text-sumi-200">{asString(track.name)}</td>
                <td className="px-2 py-2 text-sumi-400">{asString(track.lifecycle)} / {asString(track.status)}</td>
                <td className="px-2 py-2 text-sumi-300">{asString(track.readiness)}%</td>
                <td className="px-2 py-2 text-sumi-400">{track.evidence_present ? "present" : "missing"} · verified {asString(track.verified_at)}</td>
                <td className="max-w-[360px] truncate px-2 py-2 text-sumi-500">{asString(track.owned_surfaces)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export function RealityRadarSection({ report }: { report: OperatorCoherenceReport }) {
  return (
    <section className="rounded-xl border border-sumi-800/60 bg-sumi-950/50 p-4">
      <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-sumi-500">
        Rogue Work Radar
      </div>
      <h2 className="mt-1 text-lg font-semibold text-torinoko">
        {report.rogue_work_radar.dirty_worktree_count} dirty worktrees ·{" "}
        {report.rogue_work_radar.local_only_count} local-only/ahead ·{" "}
        {report.rogue_work_radar.stash_count} stashes
      </h2>
      <div className="mt-2 text-xs text-sumi-400">
        Branch census: {report.branch_census?.total ?? 0} local branches ·{" "}
        {report.rogue_work_radar.local_only_branch_count ?? 0} local-only ·{" "}
        {report.rogue_work_radar.unpushed_branch_count ?? 0} unpushed-ahead ·{" "}
        {report.rogue_work_radar.orphaned_branch_count ?? 0} orphaned (upstream gone)
      </div>
      <div className="mt-4">
        <CardList cards={report.rogue_work_radar.cards} empty="No rogue/dirty cards emitted." />
      </div>
    </section>
  );
}

export function CensusSurfaceLedgerSections({ report }: { report: OperatorCoherenceReport }) {
  const tmux = report.agent_terminal_census.tmux_sessions ?? [];
  const launchd = report.agent_terminal_census.launchd_jobs ?? [];
  const processes = report.agent_terminal_census.processes ?? [];
  const surfaces = report.operator_surfaces.surfaces ?? [];
  const preservation = (report.preservation_ledger.local_preservation ?? []) as Record<string, unknown>[];
  const prs = (report.pr_ci_triage.prs ?? []) as Record<string, unknown>[];
  const liveOps = report.live_ops ?? {};
  const liveOpsSurfaces = (liveOps.surfaces ?? []) as Record<string, unknown>[];
  const liveOpsStatus = (liveOps.summary?.by_status ?? {}) as Record<string, number>;
  const onboarding = report.onboarding ?? {};
  const runtimeReceipts = report.runtime_receipts ?? {};
  const runtimeDbs = (runtimeReceipts.runtime_dbs ?? []) as Record<string, unknown>[];

  return (
    <div className="grid gap-3 xl:grid-cols-2">
      <section className="rounded-xl border border-sumi-800/60 bg-sumi-950/50 p-4">
        <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-sumi-500">
          Agent / Terminal Census
        </div>
        <h2 className="mt-1 text-lg font-semibold text-torinoko">
          {tmux.length} tmux · {launchd.length} launchd · {processes.length} process hints
        </h2>
        <div className="mt-3 space-y-2 text-xs text-sumi-400">
          {[...tmux.slice(0, 4), ...launchd.slice(0, 4)].map((item, index) => (
            <div key={`${asString(item.name ?? item.label)}-${index}`} className="rounded border border-sumi-800/50 bg-sumi-900/30 p-2">
              <span className="font-semibold text-sumi-200">{asString(item.name ?? item.label)}</span>
              <span className="text-sumi-500"> · owner track {asString(item.track)}</span>
            </div>
          ))}
          {!tmux.length && !launchd.length ? <div className="text-sumi-600">No live terminal/process owner rows, or probes disabled/unavailable.</div> : null}
        </div>
      </section>

      <section className="rounded-xl border border-sumi-800/60 bg-sumi-950/50 p-4">
        <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-sumi-500">
          Live Ops Liveness
        </div>
        <h2 className="mt-1 text-lg font-semibold text-torinoko">
          {liveOps.enabled
            ? `${liveOpsStatus.live ?? 0} live · ${liveOpsStatus.stale ?? 0} stale · ${liveOpsStatus.blocked ?? 0} blocked · ${liveOpsStatus.stopped ?? 0} stopped`
            : `Unavailable: ${asString(liveOps.reason)}`}
        </h2>
        <div className="mt-1 text-[10px] text-sumi-600">
          Source: scripts/runtime/live_ops_census.py (canonical liveness owner)
        </div>
        <div className="mt-3 space-y-2 text-xs">
          {liveOpsSurfaces.slice(0, 6).map((surface, index) => (
            <div key={`${asString(surface.id)}-${index}`} className="rounded border border-sumi-800/50 bg-sumi-900/30 p-2">
              <div className="font-semibold text-sumi-200">{asString(surface.label ?? surface.id)}</div>
              <div className="text-sumi-500">
                status {asString(surface.status)} · desired {asString(surface.desired_state)} · age {asString(surface.age_hours)}h
              </div>
            </div>
          ))}
          {!liveOpsSurfaces.length ? <div className="text-sumi-600">No live-ops surfaces in this projection.</div> : null}
        </div>
      </section>

      <section className="rounded-xl border border-sumi-800/60 bg-sumi-950/50 p-4">
        <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-sumi-500">
          Operator Surfaces
        </div>
        <h2 className="mt-1 text-lg font-semibold text-torinoko">
          Dashboard, terminal, cockpit, A2A, live ops, routing
        </h2>
        <div className="mt-3 grid gap-2 md:grid-cols-2">
          {surfaces.map((surface) => (
            <div key={asString(surface.id)} className="rounded border border-sumi-800/50 bg-sumi-900/30 p-2 text-xs">
              <div className="font-semibold text-sumi-200">{asString(surface.label)}</div>
              <div className="text-sumi-500">
                {asString(surface.status)} · proof age {asString(surface.proof_age_hours)}h
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="rounded-xl border border-sumi-800/60 bg-sumi-950/50 p-4">
        <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-sumi-500">
          Onboarding + Runtime Receipts
        </div>
        <h2 className="mt-1 text-lg font-semibold text-torinoko">
          make onboard {asString(onboarding.status)} · {asString(runtimeReceipts.receipt_count)} receipt files
        </h2>
        <div className="mt-3 space-y-2 text-xs">
          <div className="rounded border border-sumi-800/50 bg-sumi-900/30 p-2">
            <div className="font-semibold text-sumi-200">Onboarding door</div>
            <div className="text-sumi-500">{asString(onboarding.target)}</div>
          </div>
          {runtimeDbs.slice(0, 4).map((db) => (
            <div key={asString(db.path)} className="rounded border border-sumi-800/50 bg-sumi-900/30 p-2">
              <div className="font-semibold text-sumi-200">{asString(db.path)}</div>
              <div className="text-sumi-500">
                exists={asString(db.exists)} · readable={asString(db.readable)} · age={asString(db.age_hours)}h
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="rounded-xl border border-sumi-800/60 bg-sumi-950/50 p-4">
        <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-sumi-500">
          Preservation Ledger
        </div>
        <h2 className="mt-1 text-lg font-semibold text-torinoko">
          Safe locally vs off-machine risk
        </h2>
        <div className="mt-3 space-y-2 text-xs">
          {preservation.map((entry) => (
            <div key={asString(entry.path)} className="rounded border border-sumi-800/50 bg-sumi-900/30 p-2">
              <div className="font-semibold text-sumi-200">{asString(entry.path)}</div>
              <div className="text-sumi-500">
                exists={asString(entry.exists)} · files={asString(entry.file_count)} · latest age={asString(entry.latest_age_hours)}h
              </div>
            </div>
          ))}
          <div className="text-sumi-500">
            At-risk worktrees: {asString(report.preservation_ledger.at_risk_worktree_count)}
          </div>
        </div>
      </section>

      <section className="rounded-xl border border-sumi-800/60 bg-sumi-950/50 p-4">
        <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-sumi-500">
          PR / CI Triage
        </div>
        <h2 className="mt-1 text-lg font-semibold text-torinoko">
          {report.pr_ci_triage.enabled ? `${prs.length} PRs` : `Unavailable: ${asString(report.pr_ci_triage.reason)}`}
        </h2>
        <div className="mt-3 space-y-2 text-xs">
          {prs.slice(0, 6).map((pr) => (
            <div key={asString(pr.number)} className="rounded border border-sumi-800/50 bg-sumi-900/30 p-2">
              <div className="font-semibold text-sumi-200">#{asString(pr.number)} {asString(pr.title)}</div>
              <div className="text-sumi-500">branch {asString(pr.headRefName)} · updated {asString(pr.updatedAt)}</div>
            </div>
          ))}
          {!prs.length ? <div className="text-sumi-600">No PR rows in this projection.</div> : null}
        </div>
      </section>
    </div>
  );
}

export function QuickAnswersSection({ report }: { report: OperatorCoherenceReport }) {
  const buckets = [
    ["what_is_safe", "What is safe?"],
    ["what_is_dirty", "What is dirty?"],
    ["what_is_abandoned", "What is abandoned?"],
    ["what_is_live", "What is live?"],
    ["what_is_blocked", "What is blocked?"],
    ["what_might_be_rogue", "What might be rogue?"],
  ] as const;
  return (
    <section className="rounded-xl border border-sumi-800/60 bg-sumi-950/50 p-4">
      <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-sumi-500">
        Under-60-second answers
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {buckets.map(([key, label]) => {
          const cards = (report.definition_answers[key] ?? []) as CoherenceCard[];
          return (
            <div key={key} className="rounded-lg border border-sumi-800/50 bg-sumi-900/25 p-3">
              <h3 className="text-sm font-semibold text-torinoko">{label}</h3>
              <div className="mt-2 space-y-1.5">
                {cards.slice(0, 4).map((card) => (
                  <div key={card.id} className="text-xs text-sumi-400">
                    <span className="font-semibold text-sumi-200">{card.risk}</span> — {card.title}
                  </div>
                ))}
                {!cards.length ? <div className="text-xs text-sumi-600">No cards.</div> : null}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

export function SourceErrorSection({ report }: { report: OperatorCoherenceReport }) {
  return (
    <section className="rounded-xl border border-sumi-800/60 bg-sumi-950/50 p-4">
      <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-sumi-500">
        Uncertainty / Source Errors
      </div>
      <div className="mt-3 space-y-2">
        {report.source_errors.map((error) => (
          <div key={`${error.source}-${error.error}`} className="rounded border border-kinpaku/30 bg-kinpaku/5 p-2 text-xs text-kinpaku">
            {error.source}: {error.error}
          </div>
        ))}
        {!report.source_errors.length ? (
          <div className="text-xs text-sumi-600">No source errors captured.</div>
        ) : null}
      </div>
    </section>
  );
}
