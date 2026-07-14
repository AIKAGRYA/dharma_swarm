"use client";

import Link from "next/link";
import {
  Activity,
  AlertTriangle,
  ArrowUpRight,
  Bot,
  Clock3,
  Inbox,
  RadioTower,
  Server,
} from "lucide-react";
import {
  deriveStreamEmptyState,
  formatEvidenceAge,
  inspectRfc3339Timestamp,
  type ActivityItem,
  type RuntimeTruthState,
} from "@/lib/a2aNodeModel";
import type { AgentOut, TaskOut } from "@/lib/types";
import {
  classifyFleetError,
  deriveFleetNodeTruth as deriveNodeTruth,
  type FleetNode,
} from "./a2aNodeFleet";
import styles from "./A2ANodeShell.module.css";

const truthPresentation: Record<
  RuntimeTruthState,
  { label: string; dot: string; text: string; surface: string }
> = {
  runtime: {
    label: "runtime truth",
    dot: "bg-rokusho",
    text: "text-rokusho",
    surface: "border-rokusho/25 bg-rokusho/[0.06]",
  },
  stale: {
    label: "stale evidence",
    dot: "bg-kinpaku",
    text: "text-kinpaku",
    surface: "border-kinpaku/25 bg-kinpaku/[0.06]",
  },
  unreachable: {
    label: "unreachable",
    dot: "bg-bengara",
    text: "text-bengara",
    surface: "border-bengara/30 bg-bengara/[0.07]",
  },
  unknown: {
    label: "truth unknown",
    dot: "bg-fuji",
    text: "text-fuji",
    surface: "border-fuji/20 bg-fuji/[0.05]",
  },
};

export function errorText(error: unknown): string {
  return error instanceof Error ? error.message : "The runtime API did not answer.";
}

export function ageFrom(timestamp: string, nowMs: number): string {
  const parsed = inspectRfc3339Timestamp(timestamp, nowMs);
  return formatEvidenceAge(
    parsed.valid ? nowMs - parsed.timestampMs : null,
  );
}

function TruthPill({ state }: { state: RuntimeTruthState }) {
  const presentation = truthPresentation[state];
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-1 text-xs font-semibold uppercase tracking-[0.12em] ${presentation.surface} ${presentation.text}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${presentation.dot}`} />
      {presentation.label}
    </span>
  );
}

export function PanelHeader({
  eyebrow,
  title,
  detail,
  action,
}: {
  eyebrow: string;
  title: string;
  detail: string;
  action?: { href: string; label: string };
}) {
  return (
    <header className="mb-4 flex items-end justify-between gap-4">
      <div className="min-w-0">
        <p className="font-mono text-xs font-semibold uppercase tracking-[0.18em] text-kitsurubami/75">
          {eyebrow}
        </p>
        <h1 className="mt-1 font-heading text-[1.4rem] font-semibold tracking-[-0.03em] text-torinoko">
          {title}
        </h1>
        <p className="mt-1 max-w-2xl text-xs leading-relaxed text-kitsurubami/75">
          {detail}
        </p>
      </div>
      {action ? (
        <Link
          href={action.href}
          prefetch={false}
          className="inline-flex min-h-9 shrink-0 items-center gap-1.5 rounded-full border border-sumi-700/45 bg-sumi-900/70 px-3 text-xs font-medium text-kitsurubami transition-colors hover:border-sumi-600 hover:text-torinoko"
          aria-label={action.label}
        >
          <span className="hidden sm:inline">{action.label}</span>
          <ArrowUpRight size={13} aria-hidden="true" />
        </Link>
      ) : null}
    </header>
  );
}

export function SurfaceMessage({
  kind,
  title,
  detail,
}: {
  kind: "empty" | "error" | "loading" | "unknown";
  title: string;
  detail: string;
}) {
  const Icon =
    kind === "error" || kind === "unknown"
      ? AlertTriangle
      : kind === "loading"
        ? Clock3
        : Inbox;
  const alert = kind === "error" || kind === "unknown";
  return (
    <div
      className={`rounded-2xl border px-4 py-5 ${
        kind === "error"
          ? "border-bengara/30 bg-bengara/[0.06]"
          : kind === "unknown"
            ? "border-fuji/35 bg-fuji/[0.07]"
          : "border-sumi-700/35 bg-sumi-900/55"
      }`}
      role={alert ? "alert" : "status"}
    >
      <div className="flex items-start gap-3">
        <Icon
          size={16}
          className={
            kind === "error"
              ? "mt-0.5 text-bengara"
              : kind === "unknown"
                ? "mt-0.5 text-fuji"
                : "mt-0.5 text-kitsurubami/75"
          }
          aria-hidden="true"
        />
        <div>
          <p
            className={`text-sm font-medium ${
              kind === "error"
                ? "text-bengara"
                : kind === "unknown"
                  ? "text-fuji"
                  : "text-torinoko"
            }`}
          >
            {title}
          </p>
          <p className="mt-1 text-xs leading-relaxed text-kitsurubami/75">{detail}</p>
        </div>
      </div>
    </div>
  );
}

function RemoteNodeCard({ node, nowMs }: { node: FleetNode; nowMs: number }) {
  const truth = deriveNodeTruth(node, nowMs);
  const agentUid =
    typeof node.metadata.agent_uid === "string"
      ? node.metadata.agent_uid
      : "identity not projected";

  return (
    <article className="rounded-2xl border border-sumi-700/35 bg-sumi-900/65 p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          <div className="grid h-9 w-9 shrink-0 place-items-center rounded-xl border border-sumi-700/35 bg-sumi-850 text-aozora">
            <Server size={16} aria-hidden="true" />
          </div>
          <div className="min-w-0">
            <h2 className="truncate text-sm font-semibold text-torinoko">{node.node_id}</h2>
            <p className="truncate font-mono text-xs text-kitsurubami/75">{agentUid}</p>
          </div>
        </div>
        <TruthPill state={truth.state} />
      </div>

      <dl className="mt-4 grid grid-cols-2 gap-2 text-xs">
        <div className="rounded-xl bg-sumi-950/55 px-3 py-2">
          <dt className="text-kitsurubami/75">Heartbeat</dt>
          <dd className="mt-0.5 font-medium text-kitsurubami">
            {formatEvidenceAge(truth.ageMs)}
          </dd>
        </div>
        <div className="rounded-xl bg-sumi-950/55 px-3 py-2">
          <dt className="text-kitsurubami/75">Registry status</dt>
          <dd className="mt-0.5 font-medium text-kitsurubami">{node.status || "unknown"}</dd>
        </div>
      </dl>

      <p className="mt-3 truncate text-xs text-kitsurubami/75">
        {node.endpoint || "Endpoint not advertised"}
      </p>
      <div className="mt-3 flex flex-wrap gap-1.5">
        {node.capabilities.length ? (
          node.capabilities.slice(0, 4).map((capability) => (
            <span
              key={capability}
              className="rounded-full border border-sumi-700/30 bg-sumi-950/45 px-2 py-1 text-xs text-kitsurubami/80"
            >
              {capability}
            </span>
          ))
        ) : (
          <span className="text-xs text-kitsurubami/75">No capabilities advertised</span>
        )}
        {node.capabilities.length > 4 ? (
          <span className="px-1 py-1 text-xs text-kitsurubami/75">
            +{node.capabilities.length - 4}
          </span>
        ) : null}
      </div>
    </article>
  );
}

function AgentCard({ agent }: { agent: AgentOut }) {
  const active = ["running", "active", "online"].includes(agent.status.toLowerCase());
  return (
    <article className="rounded-2xl border border-sumi-700/30 bg-sumi-900/45 p-4">
      <div className="flex items-start gap-3">
        <div className="grid h-9 w-9 shrink-0 place-items-center rounded-xl border border-sumi-700/30 bg-sumi-950/60 text-fuji">
          <Bot size={16} aria-hidden="true" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-3">
            <h2 className="truncate text-sm font-medium text-torinoko">
              {agent.display_name || agent.name}
            </h2>
            <span className="inline-flex shrink-0 items-center gap-1.5 text-xs uppercase tracking-wider text-kitsurubami/75">
              <span className={`h-1.5 w-1.5 rounded-full ${active ? "bg-rokusho" : "bg-sumi-600"}`} />
              {agent.status}
            </span>
          </div>
          <p className="mt-1 truncate text-xs text-kitsurubami/75">
            {agent.model_label || agent.model || agent.provider}
          </p>
          <p className="mt-3 line-clamp-2 text-xs leading-relaxed text-kitsurubami/80">
            {agent.current_task || `${agent.role || "Agent"} · no current task reported`}
          </p>
        </div>
      </div>
    </article>
  );
}

export function RosterPanel({
  nodes,
  agents,
  nowMs,
  fleetLoading,
  agentsLoading,
  fleetError,
  agentsError,
}: {
  nodes: FleetNode[];
  agents: AgentOut[];
  nowMs: number;
  fleetLoading: boolean;
  agentsLoading: boolean;
  fleetError: unknown;
  agentsError: unknown;
}) {
  const fleetFailure = fleetError ? classifyFleetError(fleetError) : null;

  return (
    <div>
      <PanelHeader
        eyebrow="Roster"
        title="Who is actually here"
        detail="Fleet heartbeat truth and the existing agent registry, composed without creating a second authority."
        action={{ href: "/dashboard/command-post", label: "Command post" }}
      />

      <section aria-labelledby="runtime-nodes-heading">
        <div className="mb-2 flex items-center justify-between">
          <h2 id="runtime-nodes-heading" className="text-xs font-semibold uppercase tracking-[0.14em] text-kitsurubami/75">
            Runtime nodes
          </h2>
          <span className="font-mono text-xs text-kitsurubami/75">{nodes.length} observed</span>
        </div>
        {fleetFailure ? (
          <SurfaceMessage
            kind={fleetFailure.truth === "unknown" ? "unknown" : "error"}
            title={fleetFailure.title}
            detail={errorText(fleetError)}
          />
        ) : fleetLoading ? (
          <SurfaceMessage kind="loading" title="Reading fleet presence" detail="Waiting for the raw /api/fleet/nodes projection." />
        ) : nodes.length ? (
          <div className="grid gap-2 md:grid-cols-2">
            {nodes.map((node) => <RemoteNodeCard key={node.node_id} node={node} nowMs={nowMs} />)}
          </div>
        ) : (
          <SurfaceMessage kind="empty" title="No fleet heartbeat evidence yet" detail="The registry answered cleanly, but it currently contains no projected nodes." />
        )}
      </section>

      <section className="mt-6" aria-labelledby="agent-registry-heading">
        <div className="mb-2 flex items-center justify-between">
          <h2 id="agent-registry-heading" className="text-xs font-semibold uppercase tracking-[0.14em] text-kitsurubami/75">
            Agent registry
          </h2>
          <span className="font-mono text-xs text-kitsurubami/75">{agents.length} known</span>
        </div>
        {agentsError ? (
          <SurfaceMessage kind="error" title="Agent registry unreachable" detail={errorText(agentsError)} />
        ) : agentsLoading ? (
          <SurfaceMessage kind="loading" title="Reading known agents" detail="Waiting for the existing /api/agents surface." />
        ) : agents.length ? (
          <div className="grid gap-2 md:grid-cols-2 lg:grid-cols-3">
            {agents.map((agent, index) => (
              <AgentCard key={`agent:${agent.id}:${index}`} agent={agent} />
            ))}
          </div>
        ) : (
          <SurfaceMessage kind="empty" title="No agents reported" detail="The registry is reachable and intentionally empty on this host." />
        )}
      </section>
    </div>
  );
}

const taskStatusClass: Record<string, string> = {
  running: "bg-kinpaku",
  active: "bg-kinpaku",
  completed: "bg-rokusho",
  done: "bg-rokusho",
  failed: "bg-bengara",
  blocked: "bg-bengara",
  pending: "bg-fuji",
};

export function TasksPanel({
  tasks,
  nowMs,
  isLoading,
  error,
}: {
  tasks: TaskOut[];
  nowMs: number;
  isLoading: boolean;
  error: unknown;
}) {
  return (
    <div>
      <PanelHeader
        eyebrow="Tasks"
        title="Work already in motion"
        detail="A compact, read-only window onto TaskBoard. Assignment and creation stay on the existing task surface."
        action={{ href: "/dashboard/tasks", label: "Open task board" }}
      />
      {error ? (
        <SurfaceMessage kind="error" title="TaskBoard unreachable" detail={errorText(error)} />
      ) : isLoading ? (
        <SurfaceMessage kind="loading" title="Reading TaskBoard" detail="Waiting for /api/commands/tasks." />
      ) : tasks.length ? (
        <div className="grid gap-2 md:grid-cols-2">
          {tasks.map((task, index) => (
            <article key={`task:${task.id}:${index}`} className="rounded-2xl border border-sumi-700/35 bg-sumi-900/60 p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h2 className="text-sm font-medium leading-snug text-torinoko">{task.title}</h2>
                  <p className="mt-2 line-clamp-2 text-xs leading-relaxed text-kitsurubami/75">
                    {task.description || "No description recorded."}
                  </p>
                </div>
                <span className="inline-flex shrink-0 items-center gap-1.5 rounded-full border border-sumi-700/35 px-2 py-1 text-xs uppercase tracking-wider text-kitsurubami/80">
                  <span className={`h-1.5 w-1.5 rounded-full ${taskStatusClass[task.status.toLowerCase()] ?? "bg-sumi-600"}`} />
                  {task.status}
                </span>
              </div>
              <div className="mt-4 flex items-center justify-between gap-3 text-xs text-kitsurubami/75">
                <span className="truncate">{task.assigned_to || "unassigned"} · {task.priority}</span>
                <time dateTime={task.updated_at} className="shrink-0">{ageFrom(task.updated_at, nowMs)}</time>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <SurfaceMessage kind="empty" title="The task rail is clear" detail="TaskBoard answered with no work on this host. Nothing has been synthesized locally." />
      )}
    </div>
  );
}

export function StreamPanel({
  activity,
  nowMs,
  isLoading,
  traceError,
  a2aError,
}: {
  activity: ActivityItem[];
  nowMs: number;
  isLoading: boolean;
  traceError: unknown;
  a2aError: unknown;
}) {
  const emptyState = deriveStreamEmptyState(!traceError, !a2aError);

  return (
    <div>
      <PanelHeader
        eyebrow="Stream"
        title="The conversation between systems"
        detail="Trace events and A2A evidence share one chronology. Malformed records remain visible as unknown evidence."
      />
      <div className="space-y-2">
        {traceError ? <SurfaceMessage kind="error" title="Trace activity unreachable" detail={errorText(traceError)} /> : null}
        {a2aError ? <SurfaceMessage kind="error" title="A2A receipt stream unreachable" detail={errorText(a2aError)} /> : null}
      </div>
      {isLoading && !activity.length ? (
        <div className="mt-2"><SurfaceMessage kind="loading" title="Listening for evidence" detail="Reading trace and A2A surfaces." /></div>
      ) : activity.length ? (
        <div className="relative mt-3 space-y-2 pl-5">
          <span className={styles.streamRail} aria-hidden="true" />
          {activity.map((item) => {
            const unknown = item.evidenceState === "unknown";
            const Icon = unknown ? AlertTriangle : item.source === "a2a" ? RadioTower : Activity;
            return (
              <article
                key={item.key}
                className={`relative rounded-2xl border p-4 ${
                  unknown
                    ? "border-bengara/40 bg-bengara/[0.08]"
                    : item.source === "a2a"
                      ? "ml-3 border-kinpaku/20 bg-kinpaku/[0.045]"
                      : "mr-3 border-sumi-700/35 bg-sumi-900/60"
                }`}
              >
                <span className={`absolute -left-[1.42rem] top-5 grid h-5 w-5 place-items-center rounded-full border bg-sumi-950 ${unknown ? "border-bengara/50 text-bengara" : "border-sumi-700 text-kitsurubami/75"}`}>
                  <Icon size={10} aria-hidden="true" />
                </span>
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className={`font-mono text-xs uppercase tracking-[0.14em] ${unknown ? "text-bengara" : "text-kitsurubami/75"}`}>
                      {unknown ? "Unknown evidence" : item.source === "a2a" ? "A2A send" : "Runtime trace"} · {item.actor}
                    </p>
                    <h2 className="mt-1 text-sm font-medium leading-snug text-torinoko">{item.title}</h2>
                    <p className={`mt-2 text-xs leading-relaxed ${unknown ? "text-bengara" : "text-kitsurubami/75"}`}>{item.detail}</p>
                  </div>
                  <time dateTime={item.timestamp ?? undefined} className="shrink-0 font-mono text-xs text-kitsurubami/75">
                    {item.timestampMs === null ? "time ?" : formatEvidenceAge(Math.max(0, nowMs - item.timestampMs))}
                  </time>
                </div>
              </article>
            );
          })}
        </div>
      ) : (
        <div className="mt-2">
          <SurfaceMessage
            kind={emptyState.state === "intentional-empty" ? "empty" : "error"}
            title={emptyState.title}
            detail={emptyState.detail}
          />
        </div>
      )}
    </div>
  );
}
