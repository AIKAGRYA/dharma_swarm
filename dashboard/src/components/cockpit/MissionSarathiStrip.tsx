"use client";

import {
  AlertTriangle,
  CheckCircle2,
  CircleDashed,
  Network,
  RefreshCw,
  ShieldQuestion,
} from "lucide-react";
import {
  useMissionSarathi,
  type EvidenceTimelineItem,
  type MissionSnapshot,
  type TaskTruthRow,
  type TaskTruthState,
} from "@/hooks/useMissionSarathi";

const STATE_TONE: Record<TaskTruthState, string> = {
  verified_working: "border-botan/40 bg-botan/10 text-botan",
  terminal_receipted: "border-aozora/40 bg-aozora/10 text-aozora",
  lease_only: "border-kincha/40 bg-kincha/10 text-kincha",
  queued: "border-sumi-600/40 bg-sumi-800/30 text-sumi-300",
  stale: "border-kincha/40 bg-kincha/10 text-kincha",
  expired: "border-bengara/40 bg-bengara/10 text-bengara",
  orphan: "border-bengara/40 bg-bengara/10 text-bengara",
  join_unknown: "border-kincha/40 bg-kincha/10 text-kincha",
  conflict: "border-bengara/50 bg-bengara/15 text-bengara",
  terminal_unverified: "border-bengara/40 bg-bengara/10 text-bengara",
  unknown: "border-sumi-600/40 bg-sumi-800/30 text-sumi-400",
};

function shortId(value: string): string {
  if (!value) return "—";
  return value.length > 22 ? `${value.slice(0, 10)}…${value.slice(-7)}` : value;
}

function formatTime(value: string | null): string {
  if (!value) return "time unknown";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "invalid time";
  return parsed.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function TaskTruthRegion({ rows }: { rows: TaskTruthRow[] }) {
  return (
    <section aria-labelledby="mission-task-truth-title" className="min-w-0">
      <div className="mb-2 flex items-center justify-between gap-2">
        <h3
          id="mission-task-truth-title"
          className="text-xs font-semibold uppercase tracking-[0.14em] text-sumi-300"
        >
          Task / execution truth
        </h3>
        <span className="text-[11px] text-sumi-500">{rows.length} tasks</span>
      </div>
      {rows.length === 0 ? (
        <div className="rounded-md border border-sumi-700/40 bg-sumi-900/30 p-3 text-xs text-sumi-400">
          No canonical task snapshot is available. Empty does not mean idle or
          complete.
        </div>
      ) : (
        <ol className="space-y-2">
          {rows.map((row) => (
            <li
              key={row.task.task_id}
              className="rounded-md border border-sumi-800/60 bg-sumi-900/35 p-3"
            >
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="break-words text-sm font-medium text-torinoko">
                    {row.task.title || row.task.task_id}
                  </div>
                  <code className="mt-0.5 block break-all text-[10px] text-sumi-500">
                    {row.task.task_id}
                  </code>
                </div>
                <span
                  className={`shrink-0 rounded border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide ${STATE_TONE[row.state]}`}
                >
                  {row.label}
                </span>
              </div>
              <p className="mt-2 text-xs leading-5 text-sumi-400">{row.detail}</p>
              <dl className="mt-2 grid grid-cols-1 gap-x-3 gap-y-1 text-[11px] sm:grid-cols-2">
                <div className="min-w-0">
                  <dt className="inline text-sumi-600">Agent </dt>
                  <dd className="inline break-all text-sumi-300">
                    {row.attempt?.assigned_to ||
                      row.lease?.agent_id ||
                      row.task.assigned_to ||
                      "unassigned"}
                  </dd>
                </div>
                <div className="min-w-0">
                  <dt className="inline text-sumi-600">Attempt </dt>
                  <dd className="inline break-all text-sumi-300">
                    {shortId(row.attempt?.attempt_id ?? "")}
                  </dd>
                </div>
                <div className="min-w-0">
                  <dt className="inline text-sumi-600">Lease </dt>
                  <dd className="inline text-sumi-300">
                    {row.lease
                      ? row.lease.expired
                        ? "expired"
                        : row.lease.active
                          ? "active · not proof"
                          : row.lease.status
                      : "not observed"}
                  </dd>
                </div>
                <div className="min-w-0">
                  <dt className="inline text-sumi-600">Owner run </dt>
                  <dd className="inline break-all text-sumi-300">
                    {shortId(row.ownerRunId)}
                  </dd>
                </div>
                <div className="min-w-0">
                  <dt className="inline text-sumi-600">Acceptance </dt>
                  <dd className="inline text-sumi-300">
                    {row.acceptance.replace("_", " ")}
                  </dd>
                </div>
              </dl>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

function TopologyRegion({
  snapshot,
  rows,
}: {
  snapshot: MissionSnapshot | null;
  rows: TaskTruthRow[];
}) {
  const visibleRows = [...rows]
    .sort((left, right) =>
      left.task.task_id.localeCompare(right.task.task_id),
    )
    .slice(0, 10);
  const height = Math.max(170, visibleRows.length * 58 + 36);

  return (
    <section aria-labelledby="mission-topology-title" className="min-w-0">
      <div className="mb-2 flex items-center justify-between gap-2">
        <h3
          id="mission-topology-title"
          className="text-xs font-semibold uppercase tracking-[0.14em] text-sumi-300"
        >
          Stable topology
        </h3>
        <span className="text-[11px] text-sumi-500">deterministic · ≤10 tasks</span>
      </div>
      {!snapshot ? (
        <div className="rounded-md border border-sumi-700/40 bg-sumi-900/30 p-3 text-xs text-sumi-400">
          Topology is uninitialized because no canonical mission snapshot was
          injected.
        </div>
      ) : (
        <>
          <div className="hidden md:block">
            <svg
              viewBox={`0 0 720 ${height}`}
              className="h-auto w-full text-sumi-600"
              role="img"
              aria-labelledby="mission-topology-svg-title mission-topology-svg-desc"
            >
              <title id="mission-topology-svg-title">
                Mission, task, and assigned agent topology
              </title>
              <desc id="mission-topology-svg-desc">
                Solid task-to-agent edges have recent matching work evidence.
                Dashed edges are structural identity only.
              </desc>
              <rect
                x="16"
                y={height / 2 - 28}
                width="148"
                height="56"
                rx="8"
                className="fill-sumi-900 stroke-aozora"
              />
              <text
                x="30"
                y={height / 2 - 5}
                className="fill-torinoko text-[13px] font-medium"
              >
                {snapshot.mission.title || "Mission"}
              </text>
              <text
                x="30"
                y={height / 2 + 14}
                className="fill-sumi-500 text-[10px]"
              >
                {shortId(snapshot.mission.mission_id)}
              </text>
              {visibleRows.map((row, index) => {
                const y = 26 + index * 58;
                const verified = row.state === "verified_working";
                const agent =
                  row.attempt?.assigned_to ||
                  row.lease?.agent_id ||
                  row.task.assigned_to ||
                  "unassigned";
                return (
                  <g key={row.task.task_id}>
                    <line
                      x1="164"
                      y1={height / 2}
                      x2="252"
                      y2={y + 19}
                      className="stroke-sumi-700"
                      strokeWidth="1.5"
                    />
                    <rect
                      x="252"
                      y={y}
                      width="204"
                      height="38"
                      rx="6"
                      className={`fill-sumi-900 ${verified ? "stroke-botan" : "stroke-sumi-600"}`}
                    />
                    <text
                      x="264"
                      y={y + 16}
                      className="fill-torinoko text-[11px]"
                    >
                      {(row.task.title || row.task.task_id).slice(0, 27)}
                    </text>
                    <text
                      x="264"
                      y={y + 30}
                      className="fill-sumi-500 text-[9px]"
                    >
                      {row.label}
                    </text>
                    <line
                      x1="456"
                      y1={y + 19}
                      x2="536"
                      y2={y + 19}
                      className={verified ? "stroke-botan" : "stroke-sumi-600"}
                      strokeWidth={verified ? "2" : "1.5"}
                      strokeDasharray={verified ? undefined : "5 5"}
                    />
                    <rect
                      x="536"
                      y={y + 2}
                      width="166"
                      height="34"
                      rx="17"
                      className="fill-sumi-900 stroke-sumi-700"
                    />
                    <text
                      x="550"
                      y={y + 23}
                      className="fill-sumi-300 text-[10px]"
                    >
                      {agent.slice(0, 23)}
                    </text>
                  </g>
                );
              })}
            </svg>
            <p className="mt-1 text-[10px] text-sumi-500">
              Solid = recent matching substantive event. Dashed = assignment or
              lease only.
            </p>
          </div>
          <ul className="space-y-2 md:hidden" aria-label="Topology as a list">
            {visibleRows.map((row) => (
              <li
                key={row.task.task_id}
                className="rounded-md border border-sumi-800/60 bg-sumi-900/35 p-3 text-xs"
              >
                <div className="font-medium text-torinoko">
                  {snapshot.mission.title || snapshot.mission.mission_id}
                </div>
                <div className="my-1 text-sumi-600" aria-hidden="true">
                  ↓
                </div>
                <div className="break-words text-sumi-300">{row.task.title}</div>
                <div className="my-1 text-sumi-600" aria-hidden="true">
                  {row.state === "verified_working" ? "━━" : "┄┄"}▶
                </div>
                <div className="break-all text-sumi-400">
                  {row.attempt?.assigned_to ||
                    row.lease?.agent_id ||
                    row.task.assigned_to ||
                    "unassigned"}
                </div>
                <div className="mt-1 text-[10px] text-sumi-500">{row.label}</div>
              </li>
            ))}
          </ul>
          {rows.length > visibleRows.length && (
            <p className="mt-2 text-[11px] text-kincha">
              {rows.length - visibleRows.length} additional tasks omitted from
              the bounded map; all remain listed in task truth.
            </p>
          )}
        </>
      )}
    </section>
  );
}

function TimelineItem({ item }: { item: EvidenceTimelineItem }) {
  return (
    <li className="border-l border-sumi-700/60 pl-3">
      <div className="flex flex-wrap items-center gap-2">
        <span
          className={`rounded border px-1.5 py-0.5 text-[10px] uppercase tracking-wide ${
            item.source === "runtime_event"
              ? "border-botan/30 text-botan"
              : "border-aozora/30 text-aozora"
          }`}
        >
          {item.source === "runtime_event" ? "runtime" : "receipt"}
        </span>
        <span className="break-all text-xs font-medium text-torinoko">
          {item.kind}
        </span>
        <time className="text-[10px] text-sumi-500" dateTime={item.createdAt ?? undefined}>
          {formatTime(item.createdAt)}
        </time>
      </div>
      <p className="mt-1 break-words text-xs leading-5 text-sumi-400">
        {item.summary}
      </p>
      <code className="mt-1 block break-all text-[10px] text-sumi-600">
        task {shortId(item.taskId)} · execution {shortId(item.executionId)} ·{" "}
        {item.status || "status unknown"}
      </code>
    </li>
  );
}

function EvidenceTimelineRegion({
  items,
}: {
  items: EvidenceTimelineItem[];
}) {
  return (
    <section aria-labelledby="mission-evidence-title" className="min-w-0">
      <div className="mb-2 flex items-center justify-between gap-2">
        <h3
          id="mission-evidence-title"
          className="text-xs font-semibold uppercase tracking-[0.14em] text-sumi-300"
        >
          Evidence timeline
        </h3>
        <span className="text-[11px] text-sumi-500">newest first · ≤24</span>
      </div>
      {items.length === 0 ? (
        <div className="rounded-md border border-sumi-700/40 bg-sumi-900/30 p-3 text-xs text-sumi-400">
          No mission receipts or projected runtime events were observed. A
          heartbeat or empty timeline is not completed work.
        </div>
      ) : (
        <ol className="space-y-3">
          {items.map((item) => (
            <TimelineItem key={item.id} item={item} />
          ))}
        </ol>
      )}
    </section>
  );
}

export function MissionSarathiStrip({ missionId }: { missionId: string }) {
  const {
    projection,
    snapshot,
    taskTruth,
    timeline,
    sourceErrors,
    runtimeSuppressedReason,
    generatedAt,
    isLoading,
    isFetching,
    error,
    refresh,
  } = useMissionSarathi(missionId);
  const verifiedCount = taskTruth.filter(
    (row) => row.state === "verified_working",
  ).length;
  const attentionCount = taskTruth.filter((row) =>
    [
      "expired",
      "orphan",
      "join_unknown",
      "conflict",
      "terminal_unverified",
    ].includes(row.state),
  ).length;
  const state = projection?.state ?? (isLoading ? "loading" : "unknown");

  return (
    <section
      aria-labelledby="mission-sarathi-title"
      className="rounded-xl border border-sumi-700/40 bg-sumi-950/60"
    >
      <header className="flex flex-wrap items-start justify-between gap-3 border-b border-sumi-800/50 px-3 py-3 sm:px-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Network className="h-4 w-4 text-aozora" aria-hidden="true" />
            <h2
              id="mission-sarathi-title"
              className="text-sm font-semibold text-torinoko"
            >
              Dharma Constellation
            </h2>
            <span className="rounded border border-sumi-700/50 px-2 py-0.5 text-[10px] uppercase tracking-wide text-sumi-400">
              {state}
            </span>
          </div>
          <code className="mt-1 block break-all text-[10px] text-sumi-500">
            {missionId}
          </code>
          <p className="mt-1 max-w-3xl text-xs leading-5 text-sumi-400">
            Three synchronized views of canonical mission truth. Lease,
            heartbeat, and ACK state remain connectivity evidence—not verified
            work.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void refresh()}
          disabled={isFetching}
          className="inline-flex min-h-10 items-center gap-2 rounded-md border border-sumi-700/50 bg-sumi-900/50 px-3 py-2 text-xs text-sumi-300 hover:border-aozora/40 hover:text-torinoko disabled:cursor-wait disabled:opacity-60"
          aria-label="Refresh mission constellation"
        >
          <RefreshCw className="h-4 w-4" aria-hidden="true" />
          {isFetching ? "Checking…" : "Refresh"}
        </button>
      </header>

      <div className="grid grid-cols-2 gap-px border-b border-sumi-800/50 bg-sumi-800/50 sm:grid-cols-4">
        <div className="bg-sumi-950/90 p-3">
          <div className="text-[10px] uppercase tracking-wide text-sumi-600">Tasks</div>
          <div className="mt-1 text-lg font-medium text-torinoko">{taskTruth.length}</div>
        </div>
        <div className="bg-sumi-950/90 p-3">
          <div className="text-[10px] uppercase tracking-wide text-sumi-600">
            Verified working
          </div>
          <div className="mt-1 text-lg font-medium text-botan">{verifiedCount}</div>
        </div>
        <div className="bg-sumi-950/90 p-3">
          <div className="text-[10px] uppercase tracking-wide text-sumi-600">
            Needs attention
          </div>
          <div className="mt-1 text-lg font-medium text-bengara">{attentionCount}</div>
        </div>
        <div className="bg-sumi-950/90 p-3">
          <div className="text-[10px] uppercase tracking-wide text-sumi-600">
            Reconciliation
          </div>
          <div className="mt-1 break-words text-sm font-medium text-sumi-300">
            {snapshot?.reconciliation ?? "unknown"}
          </div>
        </div>
      </div>

      {(error || sourceErrors.length > 0 || runtimeSuppressedReason) && (
        <div
          className="border-b border-sumi-800/50 bg-sumi-900/30 px-3 py-3 text-xs sm:px-4"
          role="status"
        >
          <div className="flex items-start gap-2">
            {sourceErrors.length > 0 || error ? (
              <AlertTriangle
                className="mt-0.5 h-4 w-4 shrink-0 text-kincha"
                aria-hidden="true"
              />
            ) : (
              <ShieldQuestion
                className="mt-0.5 h-4 w-4 shrink-0 text-sumi-500"
                aria-hidden="true"
              />
            )}
            <div className="min-w-0 space-y-1 text-sumi-400">
              {error && (
                <p className="break-words text-bengara">
                  Query failed: {error instanceof Error ? error.message : String(error)}
                </p>
              )}
              {sourceErrors.map((sourceError) => (
                <p key={sourceError} className="break-words">
                  {sourceError}
                </p>
              ))}
              {runtimeSuppressedReason && (
                <p className="break-words">{runtimeSuppressedReason}</p>
              )}
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 gap-5 p-3 sm:p-4 xl:grid-cols-3">
        <TaskTruthRegion rows={taskTruth} />
        <TopologyRegion snapshot={snapshot} rows={taskTruth} />
        <EvidenceTimelineRegion items={timeline} />
      </div>

      <footer className="flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-sumi-800/50 px-3 py-2 text-[10px] text-sumi-500 sm:px-4">
        <span className="inline-flex items-center gap-1">
          {projection?.runtime_projection_ready ? (
            <CheckCircle2 className="h-3.5 w-3.5 text-botan" aria-hidden="true" />
          ) : (
            <CircleDashed className="h-3.5 w-3.5" aria-hidden="true" />
          )}
          Runtime source: {projection?.runtime_projection_mode ?? "unavailable"}
        </span>
        <span>Authority: {snapshot?.authority ?? "not observed"}</span>
        <span>
          Generated{" "}
          {generatedAt ? (
            <time dateTime={generatedAt}>{formatTime(generatedAt)}</time>
          ) : (
            "unknown"
          )}
        </span>
      </footer>
    </section>
  );
}
