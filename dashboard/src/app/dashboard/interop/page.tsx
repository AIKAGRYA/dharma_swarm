"use client";

import { useMemo, useState, type FormEvent, type ReactNode } from "react";
import {
  Activity,
  CheckCircle2,
  Clock3,
  Inbox,
  Network,
  Radio,
  RefreshCcw,
  Send,
  SquareTerminal,
} from "lucide-react";
import { useInterop } from "@/hooks/useInterop";
import type {
  InteropAdapterOut,
  InteropEventOut,
  InteropTaskOut,
  InteropWorkerOut,
} from "@/lib/types";

type Tone = "ok" | "warn" | "idle" | "error";

export default function InteropDeskPage() {
  const {
    status,
    adapters,
    workers,
    tasks,
    events,
    mailboxCounts,
    isLoading,
    error,
    enqueueTask,
    isEnqueuing,
  } = useInterop();
  const readyAdapters = adapters.filter((adapter) => adapter.ready).length;
  const queuedCount = mailboxCounts.queued ?? 0;
  const activeWorkers = workers.filter((worker) => worker.status !== "offline").length;
  const totalWorkers = status?.worker_total_count ?? workers.length;
  const defaultRecipient = adapters[0]?.adapter_id ?? "codex-cli";

  return (
    <main className="space-y-5">
      <section className="glass-panel p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="space-y-2">
            <div className="flex items-center gap-3">
              <Network size={20} className="text-aozora" />
              <h1 className="font-heading text-2xl font-semibold text-torinoko">
                Agent Interop Desk
              </h1>
            </div>
            <div className="font-mono text-xs uppercase tracking-[0.16em] text-sumi-600">
              {status?.schema_version ?? (isLoading ? "loading" : "offline")}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Metric label="Adapters" value={`${readyAdapters}/${adapters.length}`} tone="ok" />
            <Metric label="Workers" value={String(activeWorkers)} tone={activeWorkers > 0 ? "ok" : "warn"} />
            <Metric label="Queued" value={String(queuedCount)} tone={queuedCount > 0 ? "warn" : "idle"} />
            <Metric label="Events" value={String(events.length)} tone="idle" />
          </div>
        </div>
      </section>

      {error && (
        <section className="rounded-xl border border-akabeni/35 bg-akabeni/10 p-4 text-sm text-akabeni">
          {error instanceof Error ? error.message : String(error)}
        </section>
      )}

      <section className="grid gap-5 xl:grid-cols-[minmax(0,1.15fr)_minmax(360px,0.85fr)]">
        <div className="space-y-5">
          <AdaptersPanel adapters={adapters} isLoading={isLoading} />
          <TasksPanel tasks={tasks} />
        </div>

        <div className="space-y-5">
          <MailboxPanel
            adapters={adapters}
            defaultRecipient={defaultRecipient}
            enqueueTask={enqueueTask}
            isEnqueuing={isEnqueuing}
          />
          <WorkersPanel workers={workers} activeWorkers={activeWorkers} totalWorkers={totalWorkers} />
          <EventsPanel events={events} />
        </div>
      </section>
    </main>
  );
}

function Metric({ label, value, tone }: { label: string; value: string; tone: Tone }) {
  return (
    <div className={`rounded-xl border px-4 py-3 ${toneClass(tone, "panel")}`}>
      <div className="font-mono text-[10px] uppercase tracking-[0.16em] text-sumi-600">
        {label}
      </div>
      <div className={`mt-1 font-heading text-xl font-semibold ${toneClass(tone, "text")}`}>
        {value}
      </div>
    </div>
  );
}

function AdaptersPanel({
  adapters,
  isLoading,
}: {
  adapters: InteropAdapterOut[];
  isLoading: boolean;
}) {
  return (
    <section className="glass-panel p-5">
      <PanelHeader icon={<Radio size={17} />} title="Adapters" detail={`${adapters.length} lanes`} />
      <div className="mt-4 overflow-hidden rounded-xl border border-sumi-700/30">
        <table className="w-full text-left text-sm">
          <thead className="bg-sumi-900/75 text-[10px] uppercase tracking-[0.16em] text-sumi-600">
            <tr>
              <th className="px-3 py-3 font-medium">Agent</th>
              <th className="px-3 py-3 font-medium">Transport</th>
              <th className="px-3 py-3 font-medium">Ready</th>
              <th className="px-3 py-3 font-medium">Capabilities</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-sumi-700/25">
            {isLoading && adapters.length === 0 ? (
              <tr>
                <td className="px-3 py-4 text-sumi-600" colSpan={4}>
                  Loading adapters...
                </td>
              </tr>
            ) : (
              adapters.map((adapter) => (
                <tr key={adapter.adapter_id} className="bg-sumi-850/35">
                  <td className="px-3 py-3">
                    <div className="font-medium text-torinoko">{adapter.label}</div>
                    <div className="font-mono text-[11px] text-sumi-600">{adapter.adapter_id}</div>
                  </td>
                  <td className="px-3 py-3">
                    <span className="rounded-md border border-sumi-700/30 bg-sumi-900/55 px-2 py-1 font-mono text-[11px] text-kitsurubami">
                      {adapter.transport}
                    </span>
                  </td>
                  <td className="px-3 py-3">
                    <StatusPill label={adapter.ready ? "ready" : "handoff"} tone={adapter.ready ? "ok" : "warn"} />
                  </td>
                  <td className="px-3 py-3 text-xs leading-5 text-sumi-500">
                    {adapter.capabilities.slice(0, 4).join(", ") || "none"}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function MailboxPanel({
  adapters,
  defaultRecipient,
  enqueueTask,
  isEnqueuing,
}: {
  adapters: InteropAdapterOut[];
  defaultRecipient: string;
  enqueueTask: ReturnType<typeof useInterop>["enqueueTask"];
  isEnqueuing: boolean;
}) {
  const [recipient, setRecipient] = useState(defaultRecipient);
  const [summary, setSummary] = useState("");
  const [body, setBody] = useState("");
  const [notice, setNotice] = useState("");

  const normalizedRecipient = recipient || defaultRecipient;

  async function submitTask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setNotice("");
    const cleanSummary = summary.trim();
    const cleanBody = body.trim();
    if (!normalizedRecipient || !cleanSummary || !cleanBody) {
      setNotice("Recipient, summary, and body are required.");
      return;
    }
    const result = await enqueueTask({
      recipient: normalizedRecipient,
      sender: "operator",
      summary: cleanSummary,
      body: cleanBody,
      metadata: { source: "dashboard.interop" },
    });
    if (result.status === "error") {
      setNotice(result.error || "Task enqueue failed.");
      return;
    }
    setSummary("");
    setBody("");
    setNotice(`Queued ${result.data.task_id}`);
  }

  return (
    <section className="glass-panel p-5">
      <PanelHeader icon={<Send size={17} />} title="Mailbox" detail={normalizedRecipient} />
      <form className="mt-4 space-y-3" onSubmit={submitTask}>
        <label className="block">
          <span className="mb-1 block font-mono text-[10px] uppercase tracking-[0.16em] text-sumi-600">
            Recipient
          </span>
          <select
            className="w-full rounded-lg border border-sumi-700/45 bg-sumi-900/80 px-3 py-2 text-sm text-torinoko outline-none focus:border-aozora"
            value={normalizedRecipient}
            onChange={(event) => setRecipient(event.target.value)}
          >
            {adapters.length === 0 && <option value={normalizedRecipient}>{normalizedRecipient}</option>}
            {adapters.map((adapter) => (
              <option key={adapter.adapter_id} value={adapter.adapter_id}>
                {adapter.label}
              </option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="mb-1 block font-mono text-[10px] uppercase tracking-[0.16em] text-sumi-600">
            Summary
          </span>
          <input
            className="w-full rounded-lg border border-sumi-700/45 bg-sumi-900/80 px-3 py-2 text-sm text-torinoko outline-none focus:border-aozora"
            value={summary}
            onChange={(event) => setSummary(event.target.value)}
            placeholder="Review the API health path"
          />
        </label>
        <label className="block">
          <span className="mb-1 block font-mono text-[10px] uppercase tracking-[0.16em] text-sumi-600">
            Body
          </span>
          <textarea
            className="min-h-[132px] w-full resize-y rounded-lg border border-sumi-700/45 bg-sumi-900/80 px-3 py-2 text-sm leading-6 text-torinoko outline-none focus:border-aozora"
            value={body}
            onChange={(event) => setBody(event.target.value)}
            placeholder="Describe the task, expected output, and any files to inspect."
          />
        </label>
        <div className="flex items-center justify-between gap-3">
          <button
            type="submit"
            disabled={isEnqueuing}
            className="inline-flex items-center gap-2 rounded-lg border border-aozora/45 bg-aozora/15 px-4 py-2 text-sm font-medium text-aozora transition hover:bg-aozora/25 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isEnqueuing ? <RefreshCcw size={16} className="animate-spin" /> : <Send size={16} />}
            Send
          </button>
          {notice && <span className="min-w-0 truncate text-xs text-sumi-500">{notice}</span>}
        </div>
      </form>
    </section>
  );
}

function WorkersPanel({
  workers,
  activeWorkers,
  totalWorkers,
}: {
  workers: InteropWorkerOut[];
  activeWorkers: number;
  totalWorkers: number;
}) {
  return (
    <section className="glass-panel p-5">
      <PanelHeader icon={<SquareTerminal size={17} />} title="Workers" detail={`${activeWorkers}/${totalWorkers} live`} />
      <div className="mt-4 space-y-2">
        {workers.length === 0 ? (
          <EmptyLine text="No worker heartbeats yet." />
        ) : (
          workers.map((worker) => (
            <div key={worker.worker_id} className="rounded-xl border border-sumi-700/30 bg-sumi-850/45 p-3">
              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <div className="truncate text-sm font-medium text-torinoko">{worker.worker_id}</div>
                  <div className="font-mono text-[11px] text-sumi-600">{worker.adapter_id}</div>
                </div>
                <StatusPill label={worker.status} tone={workerTone(worker.status)} />
              </div>
              <div className="mt-2 flex items-center gap-2 text-xs text-sumi-600">
                <Clock3 size={13} />
                {formatTime(worker.last_heartbeat)}
              </div>
            </div>
          ))
        )}
      </div>
    </section>
  );
}

function EventsPanel({ events }: { events: InteropEventOut[] }) {
  return (
    <section className="glass-panel p-5">
      <PanelHeader icon={<Activity size={17} />} title="Events" detail={`${events.length} recent`} />
      <div className="mt-4 space-y-2">
        {events.length === 0 ? (
          <EmptyLine text="No events yet." />
        ) : (
          events.slice(0, 8).map((event) => (
            <div key={event.event_id} className="rounded-xl border border-sumi-700/25 bg-sumi-900/45 p-3">
              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0 truncate text-sm text-kitsurubami">{event.summary}</div>
                <span className="shrink-0 font-mono text-[10px] uppercase tracking-[0.14em] text-sumi-600">
                  {event.event_type}
                </span>
              </div>
              <div className="mt-1 text-xs text-sumi-600">{formatTime(event.created_at)}</div>
            </div>
          ))
        )}
      </div>
    </section>
  );
}

function TasksPanel({ tasks }: { tasks: InteropTaskOut[] }) {
  const sortedTasks = useMemo(() => tasks.slice(0, 10), [tasks]);
  return (
    <section className="glass-panel p-5">
      <PanelHeader icon={<Inbox size={17} />} title="Recent Tasks" detail={`${tasks.length} shown`} />
      <div className="mt-4 overflow-hidden rounded-xl border border-sumi-700/30">
        <table className="w-full text-left text-sm">
          <thead className="bg-sumi-900/75 text-[10px] uppercase tracking-[0.16em] text-sumi-600">
            <tr>
              <th className="px-3 py-3 font-medium">Task</th>
              <th className="px-3 py-3 font-medium">Recipient</th>
              <th className="px-3 py-3 font-medium">Status</th>
              <th className="px-3 py-3 font-medium">Updated</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-sumi-700/25">
            {sortedTasks.length === 0 ? (
              <tr>
                <td className="px-3 py-4 text-sumi-600" colSpan={4}>
                  No interop tasks yet.
                </td>
              </tr>
            ) : (
              sortedTasks.map((task) => (
                <tr key={task.task_id} className="bg-sumi-850/35">
                  <td className="px-3 py-3">
                    <div className="max-w-[520px] truncate font-medium text-torinoko">
                      {task.summary}
                    </div>
                    <div className="font-mono text-[11px] text-sumi-600">{task.task_id}</div>
                  </td>
                  <td className="px-3 py-3 font-mono text-xs text-kitsurubami">{task.recipient}</td>
                  <td className="px-3 py-3">
                    <StatusPill label={task.status} tone={taskTone(task.status)} />
                  </td>
                  <td className="px-3 py-3 text-xs text-sumi-600">
                    {formatTime(task.responded_at || task.claimed_at || task.created_at)}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function PanelHeader({
  icon,
  title,
  detail,
}: {
  icon: ReactNode;
  title: string;
  detail: string;
}) {
  return (
    <div className="flex items-center justify-between gap-3">
      <div className="flex items-center gap-2 text-aozora">
        {icon}
        <h2 className="font-heading text-lg font-semibold text-torinoko">{title}</h2>
      </div>
      <div className="font-mono text-[10px] uppercase tracking-[0.16em] text-sumi-600">
        {detail}
      </div>
    </div>
  );
}

function StatusPill({ label, tone }: { label: string; tone: Tone }) {
  return (
    <span className={`inline-flex items-center gap-1 rounded-md border px-2 py-1 font-mono text-[11px] ${toneClass(tone, "panel")}`}>
      {tone === "ok" ? <CheckCircle2 size={12} /> : <span className="h-2 w-2 rounded-full bg-current" />}
      {label}
    </span>
  );
}

function EmptyLine({ text }: { text: string }) {
  return (
    <div className="rounded-xl border border-dashed border-sumi-700/30 bg-sumi-900/35 p-4 text-sm text-sumi-600">
      {text}
    </div>
  );
}

function taskTone(status: string): Tone {
  if (status === "responded") return "ok";
  if (status === "failed") return "error";
  if (status === "claimed") return "warn";
  return "idle";
}

function workerTone(status: string): Tone {
  if (status === "offline") return "error";
  if (status === "idle") return "ok";
  return "warn";
}

function toneClass(tone: Tone, target: "panel" | "text") {
  if (target === "text") {
    if (tone === "ok") return "text-rokusho";
    if (tone === "warn") return "text-ukon";
    if (tone === "error") return "text-akabeni";
    return "text-kitsurubami";
  }
  if (tone === "ok") return "border-rokusho/30 bg-rokusho/10 text-rokusho";
  if (tone === "warn") return "border-ukon/30 bg-ukon/10 text-ukon";
  if (tone === "error") return "border-akabeni/35 bg-akabeni/10 text-akabeni";
  return "border-sumi-700/35 bg-sumi-900/50 text-kitsurubami";
}

function formatTime(value?: string) {
  if (!value) return "not seen";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
