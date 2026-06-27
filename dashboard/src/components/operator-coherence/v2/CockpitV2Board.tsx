"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  BookOpen,
  ClipboardList,
  Layers3,
  RefreshCw,
  ShieldAlert,
} from "lucide-react";
import type { OperatorCoherenceReport } from "@/lib/operatorCoherence";
import {
  actionPacketToInspect,
  asText,
  buildActionPackets,
  buildAuthorityInspect,
  buildLaneAdmissionInspect,
  buildReportSourceSummary,
  buildTopPanels,
  buildAnswerRibbon,
  buildEventTape,
  buildUncertainty,
  DESIGN_SOURCES,
  filterCards,
  formatCount,
  freshnessLabel,
  humanRisk,
  LANE_ADMISSION_FIELDS,
  MODES,
  sourceToInspect,
  tapeEventInspect,
  uncertaintyInspect,
  type AnswerDatum,
  type CockpitMode,
  type InspectItem,
  type TapeEvent,
  type UncertaintyDatum,
} from "./cockpitV2Model";
import {
  V2CardRow,
  V2Drawer,
  V2FilterBar,
  V2Panel,
  V2Section,
  toneClass,
} from "./CockpitV2Primitives";
import { CockpitTopology, RecursiveMandala } from "./CockpitV2Topology";

export function CockpitV2Board({
  report,
  isLoading,
  onRefresh,
}: {
  report: OperatorCoherenceReport;
  isLoading: boolean;
  onRefresh: () => void;
}) {
  const [mode, setMode] = useState<CockpitMode>("overview");
  const [query, setQuery] = useState("");
  const [inspect, setInspect] = useState<InspectItem | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const searchRef = useRef<HTMLInputElement>(null);

  const panels = useMemo(() => buildTopPanels(report), [report]);
  const answers = useMemo(() => buildAnswerRibbon(report), [report]);
  const actionPackets = useMemo(() => buildActionPackets(report), [report]);
  const uncertainty = useMemo(() => buildUncertainty(report), [report]);
  const tape = useMemo(() => buildEventTape(report), [report]);
  const filteredCards = useMemo(() => filterCards(report.cards, mode, query), [mode, query, report.cards]);
  const repairCards = useMemo(
    () => report.cards.filter((card) => card.lane === "Needs Repair" || card.lane === "Needs Decision"),
    [report.cards],
  );
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (event.key !== "/" || target?.tagName === "INPUT" || target?.tagName === "TEXTAREA" || target?.isContentEditable) return;
      event.preventDefault();
      searchRef.current?.focus();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  // Selection is preserved across modes (REQ-032): selectedId persists even
  // when the user switches Linear ↔ Topology ↔ Recursive. The topology and
  // mandala both write selectedId via onSelect, so the highlighted object is
  // retained when the mode changes.
  const inspectItem = (item: InspectItem) => {
    setInspect(item);
    if (item.id) setSelectedId(item.id);
  };
  return (
    <div className="min-h-[calc(100vh-8rem)] space-y-3 overflow-x-hidden text-torinoko">
      <V2Hero report={report} isLoading={isLoading} onRefresh={onRefresh} onInspect={inspectItem} />

      <UncertaintyStrip items={uncertainty} onInspect={inspectItem} />

      <AnswerRibbon answers={answers} onInspect={inspectItem} onFilter={(status) => { setQuery(status); setMode("evidence"); }} />

      <V2FilterBar modes={MODES} activeMode={mode} query={query} onMode={setMode} onQuery={setQuery} inputRef={searchRef} />

      <div className="grid gap-3 xl:grid-cols-6">
        {panels.map((panel) => (
          <V2Panel key={panel.id} panel={panel} onInspect={inspectItem} />
        ))}
      </div>

      {mode === "overview" ? (
        <OverviewMode
          report={report}
          repairCards={repairCards}
          actionPackets={actionPackets}
          onMode={setMode}
          onInspect={inspectItem}
        />
      ) : mode === "topology" ? (
        <CockpitTopology report={report} selectedId={selectedId} filterText={query} onInspect={inspectItem} onSelect={setSelectedId} />
      ) : mode === "recursive" ? (
        <RecursiveMandala report={report} selectedId={selectedId} filterText={query} onInspect={inspectItem} onSelect={setSelectedId} />
      ) : mode === "errors" ? (
        <ErrorsMode report={report} items={uncertainty} onInspect={inspectItem} />
      ) : mode === "design" ? (
        <DesignMode onInspect={inspectItem} />
      ) : mode === "tracks" ? (
        <TracksMode report={report} onInspect={inspectItem} />
      ) : mode === "runtime" ? (
        <RuntimeMode report={report} cards={filteredCards} onInspect={inspectItem} />
      ) : mode === "git" ? (
        <GitMode report={report} cards={filteredCards} onInspect={inspectItem} />
      ) : mode === "preservation" ? (
        <PreservationMode report={report} cards={filteredCards} onInspect={inspectItem} />
      ) : (
        <CardTableMode title={mode === "triage" ? "Triage queue" : "Evidence table"} cards={filteredCards} onInspect={inspectItem} />
      )}

      <ReceiptEventTape events={tape} onInspect={inspectItem} />

      <div className="rounded-md border border-sumi-800/60 bg-sumi-950/50 px-3 py-2 text-[10px] text-sumi-600">
        Data: `/api/operator-coherence/report` · receipts: `reports/governance/operator_coherence_cockpit.*` · design manifest: `docs/design/COCKPIT_V2_DESKTOP_SOURCE_MANIFEST.md`
      </div>

      <V2Drawer item={inspect} onClose={() => { setInspect(null); setSelectedId(null); }} />
    </div>
  );
}

function UncertaintyStrip({ items, onInspect }: { items: UncertaintyDatum[]; onInspect: (item: InspectItem) => void }) {
  // REQ-006 / core goal: source errors + missing evidence must be impossible to
  // miss. This is a full-width banner directly under the hero, never hidden.
  if (!items.length) {
    return (
      <div className="flex items-center gap-2 rounded-md border border-rokusho/35 bg-rokusho/8 px-3 py-2 text-xs text-rokusho">
        <ShieldAlert size={14} /> All probed sources responded. No source errors or unavailable systems in this snapshot.
      </div>
    );
  }
  return (
    <div className="rounded-md border border-bengara/50 bg-bengara/12 p-2.5">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <span className="inline-flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.16em] text-bengara">
          <ShieldAlert size={14} /> {items.length} source{items.length === 1 ? "" : "s"} uncertain — absence is NOT success
        </span>
        <span className="text-[10px] text-sumi-400">gh / tmux / launchctl / ps / gcx unavailability is shown, never hidden</span>
      </div>
      <div className="flex flex-wrap gap-2">
        {items.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => onInspect(uncertaintyInspect(item))}
            className="group flex min-w-[180px] flex-1 items-start gap-2 rounded-md border border-bengara/35 bg-sumi-950/40 px-2.5 py-2 text-left hover:border-bengara/70"
          >
            <span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-bengara" />
            <span className="min-w-0">
              <span className="block truncate font-mono text-[11px] font-semibold text-torinoko">{item.label}</span>
              <span className="mt-0.5 block line-clamp-2 text-[10px] leading-4 text-sumi-400">{item.detail}</span>
              <span className="mt-1 inline-block rounded border border-bengara/40 px-1 py-0.5 text-[8px] uppercase tracking-[0.12em] text-bengara">
                {item.state}
              </span>
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}

function AnswerRibbon({
  answers,
  onInspect,
  onFilter,
}: {
  answers: AnswerDatum[];
  onInspect: (item: InspectItem) => void;
  onFilter: (status: string) => void;
}) {
  // Spec 11.3 / REQ-013/014 — under-60-second answers, one per question.
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 xl:grid-cols-8">
      {answers.map((answer) => (
        <button
          key={answer.key}
          type="button"
          onClick={() => {
            onInspect(answer.inspect);
            if (answer.filterStatus) onFilter(answer.filterStatus);
          }}
          title={answer.topEvidence}
          className={`rounded-md border bg-sumi-950/40 p-2.5 text-left transition hover:-translate-y-0.5 hover:bg-sumi-900/60 ${toneClass(answer.tone)}`}
        >
          <div className="text-[9px] font-semibold uppercase tracking-[0.14em] opacity-75">{answer.label}</div>
          <div className="mt-1 font-mono text-2xl font-semibold leading-none tabular-nums text-torinoko">{answer.value}</div>
          <div className="mt-1.5 line-clamp-2 text-[10px] leading-4 text-sumi-400">{answer.topEvidence}</div>
        </button>
      ))}
    </div>
  );
}

function ReceiptEventTape({ events, onInspect }: { events: TapeEvent[]; onInspect: (item: InspectItem) => void }) {
  // Spec 11.9 / REQ-060: snapshot tape; history honestly labeled "not yet wired".
  return (
    <section className="rounded-md border border-sumi-800/60 bg-sumi-950/45 p-3">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-sumi-600">event tape · receipts + probes</div>
        <span className="rounded border border-sumi-800/70 bg-sumi-900/40 px-1.5 py-0.5 text-[9px] uppercase tracking-[0.12em] text-sumi-500">
          history not yet wired · single snapshot
        </span>
      </div>
      <div className="flex gap-2 overflow-x-auto pb-1">
        {events.map((event) => (
          <button
            key={event.id}
            type="button"
            onClick={() => onInspect(tapeEventInspect(event))}
            className={`flex min-w-[190px] shrink-0 flex-col gap-1 rounded-md border bg-sumi-950/40 px-2.5 py-2 text-left hover:bg-sumi-900/60 ${toneClass(event.tone)}`}
          >
            <span className="truncate font-mono text-[11px] font-semibold text-torinoko">{event.label}</span>
            <span className="line-clamp-2 text-[10px] leading-4 text-sumi-400">{event.detail}</span>
            <span className="text-[8px] uppercase tracking-[0.12em] opacity-70">{event.kind} · {freshnessLabel(event.freshness)}</span>
          </button>
        ))}
      </div>
    </section>
  );
}

function ErrorsMode({
  report,
  items,
  onInspect,
}: {
  report: OperatorCoherenceReport;
  items: UncertaintyDatum[];
  onInspect: (item: InspectItem) => void;
}) {
  const prCi = report.pr_ci_triage as { enabled?: boolean; reason?: string } | undefined;
  return (
    <div className="grid gap-3 xl:grid-cols-2">
      <V2Section title="Unavailable / uncertain sources" eyebrow="REQ-006 / REQ-052 / REQ-070 / REQ-072">
        <div className="space-y-2">
          {items.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => onInspect(uncertaintyInspect(item))}
              className="grid w-full grid-cols-[minmax(0,1fr)_92px] gap-2 rounded-md border border-bengara/35 bg-sumi-950/35 p-3 text-left text-xs hover:border-bengara/70"
            >
              <div className="min-w-0">
                <div className="truncate font-mono font-semibold text-torinoko">{item.label}</div>
                <div className="mt-1 line-clamp-2 text-sumi-400">{item.detail}</div>
              </div>
              <div className="self-center rounded border border-bengara/40 px-2 py-1 text-center text-[10px] font-semibold uppercase tracking-[0.12em] text-bengara">
                {item.state}
              </div>
            </button>
          ))}
        </div>
      </V2Section>
      <div className="space-y-3">
        <V2Section title="PR / CI triage" eyebrow="gh auth required">
          {prCi?.enabled === false ? (
            <div className="rounded-md border border-bengara/35 bg-bengara/8 p-3 text-xs text-sumi-300">
              <div className="font-semibold text-bengara">Unavailable</div>
              <div className="mt-1">{prCi.reason ?? "gh auth unavailable; PR/CI triage omitted."}</div>
              <div className="mt-2 text-sumi-500">Open PRs, CI state, blocked checks, and merge risk appear here once `gh auth` is restored. Until then this is uncertainty, not a clean state.</div>
            </div>
          ) : (
            <div className="text-xs text-sumi-400">PR/CI data present in report.</div>
          )}
        </V2Section>
        <V2Section title="Grafana / gcx integration" eyebrow="spec 11.10 — no fake telemetry">
          <div className="rounded-md border border-sumi-800/55 bg-sumi-950/35 p-3 text-xs text-sumi-300">
            <div className="font-semibold text-sumi-200">Unconfigured</div>
            <div className="mt-1 text-sumi-400">
              gcx context is not wired into the operator-coherence report. Datasources, dashboards, SLOs, and alerts are shown as unavailable until configured. No external telemetry is invented.
            </div>
            <div className="mt-2 font-mono text-[10px] text-sumi-600">next: configure Grafana Cloud context → discover datasources → render real sources only</div>
          </div>
        </V2Section>
      </div>
    </div>
  );
}

function V2Hero({
  report,
  isLoading,
  onRefresh,
  onInspect,
}: {
  report: OperatorCoherenceReport;
  isLoading: boolean;
  onRefresh: () => void;
  onInspect: (item: InspectItem) => void;
}) {
  const sourceErrorCount = report.source_errors.length;
  const source = buildReportSourceSummary(report);
  const status = report.readiness.score >= 70 ? "STABLE" : report.readiness.score >= 40 ? "MIXED" : "DEGRADED";
  const authorityInspect = buildAuthorityInspect(report);
  const candidateBranch = report.git?.main?.branch ?? "unknown";
  const localMax = (report.track_portfolio as { policy?: { max_active?: unknown } }).policy?.max_active;
  return (
    <header className="rounded-md border border-sumi-800/60 bg-[linear-gradient(135deg,rgba(20,27,46,0.92),rgba(10,14,26,0.96))] p-4">
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_420px]">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.2em] text-aozora">
            <Layers3 size={13} /> Mandala Mission Control · Linear Board Mode
          </div>
          <div className="mt-3 flex flex-wrap items-end gap-4">
            <h1 className="font-heading text-4xl font-semibold tracking-tight text-torinoko">Dharma Swarm Operator Observatory</h1>
            <div className="font-mono text-3xl font-semibold text-kinpaku tabular-nums">{status}</div>
          </div>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-sumi-400">
            Grafana-style operator instrument grounded in Desktop canon/prototypes/inspiration. It projects real git, governance, live-ops, receipts, preservation, and dashboard surfaces — never a new source of truth.
          </p>
          <button
            type="button"
            onClick={() => onInspect(authorityInspect)}
            className="mt-4 grid w-full max-w-4xl gap-3 rounded-md border border-bengara/40 bg-bengara/10 p-3 text-left text-xs hover:border-bengara/70 md:grid-cols-[minmax(0,1fr)_minmax(210px,0.45fr)]"
          >
            <div>
              <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-bengara">
                <ShieldAlert size={13} /> Report source / read-only
              </div>
              <div className="mt-1 text-sm font-semibold text-torinoko">
                This observatory is a read-only source projection: {source.label}. Missing or partial evidence is treated as uncertainty.
              </div>
              <div className="mt-1 text-sumi-400">
                Local branch `{candidateBranch}` reports {report.track_portfolio.active_count}/{asText(localMax)} active tracks via `/api/operator-coherence/report`; no canonical baseline is invented in the UI.
              </div>
            </div>
            <div className="rounded border border-bengara/30 bg-sumi-950/35 p-2 font-mono text-[10px] text-sumi-300">
              {source.mode.toUpperCase()}
              <br />
              {source.ageHours == null ? "age unknown" : `${Math.round(source.ageHours)}h old`}
            </div>
          </button>
          <div className="mt-4 flex flex-wrap gap-2 text-xs">
            <button
              type="button"
              onClick={() => onInspect({
                type: "panel",
                title: "Source uncertainty",
                subtitle: `${sourceErrorCount} source errors`,
                status: sourceErrorCount ? "partial" : "clean",
                evidence: report.source_errors.map((error) => ({ kind: "source_error", source: error.source, detail: error.error })),
                raw: report.source_errors,
              })}
              className="rounded-md border border-kinpaku/35 bg-kinpaku/8 px-3 py-2 text-kinpaku hover:bg-kinpaku/15"
            >
              {sourceErrorCount} uncertainty
            </button>
            <button
              type="button"
              onClick={() => onInspect(sourceToInspect(DESIGN_SOURCES[0]))}
              className="rounded-md border border-aozora/35 bg-aozora/8 px-3 py-2 text-aozora hover:bg-aozora/15"
            >
              Design canon
            </button>
          </div>
        </div>
        <div className="rounded-md border border-sumi-700/55 bg-sumi-950/45 p-3">
          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-sumi-600">Generated</div>
              <div className="mt-1 font-mono text-xs text-sumi-300">{report.generated_at}</div>
            </div>
            <button
              type="button"
              onClick={onRefresh}
              disabled={isLoading}
              className="inline-flex items-center gap-2 rounded-md border border-sumi-700/70 bg-sumi-900/70 px-3 py-2 text-xs font-semibold text-sumi-200 hover:border-aozora/60 disabled:opacity-50"
            >
              <RefreshCw size={13} className={isLoading ? "animate-spin" : ""} /> Refresh
            </button>
          </div>
          <div className="mt-4 grid grid-cols-4 gap-2 text-center text-xs">
            <MiniStat label="cards" value={report.cards.length} />
            <MiniStat label="branches" value={report.branch_census?.total ?? 0} />
            <MiniStat label="live" value={report.live_ops?.summary?.by_status?.live ?? 0} />
            <MiniStat label="errors" value={sourceErrorCount} />
          </div>
          <div className={`mt-2 rounded-md border px-2 py-1.5 text-[10px] uppercase tracking-[0.12em] ${toneClass(source.tone)}`}>
            source mode: {source.mode} · {source.detail}
          </div>
        </div>
      </div>
    </header>
  );
}

function MiniStat({ label, value }: { label: string; value: unknown }) {
  return (
    <div className="rounded-md border border-sumi-800/55 bg-sumi-900/35 p-2">
      <div className="font-mono text-lg font-semibold text-torinoko tabular-nums">{formatCount(value)}</div>
      <div className="text-[9px] uppercase tracking-[0.12em] text-sumi-600">{label}</div>
    </div>
  );
}

function OverviewMode({
  report,
  repairCards,
  actionPackets,
  onMode,
  onInspect,
}: {
  report: OperatorCoherenceReport;
  repairCards: typeof report.cards;
  actionPackets: ReturnType<typeof buildActionPackets>;
  onMode: (mode: CockpitMode) => void;
  onInspect: (item: InspectItem) => void;
}) {
  return (
    <div className="grid gap-3 xl:grid-cols-[minmax(0,1.18fr)_minmax(360px,0.82fr)]">
      <div className="space-y-3">
        <V2Section
          title="Next actions"
          eyebrow="operator queue"
          action={<ModeButton label="Open triage" onClick={() => onMode("triage")} />}
        >
          <div className="space-y-2">
            {actionPackets.map((packet) => (
              <button
                type="button"
                key={packet.id}
                onClick={() => onInspect(actionPacketToInspect(packet))}
                className="grid w-full grid-cols-[28px_minmax(0,1fr)_120px] gap-3 rounded-md border border-kinpaku/25 bg-kinpaku/6 p-3 text-left text-sm hover:border-kinpaku/50 max-lg:grid-cols-1"
              >
                <AlertTriangle size={16} className="mt-0.5 text-kinpaku" />
                <div className="min-w-0">
                  <div className="font-semibold text-torinoko">#{packet.rank} · {humanRisk(packet.risk)}</div>
                  <div className="mt-1 line-clamp-2 text-xs text-sumi-400">{packet.why}</div>
                  <div className="mt-1 text-[9px] uppercase tracking-[0.12em] text-kinpaku">proposal only · can act now: no</div>
                </div>
                <div className="self-center text-right text-[10px] uppercase tracking-[0.14em] text-sumi-500 max-lg:text-left">{packet.urgency}</div>
              </button>
            ))}
          </div>
        </V2Section>

        <V2Section title="Source-control radar" eyebrow="git reality" action={<ModeButton label="Open Git" onClick={() => onMode("git")} />}>
          <SourceControlBars report={report} />
        </V2Section>

        <V2Section title="Live-ops liveness" eyebrow="runtime reality" action={<ModeButton label="Open Runtime" onClick={() => onMode("runtime")} />}>
          <LiveOpsBars report={report} />
        </V2Section>

        <V2Section title="Read-only action contract" eyebrow="operator safety">
          <div className="rounded-md border border-kinpaku/30 bg-kinpaku/8 p-3 text-xs leading-5 text-sumi-300">
            Recommendations are proposal packets only. This cockpit does not reset, stash, merge, kill, post, spend, or mutate systems. Future mutation requires an approved action API with blast radius, rollback, evidence, and receipt path.
          </div>
        </V2Section>
      </div>

      <div className="space-y-3">
        <V2Section title="High-signal incidents" eyebrow="click to inspect">
          <div className="space-y-2">
            {repairCards.slice(0, 10).map((card) => <V2CardRow key={card.id} card={card} onInspect={onInspect} />)}
          </div>
        </V2Section>
        <V2Section title="Board provenance" eyebrow="Desktop sources">
          <div className="space-y-2">
            {DESIGN_SOURCES.slice(0, 5).map((source) => (
              <button
                key={source.id}
                type="button"
                onClick={() => onInspect(sourceToInspect(source))}
                className="w-full rounded-md border border-sumi-800/55 bg-sumi-950/35 p-3 text-left hover:border-aozora/45"
              >
                <div className="text-sm font-semibold text-sumi-200">{source.label}</div>
                <div className="mt-1 line-clamp-2 text-xs text-sumi-500">{source.role}</div>
              </button>
            ))}
          </div>
        </V2Section>
        <LaneAdmissionSection onInspect={onInspect} />
      </div>
    </div>
  );
}

function LaneAdmissionSection({ onInspect }: { onInspect: (item: InspectItem) => void }) {
  return (
    <V2Section
      title="Lane admission packet"
      eyebrow="parallel agent lanes"
      action={<ModeButton label="Inspect schema" onClick={() => onInspect(buildLaneAdmissionInspect())} />}
    >
      <button
        type="button"
        onClick={() => onInspect(buildLaneAdmissionInspect())}
        className="w-full rounded-md border border-aozora/30 bg-aozora/8 p-3 text-left hover:border-aozora/55"
      >
        <div className="flex items-center gap-2 text-sm font-semibold text-torinoko">
          <ClipboardList size={15} className="text-aozora" /> Every parallel lane should become a cockpit-visible packet.
        </div>
        <div className="mt-2 text-xs leading-5 text-sumi-400">
          Required contract: lane identity, provider, branch/worktree/base, touched surfaces, dirty count, verification, receipts, conflicts, canonicality, preservation, and promotion recommendation.
        </div>
        <div className="mt-3 flex flex-wrap gap-1">
          {LANE_ADMISSION_FIELDS.slice(0, 10).map((field) => (
            <span key={field} className="rounded border border-sumi-800/70 bg-sumi-950/45 px-1.5 py-0.5 font-mono text-[9px] text-sumi-500">
              {field}
            </span>
          ))}
          <span className="rounded border border-sumi-800/70 bg-sumi-950/45 px-1.5 py-0.5 font-mono text-[9px] text-sumi-500">
            +{LANE_ADMISSION_FIELDS.length - 10}
          </span>
        </div>
      </button>
    </V2Section>
  );
}

function SourceControlBars({ report }: { report: OperatorCoherenceReport }) {
  const metrics = [
    ["Branches", report.branch_census?.total ?? 0, 207],
    ["Local-only", report.branch_census?.local_only ?? 0, report.branch_census?.total ?? 1],
    ["Unpushed", report.branch_census?.unpushed_ahead ?? 0, report.branch_census?.total ?? 1],
    ["Orphaned", report.branch_census?.orphaned_gone ?? 0, report.branch_census?.total ?? 1],
    ["Stashes", report.rogue_work_radar.stash_count, 100],
    ["Dirty worktrees", report.rogue_work_radar.dirty_worktree_count, 12],
  ] as const;
  return <BarList metrics={metrics} dangerAt={0.3} />;
}

function LiveOpsBars({ report }: { report: OperatorCoherenceReport }) {
  const status = report.live_ops?.summary?.by_status ?? {};
  const total = report.live_ops?.summary?.total ?? 1;
  const metrics = [
    ["Live", status.live ?? 0, total],
    ["Stale", status.stale ?? 0, total],
    ["Blocked", status.blocked ?? 0, total],
    ["Stopped", status.stopped ?? 0, total],
    ["Human gates", report.live_ops?.summary?.human_authority_required ?? 0, total],
    ["Proof gaps", report.live_ops?.summary?.proof_gap_surfaces ?? 0, total],
  ] as const;
  return <BarList metrics={metrics} dangerAt={0.12} />;
}

function BarList({ metrics, dangerAt }: { metrics: readonly (readonly [string, number, number])[]; dangerAt: number }) {
  return (
    <div className="space-y-2">
      {metrics.map(([label, value, total]) => {
        const pct = total > 0 ? Math.min(100, Math.round((value / total) * 100)) : 0;
        const danger = label !== "Live" && value / Math.max(1, total) >= dangerAt;
        return (
          <div key={label} className="grid grid-cols-[112px_minmax(0,1fr)_76px] items-center gap-3 text-xs">
            <div className="text-sumi-400">{label}</div>
            <div className="h-2 overflow-hidden rounded-full bg-sumi-800/80">
              <div className={`h-full rounded-full ${danger ? "bg-bengara" : label === "Live" ? "bg-rokusho" : "bg-aozora"}`} style={{ width: `${pct}%` }} />
            </div>
            <div className="text-right font-mono text-sumi-300 tabular-nums">{formatCount(value)}</div>
          </div>
        );
      })}
    </div>
  );
}

function GitMode({ report, cards, onInspect }: { report: OperatorCoherenceReport; cards: typeof report.cards; onInspect: (item: InspectItem) => void }) {
  return (
    <div className="grid gap-3 xl:grid-cols-[420px_minmax(0,1fr)]">
      <V2Section title="Branch census" eyebrow="git for-each-ref">
        <SourceControlBars report={report} />
      </V2Section>
      <CardTableMode title="Git cards" cards={cards} onInspect={onInspect} />
    </div>
  );
}

function RuntimeMode({ report, cards, onInspect }: { report: OperatorCoherenceReport; cards: typeof report.cards; onInspect: (item: InspectItem) => void }) {
  const dbs = report.runtime_receipts?.runtime_dbs ?? [];
  return (
    <div className="grid gap-3 xl:grid-cols-[420px_minmax(0,1fr)]">
      <div className="space-y-3">
        <V2Section title="Live ops breakdown" eyebrow="scripts/runtime/live_ops_census.py">
          <LiveOpsBars report={report} />
        </V2Section>
        <V2Section title="Runtime DBs" eyebrow="read-only sqlite probe">
          <div className="space-y-2 text-xs">
            {dbs.map((db, index) => (
              <div key={`${asText(db.path)}-${index}`} className="rounded-md border border-sumi-800/55 bg-sumi-950/35 p-2">
                <div className="truncate font-semibold text-sumi-200">{asText(db.path)}</div>
                <div className="mt-1 text-sumi-500">readable={asText(db.readable)} · age={asText(db.age_hours)}h</div>
              </div>
            ))}
          </div>
        </V2Section>
      </div>
      <CardTableMode title="Runtime cards" cards={cards} onInspect={onInspect} />
    </div>
  );
}

function TracksMode({ report, onInspect }: { report: OperatorCoherenceReport; onInspect: (item: InspectItem) => void }) {
  const tracks = report.track_portfolio.tracks ?? [];
  return (
    <div className="space-y-3">
      <V2Section title="Track portfolio" eyebrow="ACTIVE_TRACK.yaml + active_track_evidence.json">
        <div className="overflow-x-auto">
          <table className="min-w-full text-left text-xs">
            <thead className="text-[10px] uppercase tracking-[0.14em] text-sumi-600">
              <tr>
                <th className="px-2 py-2">Track</th>
                <th className="px-2 py-2">State</th>
                <th className="px-2 py-2">Readiness</th>
                <th className="px-2 py-2">Evidence</th>
                <th className="px-2 py-2">Next items</th>
              </tr>
            </thead>
            <tbody>
              {tracks.map((track, index) => (
                <tr
                  key={`${asText(track.id)}-${index}`}
                  onClick={() => onInspect({ type: "track", title: asText(track.name), subtitle: asText(track.id), status: asText(track.status), raw: track })}
                  className="cursor-pointer border-t border-sumi-800/45 hover:bg-sumi-900/45"
                >
                  <td className="max-w-[360px] px-2 py-2 font-semibold text-sumi-200">{asText(track.name)}</td>
                  <td className="px-2 py-2 text-sumi-400">{asText(track.lifecycle)} · {track.stale ? "stale" : asText(track.status)}</td>
                  <td className="px-2 py-2 font-mono text-sumi-300">{asText(track.readiness)}%</td>
                  <td className="px-2 py-2 text-sumi-400">{track.evidence_present ? "present" : "missing"}</td>
                  <td className="max-w-[420px] truncate px-2 py-2 text-sumi-500">{asText(track.next_items)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </V2Section>
    </div>
  );
}

function PreservationMode({ report, cards, onInspect }: { report: OperatorCoherenceReport; cards: typeof report.cards; onInspect: (item: InspectItem) => void }) {
  return (
    <div className="grid gap-3 xl:grid-cols-[420px_minmax(0,1fr)]">
      <V2Section title="Preservation ledger" eyebrow="local + off-machine risk">
        <pre className="max-h-[420px] overflow-auto rounded-md border border-sumi-800/55 bg-black/20 p-3 text-[10px] text-sumi-400">
          {JSON.stringify(report.preservation_ledger, null, 2)}
        </pre>
      </V2Section>
      <CardTableMode title="Preservation / receipt cards" cards={cards} onInspect={onInspect} />
    </div>
  );
}

function DesignMode({ onInspect }: { onInspect: (item: InspectItem) => void }) {
  return (
    <V2Section title="Design source board" eyebrow="Desktop canon + prototypes + inspiration drawings">
      <div className="mb-4 rounded-md border border-aozora/30 bg-aozora/8 p-3 text-sm leading-6 text-sumi-300">
        This board is intentionally using the Desktop packet: Grafana panel density, Atlas Board structure, Command Synthesis operational rails, and the Rug→Instrument anti-pattern. The full inventory is generated in `docs/design/COCKPIT_V2_DESKTOP_SOURCE_MANIFEST.md`.
      </div>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {DESIGN_SOURCES.map((source) => (
          <button
            key={source.id}
            type="button"
            onClick={() => onInspect(sourceToInspect(source))}
            className="rounded-md border border-sumi-800/60 bg-sumi-950/40 p-4 text-left transition hover:border-aozora/50 hover:bg-sumi-900/55"
          >
            <div className="flex items-start gap-2">
              <BookOpen size={15} className="mt-0.5 shrink-0 text-aozora" />
              <div>
                <div className="font-semibold text-torinoko">{source.label}</div>
                <div className="mt-1 text-xs text-sumi-500">{source.path}</div>
              </div>
            </div>
            <div className="mt-3 text-xs leading-5 text-sumi-400">{source.role}</div>
          </button>
        ))}
      </div>
    </V2Section>
  );
}

function CardTableMode({ title, cards, onInspect }: { title: string; cards: CoherenceCardLike[]; onInspect: (item: InspectItem) => void }) {
  return (
    <V2Section title={title} eyebrow={`${cards.length} cards`}>
      <div className="space-y-2">
        {cards.slice(0, 80).map((card) => <V2CardRow key={card.id} card={card} onInspect={onInspect} />)}
        {!cards.length ? <div className="rounded-md border border-dashed border-sumi-800/70 p-6 text-center text-sm text-sumi-600">No cards match this view.</div> : null}
        {cards.length > 80 ? <div className="text-xs text-sumi-600">+{cards.length - 80} more cards available via search/API.</div> : null}
      </div>
    </V2Section>
  );
}

type CoherenceCardLike = OperatorCoherenceReport["cards"][number];

function ModeButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button type="button" onClick={onClick} className="rounded-md border border-sumi-800/70 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-sumi-500 hover:border-aozora/50 hover:text-aozora">
      {label}
    </button>
  );
}
