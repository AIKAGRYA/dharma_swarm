"use client";

import { FormEvent, useMemo, useState, useSyncExternalStore } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  CircleDashed,
  Eye,
  FlaskConical,
  RefreshCw,
  ShieldCheck,
  Workflow,
  XCircle,
} from "lucide-react";
import { isMissionIdentifier, useMissionControl } from "@/hooks/useMissionControl";
import type {
  MissionControlSnapshot,
  MissionControlTaskView,
} from "@/lib/types";

const DEFAULT_MISSION_ID = "fleet-advancement-20260826";

const PROTOTYPE_SNAPSHOT: MissionControlSnapshot = {
  mission: {
    mission_id: DEFAULT_MISSION_ID,
    session_id: "prototype:mission:fleet-advancement-20260826",
    title: "Fleet advancement",
    goal: "Wrap Mission Control, Fleet Hub, and HELM into a coherent operator experience.",
    operator_id: "prototype-fixture",
    status: "prototype",
    metadata: { provenance: "simulation" },
    created_at: "2026-08-26T00:00:00Z",
    updated_at: "2026-08-26T09:30:00Z",
  },
  tasks: [
    {
      task_id: "fleet-t01",
      mission_id: DEFAULT_MISSION_ID,
      title: "Fleet Hub tactile prototype",
      description: "Five-destination operator shell with explicit runtime provenance.",
      status: "review",
      priority: "high",
      assigned_to: "fleet-seat",
      result: "",
      metadata: {},
      created_at: "2026-08-26T00:20:00Z",
      updated_at: "2026-08-26T09:22:00Z",
    },
    {
      task_id: "fleet-t02",
      mission_id: DEFAULT_MISSION_ID,
      title: "HELM operator surface",
      description: "Terminal-first whole-organism seat with compact proof boundaries.",
      status: "running",
      priority: "high",
      assigned_to: "helm-seat",
      result: "",
      metadata: {},
      created_at: "2026-08-26T00:25:00Z",
      updated_at: "2026-08-26T09:18:00Z",
    },
    {
      task_id: "fleet-t03",
      mission_id: DEFAULT_MISSION_ID,
      title: "Mission Control Linear v1",
      description: "Typed mission membrane plus indigo-sumi cockpit.",
      status: "running",
      priority: "high",
      assigned_to: "mission-control-seat",
      result: "",
      metadata: {},
      created_at: "2026-08-26T00:30:00Z",
      updated_at: "2026-08-26T09:30:00Z",
    },
    {
      task_id: "fleet-t04",
      mission_id: DEFAULT_MISSION_ID,
      title: "Operator acceptance pass",
      description: "John sees and feels all three surfaces before runtime promotion.",
      status: "queued",
      priority: "high",
      assigned_to: "operator",
      result: "",
      metadata: {},
      created_at: "2026-08-26T00:35:00Z",
      updated_at: "2026-08-26T00:35:00Z",
    },
  ],
  attempts: [
    {
      attempt_id: "prototype-attempt-fleet-t02",
      mission_id: DEFAULT_MISSION_ID,
      session_id: "prototype:mission:fleet-advancement-20260826",
      task_id: "fleet-t02",
      claim_id: "prototype-claim-fleet-t02",
      assigned_to: "helm-seat",
      assigned_by: "prototype-fixture",
      status: "recorded_running",
      failure_code: "",
      idempotency_key: "prototype-only",
      metadata: { provenance: "simulation" },
      started_at: "2026-08-26T00:25:00Z",
      completed_at: null,
    },
    {
      attempt_id: "prototype-attempt-fleet-t03",
      mission_id: DEFAULT_MISSION_ID,
      session_id: "prototype:mission:fleet-advancement-20260826",
      task_id: "fleet-t03",
      claim_id: "prototype-claim-fleet-t03",
      assigned_to: "mission-control-seat",
      assigned_by: "prototype-fixture",
      status: "recorded_running",
      failure_code: "",
      idempotency_key: "prototype-only",
      metadata: { provenance: "simulation" },
      started_at: "2026-08-26T00:30:00Z",
      completed_at: null,
    },
  ],
  leases: [],
  receipts: [
    {
      receipt_id: "prototype-receipt-fleet-t01",
      mission_id: DEFAULT_MISSION_ID,
      task_id: "fleet-t01",
      attempt_id: "prototype-attempt-fleet-t01",
      agent_id: "fleet-seat",
      receipt_type: "prototype_evidence_placeholder",
      status: "simulated",
      idempotency_key: "prototype-only",
      payload: { provenance: "simulation", proves_completion: false },
      created_at: "2026-08-26T09:22:00Z",
    },
  ],
  reconciliation: "simulation_only",
  observed_at: "2026-08-26T09:30:00Z",
  authority: "TaskBoard+RuntimeStateStore",
  proves_executor_liveness: false,
};

type SourceKind = "observed" | "simulation" | "unavailable" | "loading";

function subscribeToLocation(): () => void {
  return () => undefined;
}

function browserLocationSearch(): string {
  return window.location.search;
}

function serverLocationSearch(): string {
  return "";
}

function statusTone(status: string): string {
  if (["done", "completed", "succeeded", "coherent"].includes(status)) return "text-[#7FB8A6]";
  if (["failed", "blocked", "expired"].includes(status)) return "text-[#D14B3A]";
  if (["review", "queued", "needs_action"].includes(status)) return "text-[#D8B44A]";
  if (["running", "claimed", "assigned", "recorded_running"].includes(status)) return "text-[#6FB0C4]";
  return "text-[#6B7694]";
}

function StatusGlyph({ status }: { status: string }) {
  const className = statusTone(status);
  if (["done", "completed", "succeeded", "coherent"].includes(status)) {
    return <CheckCircle2 size={15} className={className} aria-hidden />;
  }
  if (["failed", "blocked", "expired"].includes(status)) {
    return <XCircle size={15} className={className} aria-hidden />;
  }
  if (["review", "queued", "needs_action"].includes(status)) {
    return <AlertTriangle size={15} className={className} aria-hidden />;
  }
  return <CircleDashed size={15} className={className} aria-hidden />;
}

function SourceBadge({ source }: { source: SourceKind }) {
  const config = {
    observed: [Eye, "OBSERVED READ MODEL", "text-[#7FB8A6] bg-[#7FB8A6]/10"],
    simulation: [FlaskConical, "SIMULATION · NOT RUNTIME", "text-[#D8B44A] bg-[#D8B44A]/10"],
    unavailable: [AlertTriangle, "SOURCE UNAVAILABLE", "text-[#E0913C] bg-[#E0913C]/10"],
    loading: [RefreshCw, "READING BOUNDED SOURCE", "text-[#6FB0C4] bg-[#6FB0C4]/10"],
  } as const;
  const [Icon, label, className] = config[source];
  return (
    <span className={`inline-flex items-center gap-2 rounded-sm px-2.5 py-1.5 text-xs font-semibold tracking-[0.12em] ${className}`}>
      <Icon size={14} className={source === "loading" ? "animate-spin" : ""} /> {label}
    </span>
  );
}

function Metric({ label, value, note }: { label: string; value: string | number; note: string }) {
  return (
    <div className="min-h-[106px] rounded-sm bg-[#141B2E] px-4 py-3">
      <div className="font-mono text-xs uppercase tracking-[0.14em] text-[#6B7694]">{label}</div>
      <div className="mt-2 font-mono text-3xl font-semibold tabular-nums text-[#EDE8DC]">{value}</div>
      <div className="mt-2 text-xs leading-5 text-[#A9B2C7]">{note}</div>
    </div>
  );
}

function TaskRow({ task, receiptCount }: { task: MissionControlTaskView; receiptCount: number }) {
  return (
    <div className="grid gap-3 rounded-sm bg-[#141B2E] px-4 py-3 md:grid-cols-[minmax(0,1fr)_130px_118px] md:items-center">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <StatusGlyph status={task.status} />
          <span className="truncate font-medium text-[#EDE8DC]">{task.title}</span>
        </div>
        <div className="mt-1 truncate font-mono text-xs text-[#6B7694]">{task.task_id}</div>
      </div>
      <div>
        <div className={`font-mono text-xs font-semibold uppercase tracking-[0.1em] ${statusTone(task.status)}`}>
          {task.status.replaceAll("_", " ")}
        </div>
        <div className="mt-1 truncate text-xs text-[#A9B2C7]">{task.assigned_to || "unassigned"}</div>
      </div>
      <div className="font-mono text-xs text-[#A9B2C7] md:text-right">
        {receiptCount} receipt{receiptCount === 1 ? "" : "s"}
        <div className="mt-1 text-[#6B7694]">recorded state</div>
      </div>
    </div>
  );
}

export function MissionControlDeck() {
  const [missionId, setMissionId] = useState(DEFAULT_MISSION_ID);
  const [draftMissionId, setDraftMissionId] = useState(DEFAULT_MISSION_ID);
  const [simulationOverride, setSimulationOverride] = useState<boolean | null>(null);
  const locationSearch = useSyncExternalStore(
    subscribeToLocation,
    browserLocationSearch,
    serverLocationSearch,
  );
  const showSimulation = simulationOverride ?? new URLSearchParams(locationSearch).get("mc_demo") === "1";
  const { projection, sourceErrors, isLoading, error, refetch, enabled } = useMissionControl(
    missionId,
    !showSimulation,
  );

  const observed = !showSimulation && projection?.state === "observed" && projection.snapshot;
  const snapshot = showSimulation ? PROTOTYPE_SNAPSHOT : observed || null;
  const source: SourceKind = showSimulation
    ? "simulation"
    : isLoading
      ? "loading"
      : snapshot
        ? "observed"
        : "unavailable";
  const counts = snapshot
    ? {
        tasks: snapshot.tasks.length,
        attempts: snapshot.attempts.length,
        leases: snapshot.leases.length,
        receipts: snapshot.receipts.length,
      }
    : { tasks: "—", attempts: "—", leases: "—", receipts: "—" };
  const needsAction = useMemo(
    () => snapshot?.tasks.filter((task) => ["pending", "queued", "review", "blocked", "failed"].includes(task.status)) ?? [],
    [snapshot],
  );
  const receiptCounts = useMemo(() => {
    const result = new Map<string, number>();
    for (const receipt of snapshot?.receipts ?? []) {
      result.set(receipt.task_id, (result.get(receipt.task_id) ?? 0) + 1);
    }
    return result;
  }, [snapshot]);

  function submitMission(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalized = draftMissionId.trim();
    if (!isMissionIdentifier(normalized)) return;
    setMissionId(normalized);
    setSimulationOverride(false);
  }

  return (
    <section className="overflow-hidden rounded-sm bg-[#0A0E1A] text-[#EDE8DC] [font-family:'JetBrains_Mono',monospace]">
      <div className="h-1 bg-[linear-gradient(90deg,#6E96D6_0%,#6E96D6_36%,#D8B44A_36%,#D8B44A_43%,#2A3550_43%,#2A3550_100%)]" />
      <div className="p-4 sm:p-6">
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_420px]">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-3">
              <div className="text-xs font-semibold uppercase tracking-[0.22em] text-[#6E96D6]">
                Mandala Mission Control / Linear v1
              </div>
              <SourceBadge source={source} />
            </div>
            <h1 className="mt-5 max-w-4xl [font-family:'Baskerville','Iowan_Old_Style',serif] text-4xl leading-[1.05] tracking-[-0.02em] text-[#EDE8DC] sm:text-6xl">
              {snapshot?.mission.title ?? "Bounded mission view"}
            </h1>
            <p className="mt-4 max-w-3xl text-sm leading-6 text-[#A9B2C7]">
              {snapshot?.mission.goal ?? "No canonical snapshot was observed. Inject a read-only provider or enter the clearly labelled tactile simulation."}
            </p>
            <div className="mt-5 flex flex-wrap gap-x-5 gap-y-2 text-xs text-[#6B7694]">
              <span>AUTHORITY <strong className="text-[#A9B2C7]">TaskBoard + RuntimeStateStore</strong></span>
              <span>LIVENESS <strong className="text-[#D8B44A]">NOT PROVEN</strong></span>
              <span>MODE <strong className="text-[#A9B2C7]">READ ONLY</strong></span>
            </div>
          </div>

          <div className="rounded-sm bg-[#141B2E] p-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="text-xs uppercase tracking-[0.16em] text-[#6B7694]">Mission focus</div>
                <div className="mt-1 text-xs text-[#A9B2C7]">Explicit identity · no fleet discovery</div>
              </div>
              <button
                type="button"
                onClick={() => void refetch()}
                disabled={!enabled || showSimulation || isLoading}
                className="rounded-sm bg-[#1E2840] p-2 text-[#6E96D6] transition hover:bg-[#2A3550] disabled:opacity-35"
                aria-label="Refresh mission projection"
              >
                <RefreshCw size={16} className={isLoading ? "animate-spin" : ""} />
              </button>
            </div>
            <form onSubmit={submitMission} className="mt-4 flex gap-2">
              <input
                value={draftMissionId}
                onChange={(event) => setDraftMissionId(event.target.value)}
                aria-label="Mission identifier"
                className="min-w-0 flex-1 rounded-sm bg-[#0A0E1A] px-3 py-2.5 text-xs text-[#EDE8DC] outline-none ring-1 ring-[#2A3550] focus:ring-[#6E96D6]"
              />
              <button
                type="submit"
                disabled={!isMissionIdentifier(draftMissionId.trim())}
                className="rounded-sm bg-[#6E96D6] px-3 py-2.5 text-xs font-semibold text-[#0A0E1A] transition hover:bg-[#8AAAE0] disabled:bg-[#2A3550] disabled:text-[#6B7694]"
              >
                Observe
              </button>
            </form>
            <div className="mt-3 grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => setSimulationOverride(false)}
                className={`rounded-sm px-3 py-2 text-xs font-semibold ${!showSimulation ? "bg-[#1E2840] text-[#6E96D6]" : "bg-[#0A0E1A] text-[#6B7694]"}`}
              >
                Live projection
              </button>
              <button
                type="button"
                onClick={() => setSimulationOverride(true)}
                className={`rounded-sm px-3 py-2 text-xs font-semibold ${showSimulation ? "bg-[#D8B44A]/15 text-[#D8B44A]" : "bg-[#0A0E1A] text-[#6B7694]"}`}
              >
                Tactile simulation
              </button>
            </div>
          </div>
        </div>

        <div className="mt-6 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
          <Metric label="Tasks" value={counts.tasks} note="Mission-scoped board rows" />
          <Metric label="Attempts" value={counts.attempts} note="Recorded execution lineage" />
          <Metric label="Leases" value={counts.leases} note="Claims, never process proof" />
          <Metric label="Receipts" value={counts.receipts} note="Evidence, never promotion" />
        </div>

        {snapshot ? (
          <div className="mt-6 grid gap-4 xl:grid-cols-[minmax(0,1.35fr)_minmax(300px,0.65fr)]">
            <div className="rounded-sm bg-[#101626] p-3 sm:p-4">
              <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
                <div>
                  <div className="text-xs uppercase tracking-[0.16em] text-[#6B7694]">Mission sequence</div>
                  <h2 className="mt-1 [font-family:'Baskerville','Iowan_Old_Style',serif] text-2xl">Recorded task states</h2>
                </div>
                <div className="text-xs text-[#6B7694]">{snapshot.reconciliation.replaceAll("_", " ")}</div>
              </div>
              <div className="space-y-2">
                {snapshot.tasks.map((task) => (
                  <TaskRow key={task.task_id} task={task} receiptCount={receiptCounts.get(task.task_id) ?? 0} />
                ))}
                {!snapshot.tasks.length ? (
                  <div className="rounded-sm bg-[#141B2E] px-4 py-8 text-center text-sm text-[#6B7694]">
                    Mission observed with no TaskBoard rows.
                  </div>
                ) : null}
              </div>
            </div>

            <aside className="rounded-sm bg-[#141B2E] p-4">
              <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em] text-[#D8B44A]">
                <AlertTriangle size={15} /> Needs-Action
              </div>
              <div className="mt-4 space-y-3">
                {needsAction.map((task) => (
                  <div key={task.task_id} className="bg-[#0A0E1A] px-3 py-3">
                    <div className="flex items-start gap-2 text-sm text-[#EDE8DC]">
                      <StatusGlyph status={task.status} />
                      <span>{task.title}</span>
                    </div>
                    <div className="mt-2 text-xs leading-5 text-[#6B7694]">
                      {task.status === "review" ? "Review recorded prototype evidence." : task.status === "queued" ? "Wait for an explicit operator acceptance pass." : "Inspect the owner evidence before action."}
                    </div>
                  </div>
                ))}
                {!needsAction.length ? (
                  <div className="bg-[#0A0E1A] px-3 py-6 text-center text-xs text-[#6B7694]">
                    No recorded task currently maps to this lane.
                  </div>
                ) : null}
              </div>
            </aside>
          </div>
        ) : (
          <div className="mt-6 grid min-h-[250px] place-items-center rounded-sm bg-[#141B2E] px-5 py-10 text-center">
            <div className="max-w-xl">
              <Workflow size={30} className="mx-auto text-[#6B7694]" />
              <h2 className="mt-4 [font-family:'Baskerville','Iowan_Old_Style',serif] text-2xl">No mission state invented</h2>
              <p className="mt-3 text-sm leading-6 text-[#A9B2C7]">
                {error
                  ? "The bounded read failed its claim boundary."
                  : sourceErrors[0]?.error ?? "This host has no injected Mission Control read provider."}
              </p>
              <button
                type="button"
                onClick={() => setSimulationOverride(true)}
                className="mt-5 rounded-sm bg-[#D8B44A] px-4 py-2.5 text-xs font-semibold text-[#0A0E1A]"
              >
                Enter labelled simulation
              </button>
            </div>
          </div>
        )}

        <div className="mt-6 grid gap-3 rounded-sm bg-[#101626] p-4 text-xs text-[#A9B2C7] md:grid-cols-4">
          <div className="flex items-start gap-2"><ShieldCheck size={15} className="mt-0.5 text-[#7FB8A6]" /><span>Owner custody stays with TaskBoard + RuntimeStateStore.</span></div>
          <div className="flex items-start gap-2"><Eye size={15} className="mt-0.5 text-[#6E96D6]" /><span>{showSimulation ? "Fixture timestamp" : "Observed at"}: {snapshot?.observed_at ?? "unavailable"}</span></div>
          <div className="flex items-start gap-2"><AlertTriangle size={15} className="mt-0.5 text-[#D8B44A]" /><span>Executor liveness is never inferred from this view.</span></div>
          <div className="flex items-start gap-2"><FlaskConical size={15} className="mt-0.5 text-[#8A7AB0]" /><span>Simulation is visual-only and excluded from runtime claims.</span></div>
        </div>
      </div>
    </section>
  );
}
