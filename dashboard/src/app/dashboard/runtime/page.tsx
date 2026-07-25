"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { Check, RotateCcw, X } from "lucide-react";
import { ControlPlanePageSummary } from "@/components/dashboard/ControlPlanePageSummary";
import { ControlPlaneSurfaceGrid } from "@/components/dashboard/ControlPlaneSurfaceGrid";
import { ControlPlaneStrip } from "@/components/dashboard/ControlPlaneStrip";
import {
  API_TRANSPORT_MODE,
  BASE_URL,
  approveRuntimeInterrupt,
  rejectRuntimeInterrupt,
  resumeRuntimeInterrupt,
  runtimeEventsStreamPath,
} from "@/lib/api";
import { buildControlPlanePageMeta } from "@/lib/controlPlanePageMeta";
import {
  buildControlPlaneSyncState,
} from "@/lib/controlPlaneShell";
import {
  buildRuntimeControlActionRequest,
  runtimeControlActionOptions,
  type RuntimeControlActionKind,
} from "@/lib/runtimeControlPlane";
import { buildRuntimeOperatorHandbook } from "@/lib/runtimeOperatorHandbook";
import { buildControlPlaneSurfaces } from "@/lib/controlPlaneSurfaces";
import { colors, glowText } from "@/lib/theme";
import { useRuntimeControlPlane } from "@/hooks/useRuntimeControlPlane";
import type {
  ChatProfileOut,
  RuntimeAssistantsSnapshot,
  RuntimeBackgroundJobsSnapshot,
  RuntimeControlActionResult,
  RuntimeGraphSnapshot,
  RuntimeInterruptControlEvent,
  RuntimeInterruptsSnapshot,
} from "@/lib/types";

const PAGE_META = buildControlPlanePageMeta("runtime");
const PAGE_ACCENT = colors[PAGE_META.accent];

interface RuntimeControlActionState {
  eventId: string;
  action: RuntimeControlActionKind;
  status: "running" | "ok" | "error";
  message: string;
}

function transportLabel(): string {
  if (API_TRANSPORT_MODE === "same-origin") {
    return "Same-origin proxy via /api";
  }
  return BASE_URL || "Direct override";
}

function currentOriginLabel(): string {
  if (typeof window === "undefined") {
    return "server";
  }
  return window.location.origin;
}

function badgeClasses(kind: "ok" | "warn" | "error" | "muted"): string {
  switch (kind) {
    case "ok":
      return "border-emerald-900/40 bg-emerald-950/20 text-emerald-300";
    case "warn":
      return "border-amber-900/40 bg-amber-950/20 text-amber-300";
    case "error":
      return "border-red-900/40 bg-red-950/20 text-red-300";
    default:
      return "border-sumi-700/50 bg-sumi-800/50 text-sumi-300";
  }
}

function profileStatusKind(profile: ChatProfileOut): "ok" | "warn" | "error" {
  if (profile.available === true) {
    return "ok";
  }
  if (profile.availability_kind === "quota_blocked") {
    return "warn";
  }
  return "error";
}

function profileStatusLabel(profile: ChatProfileOut): string {
  if (profile.available === true) {
    return "available";
  }
  return profile.availability_kind?.replace(/_/g, " ") ?? "unavailable";
}

export default function RuntimePage() {
  const [currentOrigin, setCurrentOrigin] = useState("loading");
  const [controlActionState, setControlActionState] =
    useState<RuntimeControlActionState | null>(null);
  const transportMode = API_TRANSPORT_MODE;
  const transportDetail = transportLabel();
  const {
    chatStatus,
    health,
    runtimeGraph,
    runtimeInterrupts,
    runtimeAssistants,
    runtimeBackgroundJobs,
    error,
    snapshot,
    isLoading,
    isFetching,
    refresh,
  } = useRuntimeControlPlane();
  const syncState = buildControlPlaneSyncState({ isLoading, isFetching });

  useEffect(() => {
    const frameId = window.requestAnimationFrame(() => {
      setCurrentOrigin(currentOriginLabel());
    });
    return () => window.cancelAnimationFrame(frameId);
  }, []);

  const profiles = useMemo(() => chatStatus?.profiles ?? [], [chatStatus]);
  const runtimeHandbook = useMemo(() => buildRuntimeOperatorHandbook(), []);
  const surfaces = useMemo(
    () =>
      buildControlPlaneSurfaces({
        snapshot,
        chatStatus,
        currentPath: "/dashboard/runtime",
      }),
    [chatStatus, snapshot],
  );

  async function handleRuntimeControlAction(
    event: RuntimeInterruptControlEvent,
    action: RuntimeControlActionKind,
  ): Promise<void> {
    const body = buildRuntimeControlActionRequest(event, action);
    setControlActionState({
      eventId: event.event_id,
      action,
      status: "running",
      message: `${action} recording`,
    });

    const response =
      action === "approve"
        ? await approveRuntimeInterrupt(body)
        : action === "reject"
          ? await rejectRuntimeInterrupt(body)
          : await resumeRuntimeInterrupt(body);
    const result: RuntimeControlActionResult | null =
      response.status === "ok" ? response.data : null;

    if (result?.status) {
      setControlActionState({
        eventId: event.event_id,
        action,
        status: "ok",
        message: result.target_found
          ? `recorded ${result.status}`
          : `recorded ${result.status}; target not found`,
      });
      void refresh();
      return;
    }

    setControlActionState({
      eventId: event.event_id,
      action,
      status: "error",
      message: response.error || `failed to record ${action}`,
    });
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="space-y-6"
    >
      <div>
        <div>
          <h1
            className="font-heading text-2xl font-bold tracking-tight"
            style={{
              color: PAGE_ACCENT,
              textShadow: glowText(PAGE_ACCENT, 0.5),
            }}
          >
            {PAGE_META.pageTitle}
          </h1>
          <p className="max-w-2xl text-sm text-sumi-400">
            {PAGE_META.pageDetail}
          </p>
        </div>
      </div>

      <ControlPlanePageSummary
        routeId="runtime"
        snapshot={snapshot}
        surfaces={surfaces}
      />

      <ControlPlaneStrip
        snapshot={snapshot}
        surfaces={surfaces}
        syncState={syncState}
        onRefresh={() => {
          void refresh();
        }}
      />

      <ControlPlaneSurfaceGrid
        surfaces={surfaces}
        title={PAGE_META.deckTitle}
        detail={PAGE_META.deckDetail}
      />

      <div className="grid gap-4 xl:grid-cols-4 md:grid-cols-2">
        <RuntimeCard
          label="Runtime Status"
          value={snapshot.statusLabel}
          detail={error ?? "Launchd-backed local runtime is the canonical operator path."}
          badge={badgeClasses(snapshot.statusKind)}
        />
        <RuntimeCard
          label="Browser Origin"
          value={currentOrigin}
          detail="This stays stable in the browser. The app shell wraps the same routes in a native window."
          badge={badgeClasses("muted")}
        />
        <RuntimeCard
          label="API Transport"
          value={transportMode}
          detail={transportDetail}
          badge={badgeClasses(transportMode === "same-origin" ? "ok" : "warn")}
        />
        <RuntimeCard
          label="Chat Contract"
          value={snapshot.contractVersion}
          detail={`Default profile: ${snapshot.defaultProfile?.label ?? "unknown"}`}
          badge={badgeClasses(chatStatus?.chat_contract_version ? "ok" : "muted")}
        />
      </div>

      {isLoading && !chatStatus && !health ? (
        <div className="py-12 text-center text-sumi-500">Loading runtime status...</div>
      ) : (
        <>
          <RuntimeGraphPanel
            graph={runtimeGraph}
            interrupts={runtimeInterrupts}
            assistants={runtimeAssistants}
            background={runtimeBackgroundJobs}
            statusLabel={snapshot.runtimeGraphStatusLabel}
            detail={snapshot.runtimeGraphDetail}
            controlStatusLabel={snapshot.runtimeInterruptStatusLabel}
            controlDetail={snapshot.runtimeInterruptDetail}
            assistantsStatusLabel={snapshot.runtimeAssistantsStatusLabel}
            assistantsDetail={snapshot.runtimeAssistantsDetail}
            backgroundStatusLabel={snapshot.runtimeBackgroundStatusLabel}
            backgroundDetail={snapshot.runtimeBackgroundDetail}
            controlActionState={controlActionState}
            onControlAction={handleRuntimeControlAction}
          />

          <section className="rounded-2xl border border-sumi-700/50 bg-sumi-900/60 p-5 shadow-[0_0_0_1px_rgba(80,90,110,0.08)]">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="font-heading text-lg text-sumi-100">Chat Lanes</h2>
                <p className="text-sm text-sumi-400">
                  Server-advertised profiles only. The frontend now renders what the API
                  declares instead of relying on stale hardcoded lanes.
                </p>
              </div>
              <div className="text-xs text-sumi-500">
                Persistent sessions: {chatStatus?.persistent_sessions ? "on" : "off"}
              </div>
            </div>
            <div className="grid gap-3 lg:grid-cols-2">
              {profiles.length === 0 ? (
                <div className="rounded-xl border border-sumi-700/40 bg-sumi-800/30 p-4 text-sm text-sumi-500">
                  No profiles advertised by `/api/chat/status`.
                </div>
              ) : (
                profiles.map((profile) => (
                  <div
                    key={profile.id}
                    className="rounded-xl border border-sumi-700/40 bg-sumi-800/30 p-4"
                  >
                    <div className="mb-3 flex items-center justify-between gap-3">
                      <div>
                        <div className="text-sm font-medium text-sumi-100">{profile.label}</div>
                        <div className="text-xs text-sumi-500">
                          {profile.provider} · {profile.model}
                        </div>
                      </div>
                      <span
                        className={`rounded-full border px-2.5 py-1 text-[11px] font-medium uppercase tracking-[0.12em] ${badgeClasses(
                          profileStatusKind(profile),
                        )}`}
                      >
                        {profileStatusLabel(profile)}
                      </span>
                    </div>
                    <p className="text-sm text-sumi-300">{profile.summary}</p>
                    {profile.status_note ? (
                      <p className="mt-3 text-xs text-sumi-500">{profile.status_note}</p>
                    ) : null}
                  </div>
                ))
              )}
            </div>
          </section>

          <section className="grid gap-4 xl:grid-cols-[1.15fr_0.85fr]">
            <div className="rounded-2xl border border-sumi-700/50 bg-sumi-900/60 p-5">
              <h2 className="font-heading text-lg text-sumi-100">Backend Health</h2>
              <p className="mt-1 text-sm text-sumi-400">
                This is the server truth behind the dashboard shell, not a separate app
                health check.
              </p>

              <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                <MiniStat
                  label="Overall"
                  value={health?.overall_status ?? "unknown"}
                />
                <MiniStat
                  label="Agents"
                  value={String(health?.agent_health.length ?? 0)}
                />
                <MiniStat
                  label="Anomalies"
                  value={String(health?.anomalies.length ?? 0)}
                />
                <MiniStat
                  label="Failure Rate"
                  value={
                    health ? `${(health.failure_rate * 100).toFixed(1)}%` : "unknown"
                  }
                />
              </div>

              <div className="mt-5 space-y-3">
                {(health?.agent_health ?? []).slice(0, 8).map((agent) => (
                  <div
                    key={agent.agent_name}
                    className="flex items-center justify-between rounded-xl border border-sumi-700/40 bg-sumi-800/30 px-4 py-3"
                  >
                    <div>
                      <div className="text-sm font-medium text-sumi-100">
                        {agent.agent_name}
                      </div>
                      <div className="text-xs text-sumi-500">
                        last seen {agent.last_seen ?? "never"}
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-sm text-sumi-200">
                        {(agent.success_rate * 100).toFixed(0)}%
                      </div>
                      <div className="text-xs text-sumi-500">{agent.status}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-2xl border border-sumi-700/50 bg-sumi-900/60 p-5">
              <h2 className="font-heading text-lg text-sumi-100">Product Shell Path</h2>
              <p className="mt-1 text-sm text-sumi-400">
                Runtime truth stays on the launchd-backed dashboard shell, the overnight
                tmux watch path, and the morning artifacts they emit. Wrapper experiments
                should stay downstream of that authority.
              </p>

              <div className="mt-5 grid gap-4 xl:grid-cols-2 text-sm text-sumi-300">
                <div className="rounded-xl border border-sumi-700/40 bg-sumi-800/30 p-4">
                  <div className="mb-2 text-xs uppercase tracking-[0.16em] text-sumi-500">
                    Stable routes
                  </div>
                  <div className="space-y-1 font-mono text-xs text-sumi-300">
                    {runtimeHandbook.stableRoutes.map((href) => (
                      <div key={href}>{href}</div>
                    ))}
                  </div>
                </div>

                {runtimeHandbook.sections.map((section) => (
                  <div
                    key={section.id}
                    className="rounded-xl border border-sumi-700/40 bg-sumi-800/30 p-4"
                  >
                    <div className="mb-2 text-xs uppercase tracking-[0.16em] text-sumi-500">
                      {section.title}
                    </div>
                    <p className="text-sm text-sumi-300">{section.detail}</p>
                    <div className="mt-3 space-y-1 font-mono text-xs text-sumi-300">
                      {section.entries.map((entry) => (
                        <div key={entry}>{entry}</div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>

              <div className="mt-4 rounded-xl border border-sumi-700/40 bg-sumi-800/30 p-4">
                <div className="mb-2 text-xs uppercase tracking-[0.16em] text-sumi-500">
                  Wrapper path
                </div>
                <p className="text-sm text-sumi-300">{runtimeHandbook.wrapperDetail}</p>
                <Link
                  href={runtimeHandbook.nextStep.href}
                  className="mt-3 inline-flex text-sm text-aozora transition-colors hover:text-aozora/80"
                >
                  {`Open ${runtimeHandbook.nextStep.label}`}
                </Link>
              </div>
            </div>
          </section>
        </>
      )}
    </motion.div>
  );
}

function RuntimeGraphPanel({
  graph,
  interrupts,
  assistants,
  background,
  statusLabel,
  detail,
  controlStatusLabel,
  controlDetail,
  assistantsStatusLabel,
  assistantsDetail,
  backgroundStatusLabel,
  backgroundDetail,
  controlActionState,
  onControlAction,
}: {
  graph: RuntimeGraphSnapshot | null;
  interrupts: RuntimeInterruptsSnapshot | null;
  assistants: RuntimeAssistantsSnapshot | null;
  background: RuntimeBackgroundJobsSnapshot | null;
  statusLabel: string;
  detail: string;
  controlStatusLabel: string;
  controlDetail: string;
  assistantsStatusLabel: string;
  assistantsDetail: string;
  backgroundStatusLabel: string;
  backgroundDetail: string;
  controlActionState: RuntimeControlActionState | null;
  onControlAction: (
    event: RuntimeInterruptControlEvent,
    action: RuntimeControlActionKind,
  ) => Promise<void>;
}) {
  const topologies = graph?.topology_states.slice(0, 6) ?? [];
  const receipts = graph?.receipts.slice(0, 6) ?? [];
  const controlEvents = interrupts?.control_events.slice(0, 6) ?? [];
  const assistantRows = assistants?.assistants.slice(0, 4) ?? [];
  const configurationRows = assistants?.configurations.slice(0, 4) ?? [];
  const cronRows = background?.cron_jobs.slice(0, 4) ?? [];
  const backgroundRuns = background?.background_runs.slice(0, 4) ?? [];
  const streamPath = runtimeEventsStreamPath({ ledger_kind: "runtime", limit: 20 });

  return (
    <section className="rounded-2xl border border-sumi-700/50 bg-sumi-900/60 p-5">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="font-heading text-lg text-sumi-100">Runtime Graph</h2>
          <p className="text-sm text-sumi-400">{detail}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className={`rounded-full border px-2.5 py-1 text-[11px] font-medium uppercase tracking-[0.12em] ${badgeClasses(graph ? "ok" : "muted")}`}>
            {statusLabel}
          </span>
          <span className={`rounded-full border px-2.5 py-1 text-[11px] font-medium uppercase tracking-[0.12em] ${badgeClasses(interrupts ? "ok" : "muted")}`}>
            {controlStatusLabel}
          </span>
          <span className={`rounded-full border px-2.5 py-1 text-[11px] font-medium uppercase tracking-[0.12em] ${badgeClasses(assistants ? "ok" : "muted")}`}>
            {assistantsStatusLabel}
          </span>
          <span className={`rounded-full border px-2.5 py-1 text-[11px] font-medium uppercase tracking-[0.12em] ${badgeClasses(background ? "ok" : "muted")}`}>
            {backgroundStatusLabel}
          </span>
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-4">
        <MiniStat label="Active Runs" value={String(graph?.summary.active_run_count ?? 0)} />
        <MiniStat label="Active Agents" value={String(graph?.summary.active_agent_count ?? 0)} />
        <MiniStat label="Checkpoints" value={String(graph?.summary.checkpoint_count ?? 0)} />
        <MiniStat label="Receipts" value={String(graph?.summary.receipt_count ?? 0)} />
      </div>

      <div className="mt-3 grid gap-3 md:grid-cols-4">
        <MiniStat
          label="Pending Interrupts"
          value={String(interrupts?.summary.pending_interrupt_count ?? 0)}
        />
        <MiniStat
          label="Human Approval"
          value={String(interrupts?.summary.human_approval_required_count ?? 0)}
        />
        <MiniStat label="Approved" value={String(interrupts?.summary.approved_count ?? 0)} />
        <MiniStat label="Resumed" value={String(interrupts?.summary.resumed_count ?? 0)} />
      </div>

      <div className="mt-3 grid gap-3 md:grid-cols-4">
        <MiniStat
          label="Assistants"
          value={String(assistants?.summary.assistant_count ?? 0)}
        />
        <MiniStat
          label="Configurations"
          value={String(assistants?.summary.configuration_count ?? 0)}
        />
        <MiniStat
          label="Cron Jobs"
          value={String(background?.summary.cron_job_count ?? 0)}
        />
        <MiniStat
          label="Background Runs"
          value={String(background?.summary.background_run_count ?? 0)}
        />
      </div>

      <div className="mt-5 grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
        <div className="space-y-3">
          {topologies.length === 0 ? (
            <div className="rounded-xl border border-sumi-700/40 bg-sumi-800/30 p-4 text-sm text-sumi-500">
              No topology states in the selected runtime snapshot.
            </div>
          ) : (
            topologies.map((state) => (
              <div
                key={state.run_id}
                className="rounded-xl border border-sumi-700/40 bg-sumi-800/30 p-4"
              >
                <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <div className="text-sm font-medium text-sumi-100">
                      {state.topology}
                    </div>
                    <div className="font-mono text-xs text-sumi-500">{state.run_id}</div>
                  </div>
                  <span className="rounded-full border border-aozora/30 bg-aozora/10 px-2.5 py-1 text-[11px] font-medium uppercase tracking-[0.12em] text-aozora">
                    {state.active_agent || "no active agent"}
                  </span>
                </div>
                <div className="grid gap-2 text-xs text-sumi-400 md:grid-cols-3">
                  <div>
                    <div className="uppercase tracking-[0.14em] text-sumi-600">Task</div>
                    <div className="font-mono text-sumi-300">{state.task_id}</div>
                  </div>
                  <div>
                    <div className="uppercase tracking-[0.14em] text-sumi-600">Node</div>
                    <div className="font-mono text-sumi-300">{state.current_node || "none"}</div>
                  </div>
                  <div>
                    <div className="uppercase tracking-[0.14em] text-sumi-600">Children</div>
                    <div className="font-mono text-sumi-300">{state.child_run_ids.length}</div>
                  </div>
                </div>
                {state.checkpoint_id ? (
                  <div className="mt-3 truncate font-mono text-xs text-sumi-500">
                    {state.checkpoint_id}
                  </div>
                ) : null}
              </div>
            ))
          )}
        </div>

        <div className="space-y-4">
          <div className="rounded-xl border border-sumi-700/40 bg-sumi-800/30 p-4">
            <div className="mb-3 text-xs uppercase tracking-[0.16em] text-sumi-500">
              Recent Receipts
            </div>
            <div className="space-y-3">
              {receipts.length === 0 ? (
                <div className="text-sm text-sumi-500">No runtime receipts in snapshot.</div>
              ) : (
                receipts.map((receipt) => (
                  <div key={receipt.receipt_id} className="border-b border-sumi-700/40 pb-3 last:border-0 last:pb-0">
                    <div className="text-sm text-sumi-200">{receipt.receipt_type}</div>
                    <div className="font-mono text-xs text-sumi-500">{receipt.receipt_id}</div>
                    <div className="mt-1 text-xs text-sumi-500">
                      {receipt.status} · {receipt.agent_id || "no-agent"}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          <div className="rounded-xl border border-sumi-700/40 bg-sumi-800/30 p-4">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <div className="text-xs uppercase tracking-[0.16em] text-sumi-500">
                Control Events
              </div>
              <div className="max-w-full truncate font-mono text-[11px] text-sumi-600">
                {streamPath}
              </div>
            </div>
            <p className="mb-3 text-xs text-sumi-500">{controlDetail}</p>
            <div className="space-y-3">
              {controlEvents.length === 0 ? (
                <div className="text-sm text-sumi-500">No interrupts or approvals in snapshot.</div>
              ) : (
                controlEvents.map((event) => {
                  const actionOptions = runtimeControlActionOptions(event);
                  const activeAction =
                    controlActionState?.eventId === event.event_id
                      ? controlActionState
                      : null;
                  const actionBusy = activeAction?.status === "running";

                  return (
                    <div key={event.event_id} className="border-b border-sumi-700/40 pb-3 last:border-0 last:pb-0">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="text-sm text-sumi-200">{event.event_name}</div>
                      <span className={`rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-[0.12em] ${badgeClasses(event.status === "pending" ? "warn" : "ok")}`}>
                        {event.status}
                      </span>
                    </div>
                    <div className="mt-1 font-mono text-xs text-sumi-500">
                      {event.interrupt_id || event.approval_id || event.event_id}
                    </div>
                    <div className="mt-1 text-xs text-sumi-500">
                      {event.control_type} · {event.agent_id || "no-agent"}
                    </div>
                    {actionOptions.length > 0 ? (
                      <div className="mt-3 flex flex-wrap items-center gap-2">
                        {actionOptions.map((option) => (
                          <button
                            key={option.action}
                            type="button"
                            aria-label={option.title}
                            title={option.title}
                            disabled={actionBusy}
                            onClick={() => {
                              void onControlAction(event, option.action);
                            }}
                            className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-sumi-600/60 bg-sumi-900/70 text-sumi-200 transition-colors hover:border-aozora/50 hover:text-aozora disabled:cursor-not-allowed disabled:opacity-45"
                          >
                            <RuntimeControlActionIcon action={option.action} />
                            <span className="sr-only">{option.label}</span>
                          </button>
                        ))}
                      </div>
                    ) : null}
                    {activeAction ? (
                      <div
                        className={`mt-2 text-xs ${
                          activeAction.status === "error"
                            ? "text-red-300"
                            : activeAction.status === "ok"
                              ? "text-emerald-300"
                              : "text-sumi-400"
                        }`}
                      >
                        {activeAction.message}
                      </div>
                    ) : null}
                  </div>
                  );
                })
              )}
            </div>
          </div>
        </div>
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-2">
        <div className="rounded-xl border border-sumi-700/40 bg-sumi-800/30 p-4">
          <div className="mb-3 text-xs uppercase tracking-[0.16em] text-sumi-500">
            Assistants & Configurations
          </div>
          <p className="mb-3 text-xs text-sumi-500">{assistantsDetail}</p>
          <div className="space-y-3">
            {assistantRows.length === 0 ? (
              <div className="text-sm text-sumi-500">No assistants in runtime snapshot.</div>
            ) : (
              assistantRows.map((assistant) => (
                <div key={assistant.assistant_id} className="border-b border-sumi-700/40 pb-3 last:border-0 last:pb-0">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="text-sm text-sumi-200">{assistant.name}</div>
                    <span className={`rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-[0.12em] ${badgeClasses(assistant.active_run_count > 0 ? "ok" : "muted")}`}>
                      {assistant.active_run_count} active
                    </span>
                  </div>
                  <div className="mt-1 font-mono text-xs text-sumi-500">
                    {assistant.assistant_id}
                  </div>
                  <div className="mt-1 text-xs text-sumi-500">
                    {assistant.configuration_ids.length} configs · {assistant.run_count} runs
                  </div>
                </div>
              ))
            )}
          </div>
          {configurationRows.length > 0 ? (
            <div className="mt-4 border-t border-sumi-700/40 pt-3">
              {configurationRows.map((configuration) => (
                <div key={configuration.configuration_id} className="mb-2 last:mb-0">
                  <div className="truncate font-mono text-xs text-sumi-400">
                    {configuration.configuration_id}
                  </div>
                  <div className="text-xs text-sumi-600">
                    {configuration.provider || "provider"} · {configuration.model || "model"} · {configuration.tool_count} tools
                  </div>
                </div>
              ))}
            </div>
          ) : null}
        </div>

        <div className="rounded-xl border border-sumi-700/40 bg-sumi-800/30 p-4">
          <div className="mb-3 text-xs uppercase tracking-[0.16em] text-sumi-500">
            Background & Cron
          </div>
          <p className="mb-3 text-xs text-sumi-500">{backgroundDetail}</p>
          <div className="space-y-3">
            {cronRows.length === 0 ? (
              <div className="text-sm text-sumi-500">No cron jobs in runtime snapshot.</div>
            ) : (
              cronRows.map((job) => (
                <div key={job.job_id} className="border-b border-sumi-700/40 pb-3 last:border-0 last:pb-0">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="text-sm text-sumi-200">{job.name}</div>
                    <span className={`rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-[0.12em] ${badgeClasses(job.enabled ? "ok" : "muted")}`}>
                      {job.enabled ? "enabled" : "disabled"}
                    </span>
                  </div>
                  <div className="mt-1 text-xs text-sumi-500">
                    {job.schedule_display || "unscheduled"} · {job.output_count} outputs
                  </div>
                  <div className="mt-1 truncate font-mono text-xs text-sumi-600">
                    {job.next_run_at || job.job_id}
                  </div>
                </div>
              ))
            )}
          </div>
          {backgroundRuns.length > 0 ? (
            <div className="mt-4 border-t border-sumi-700/40 pt-3">
              {backgroundRuns.map((run) => (
                <div key={run.run_id} className="mb-2 last:mb-0">
                  <div className="truncate font-mono text-xs text-sumi-400">
                    {run.run_id}
                  </div>
                  <div className="text-xs text-sumi-600">
                    {run.status} · {run.assigned_to || "unassigned"} · {run.cron_job_id || run.run_kind}
                  </div>
                </div>
              ))}
            </div>
          ) : null}
        </div>
      </div>
    </section>
  );
}

function RuntimeControlActionIcon({
  action,
}: {
  action: RuntimeControlActionKind;
}) {
  if (action === "approve") {
    return <Check className="h-4 w-4" aria-hidden="true" />;
  }
  if (action === "reject") {
    return <X className="h-4 w-4" aria-hidden="true" />;
  }
  return <RotateCcw className="h-4 w-4" aria-hidden="true" />;
}

function RuntimeCard({
  label,
  value,
  detail,
  badge,
}: {
  label: string;
  value: string;
  detail: string;
  badge: string;
}) {
  return (
    <div className="rounded-2xl border border-sumi-700/50 bg-sumi-900/60 p-4">
      <div className="text-xs uppercase tracking-[0.16em] text-sumi-500">{label}</div>
      <div className="mt-3 flex items-center gap-3">
        <span className={`rounded-full border px-2.5 py-1 text-[11px] font-medium uppercase tracking-[0.12em] ${badge}`}>
          {value}
        </span>
      </div>
      <p className="mt-3 text-sm text-sumi-400">{detail}</p>
    </div>
  );
}

function MiniStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-sumi-700/40 bg-sumi-800/30 p-4">
      <div className="text-xs uppercase tracking-[0.16em] text-sumi-500">{label}</div>
      <div className="mt-2 text-xl font-medium text-sumi-100">{value}</div>
    </div>
  );
}
