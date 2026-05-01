"use client";

/**
 * DHARMA COMMAND -- Tasks page (L2).
 * Canonical task board for operator, campaign, and swarm work.
 */

import { useState, type ReactNode } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Layers3, Plus, Sparkles, UserRound, X } from "lucide-react";
import { useCreateTask, useTasks } from "@/hooks/useTasks";
import {
  getTaskCampaign,
  getTaskDomain,
  getTaskKind,
  getTaskLane,
  getTaskOrigin,
  getTaskSource,
  groupTasksByLane,
  summarizeOrigins,
  taskLanes,
} from "@/lib/taskBoard";
import { colors } from "@/lib/theme";
import type { TaskOut } from "@/lib/types";
import { timeAgo } from "@/lib/utils";

const statusColors: Record<string, string> = {
  pending: colors.kinpaku,
  assigned: colors.fuji,
  running: colors.aozora,
  done: colors.rokusho,
  completed: colors.rokusho,
  failed: colors.bengara,
  cancelled: colors.sumi[600],
};

const priorityConfig: Record<string, { label: string; color: string }> = {
  low: { label: "Low", color: colors.fuji },
  normal: { label: "Normal", color: colors.torinoko },
  high: { label: "High", color: colors.kinpaku },
  urgent: { label: "Urgent", color: colors.bengara },
};

const intentOptions = [
  { value: "operator_proposal", label: "Operator Proposal" },
  { value: "mission_slice", label: "Mission Slice" },
  { value: "follow_up", label: "Follow-up" },
  { value: "overnight_seed", label: "Overnight Seed" },
] as const;

function getPriority(priority: string) {
  return priorityConfig[priority] ?? priorityConfig.normal;
}

function compactText(value: string | null | undefined, max = 140): string {
  const text = (value ?? "").trim();
  if (!text) return "";
  if (text.length <= max) return text;
  return `${text.slice(0, max - 1)}…`;
}

function cleanMetadata(
  input: Record<string, string | undefined>,
): Record<string, string> {
  return Object.fromEntries(
    Object.entries(input).filter(([, value]) => Boolean(value && value.trim())),
  ) as Record<string, string>;
}

function StatCard({
  title,
  value,
  detail,
  accent,
}: {
  title: string;
  value: string;
  detail: string;
  accent: string;
}) {
  return (
    <div
      className="rounded-xl border border-sumi-700/30 bg-sumi-950/45 p-4"
      style={{
        boxShadow: `0 0 0 1px color-mix(in srgb, ${accent} 12%, transparent)`,
      }}
    >
      <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-sumi-600">
        {title}
      </p>
      <p className="mt-2 font-mono text-2xl font-bold" style={{ color: accent }}>
        {value}
      </p>
      <p className="mt-1 text-xs text-sumi-600">{detail}</p>
    </div>
  );
}

export default function TasksPage() {
  const { tasks, isLoading } = useTasks();
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [originFilter, setOriginFilter] = useState("all");

  const originSummary = summarizeOrigins(tasks);
  const filteredTasks =
    originFilter === "all"
      ? tasks
      : tasks.filter((task) => getTaskOrigin(task).key === originFilter);
  const grouped = groupTasksByLane(filteredTasks);

  const assignedCount = tasks.filter((task) => Boolean(task.assigned_to)).length;
  const operatorCount = tasks.filter((task) => getTaskOrigin(task).key === "operator").length;
  const campaignCount = tasks.filter((task) => Boolean(getTaskCampaign(task))).length;
  const activeCount = tasks.filter((task) => getTaskLane(task) === "active").length;

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h1 className="glow-botan font-heading text-2xl font-bold tracking-tight text-botan">
            Canonical Task Board
          </h1>
          <p className="mt-1 max-w-3xl text-sm text-sumi-600">
            One visible work surface over the shared task ledger. Operator tasks,
            campaign slices, overnight seeds, and swarm-generated work all show up
            here through the same canonical record.
          </p>
        </div>
        <button
          onClick={() => setShowCreateDialog(true)}
          className="inline-flex items-center gap-2 self-start rounded-lg border border-botan/30 bg-botan/10 px-4 py-2 text-sm font-medium text-botan transition-all hover:border-botan/50 hover:bg-botan/20"
        >
          <Plus size={14} />
          Add Operator Task
        </button>
      </div>

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <StatCard
          title="Board Tasks"
          value={String(tasks.length)}
          detail="All visible tasks on the canonical board."
          accent={colors.torinoko}
        />
        <StatCard
          title="Active Now"
          value={String(activeCount)}
          detail="Tasks currently in the running lane."
          accent={colors.aozora}
        />
        <StatCard
          title="Mission Linked"
          value={String(campaignCount)}
          detail="Tasks carrying campaign or mission metadata."
          accent={colors.kinpaku}
        />
        <StatCard
          title="Operator Added"
          value={String(operatorCount)}
          detail={`${assignedCount} task${assignedCount === 1 ? "" : "s"} already pointed at an owner.`}
          accent={colors.botan}
        />
      </div>

      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35 }}
        className="glass-panel p-5"
      >
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-sumi-600">
              Origin Mix
            </p>
            <p className="mt-1 text-sm text-kitsurubami">
              Filter the board by where work is coming from.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <FilterChip
              active={originFilter === "all"}
              color={colors.torinoko}
              label={`All (${tasks.length})`}
              onClick={() => setOriginFilter("all")}
            />
            {originSummary.map((origin) => (
              <FilterChip
                key={origin.key}
                active={originFilter === origin.key}
                color={origin.color}
                label={`${origin.label} (${origin.count})`}
                onClick={() => setOriginFilter(origin.key)}
              />
            ))}
          </div>
        </div>
      </motion.div>

      <div className="grid gap-4 xl:grid-cols-4">
        {taskLanes.map((lane, index) => (
          <motion.section
            key={lane.id}
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35, delay: index * 0.06 }}
            className="glass-panel flex min-h-[420px] flex-col p-4"
            style={{
              boxShadow: `0 0 0 1px color-mix(in srgb, ${lane.accent} 10%, transparent)`,
            }}
          >
            <div className="mb-4 flex items-start justify-between gap-3">
              <div>
                <div className="flex items-center gap-2">
                  <span
                    className="inline-block h-2.5 w-2.5 rounded-full"
                    style={{ backgroundColor: lane.accent }}
                  />
                  <h2 className="font-heading text-lg font-semibold text-torinoko">
                    {lane.title}
                  </h2>
                </div>
                <p className="mt-1 text-xs text-sumi-600">{lane.description}</p>
              </div>
              <span
                className="rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em]"
                style={{
                  color: lane.accent,
                  backgroundColor: `color-mix(in srgb, ${lane.accent} 14%, transparent)`,
                }}
              >
                {grouped[lane.id].length}
              </span>
            </div>

            <div className="space-y-3">
              {isLoading ? (
                <div className="glass-panel-subtle flex items-center justify-center py-10 text-sm text-sumi-600">
                  Loading tasks...
                </div>
              ) : grouped[lane.id].length === 0 ? (
                <div className="glass-panel-subtle flex min-h-[220px] items-center justify-center px-4 py-10 text-center text-sm text-sumi-600">
                  {originFilter === "all"
                    ? lane.emptyLabel
                    : `No ${originFilter} tasks in this lane.`}
                </div>
              ) : (
                grouped[lane.id].map((task, taskIndex) => (
                  <TaskCard key={task.id} task={task} index={taskIndex} />
                ))
              )}
            </div>
          </motion.section>
        ))}
      </div>

      <AnimatePresence>
        {showCreateDialog && (
          <CreateTaskDialog onClose={() => setShowCreateDialog(false)} />
        )}
      </AnimatePresence>
    </div>
  );
}

function FilterChip({
  active,
  color,
  label,
  onClick,
}: {
  active: boolean;
  color: string;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="rounded-full border px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.12em] transition-all"
      style={{
        color: active ? color : colors.sumi[600],
        borderColor: active
          ? `color-mix(in srgb, ${color} 36%, transparent)`
          : "color-mix(in srgb, #383A44 30%, transparent)",
        backgroundColor: active
          ? `color-mix(in srgb, ${color} 12%, transparent)`
          : "transparent",
      }}
    >
      {label}
    </button>
  );
}

function TaskCard({ task, index }: { task: TaskOut; index: number }) {
  const origin = getTaskOrigin(task);
  const campaign = getTaskCampaign(task);
  const domain = getTaskDomain(task);
  const source = getTaskSource(task);
  const kind = getTaskKind(task);
  const statusColor = statusColors[task.status.toLowerCase()] ?? colors.sumi[600];
  const priority = getPriority(task.priority);

  return (
    <motion.article
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, delay: index * 0.04 }}
      className="rounded-xl border border-sumi-700/30 bg-sumi-950/45 p-4"
      style={{
        boxShadow: `0 0 0 1px color-mix(in srgb, ${origin.color} 9%, transparent)`,
      }}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="font-medium text-torinoko">{task.title}</p>
          {task.description && (
            <p className="mt-2 text-sm text-kitsurubami">
              {compactText(task.description)}
            </p>
          )}
        </div>
        <span
          className="shrink-0 rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em]"
          style={{
            color: priority.color,
            backgroundColor: `color-mix(in srgb, ${priority.color} 12%, transparent)`,
          }}
        >
          {priority.label}
        </span>
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        <Tag color={origin.color} label={origin.label} />
        <Tag color={statusColor} label={task.status} />
        {campaign && <Tag color={colors.kinpaku} label={campaign} />}
        {domain && <Tag color={colors.kitsurubami} label={domain} />}
        {kind && <Tag color={colors.fuji} label={kind.replaceAll("_", " ")} />}
      </div>

      <div className="mt-4 flex flex-wrap gap-4 text-xs text-sumi-600">
        <MetaLine
          icon={<UserRound size={12} />}
          label={task.assigned_to ? `Owner ${task.assigned_to}` : `By ${task.created_by}`}
        />
        <MetaLine
          icon={<Layers3 size={12} />}
          label={source || "No source metadata"}
        />
        <MetaLine
          icon={<Sparkles size={12} />}
          label={timeAgo(task.updated_at)}
        />
      </div>

      {task.result && (
        <div className="mt-4 rounded-lg border border-sumi-700/20 bg-sumi-900/45 p-3">
          <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-sumi-600">
            Latest Result
          </p>
          <p className="mt-1 text-sm text-kitsurubami">{compactText(task.result, 180)}</p>
        </div>
      )}
    </motion.article>
  );
}

function MetaLine({
  icon,
  label,
}: {
  icon: ReactNode;
  label: string;
}) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="text-sumi-600">{icon}</span>
      <span>{label}</span>
    </span>
  );
}

function Tag({ color, label }: { color: string; label: string }) {
  return (
    <span
      className="inline-flex rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em]"
      style={{
        color,
        backgroundColor: `color-mix(in srgb, ${color} 12%, transparent)`,
        border: `1px solid color-mix(in srgb, ${color} 22%, transparent)`,
      }}
    >
      {label}
    </span>
  );
}

function CreateTaskDialog({ onClose }: { onClose: () => void }) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState("normal");
  const [assignedTo, setAssignedTo] = useState("");
  const [campaignId, setCampaignId] = useState("");
  const [domain, setDomain] = useState("");
  const [taskKind, setTaskKind] = useState("operator_proposal");
  const createTask = useCreateTask();

  const handleSubmit = () => {
    if (!title.trim()) return;
    createTask.mutate(
      {
        title: title.trim(),
        description: description.trim() || undefined,
        priority,
        assigned_to: assignedTo.trim() || undefined,
        created_by: "operator",
        metadata: cleanMetadata({
          source: "operator.dashboard",
          task_kind: taskKind,
          campaign_id: campaignId,
          domain,
          operator_surface: "dashboard.tasks",
        }),
      },
      { onSuccess: () => onClose() },
    );
  };

  return (
    <>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
        className="fixed inset-0 z-50 bg-black/55 backdrop-blur-sm"
      />
      <motion.div
        initial={{ opacity: 0, scale: 0.96, y: 18 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.96, y: 18 }}
        transition={{ type: "spring", damping: 24, stiffness: 280 }}
        className="fixed left-1/2 top-1/2 z-50 w-[min(720px,92vw)] -translate-x-1/2 -translate-y-1/2 rounded-xl border border-sumi-700/40 bg-sumi-900/95 p-6 shadow-2xl backdrop-blur-md"
      >
        <div className="mb-5 flex items-start justify-between gap-4">
          <div>
            <h2 className="font-heading text-lg font-bold text-torinoko">
              Add Operator Task
            </h2>
            <p className="mt-1 text-sm text-sumi-600">
              This writes directly into the canonical board with operator provenance.
            </p>
          </div>
          <button
            onClick={onClose}
            className="rounded p-1 text-sumi-600 hover:text-torinoko"
            aria-label="Close"
          >
            <X size={16} />
          </button>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <div className="md:col-span-2">
            <label className="mb-1.5 block text-[10px] font-semibold uppercase tracking-[0.12em] text-kitsurubami">
              Title
            </label>
            <input
              type="text"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="What should the swarm move next?"
              className="w-full rounded-lg border border-sumi-700/40 bg-sumi-850 px-3 py-2 text-sm text-torinoko placeholder-sumi-600 outline-none transition-colors focus:border-botan/50"
            />
          </div>

          <div className="md:col-span-2">
            <label className="mb-1.5 block text-[10px] font-semibold uppercase tracking-[0.12em] text-kitsurubami">
              Description
            </label>
            <textarea
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="Describe the deliverable, evidence, or next action."
              rows={4}
              className="w-full resize-none rounded-lg border border-sumi-700/40 bg-sumi-850 px-3 py-2 text-sm text-torinoko placeholder-sumi-600 outline-none transition-colors focus:border-botan/50"
            />
          </div>

          <div>
            <label className="mb-1.5 block text-[10px] font-semibold uppercase tracking-[0.12em] text-kitsurubami">
              Priority
            </label>
            <div className="grid grid-cols-2 gap-2">
              {Object.entries(priorityConfig).map(([value, config]) => (
                <button
                  key={value}
                  onClick={() => setPriority(value)}
                  className="rounded-lg border px-3 py-2 text-xs font-medium transition-all"
                  style={{
                    color: priority === value ? config.color : colors.sumi[600],
                    borderColor:
                      priority === value
                        ? `color-mix(in srgb, ${config.color} 34%, transparent)`
                        : "color-mix(in srgb, #383A44 35%, transparent)",
                    backgroundColor:
                      priority === value
                        ? `color-mix(in srgb, ${config.color} 12%, transparent)`
                        : "transparent",
                  }}
                >
                  {config.label}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="mb-1.5 block text-[10px] font-semibold uppercase tracking-[0.12em] text-kitsurubami">
              Intent
            </label>
            <select
              value={taskKind}
              onChange={(event) => setTaskKind(event.target.value)}
              className="w-full rounded-lg border border-sumi-700/40 bg-sumi-850 px-3 py-2 text-sm text-torinoko outline-none transition-colors focus:border-botan/50"
            >
              {intentOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="mb-1.5 block text-[10px] font-semibold uppercase tracking-[0.12em] text-kitsurubami">
              Owner / Agent Hint
            </label>
            <input
              type="text"
              value={assignedTo}
              onChange={(event) => setAssignedTo(event.target.value)}
              placeholder="Optional agent or owner"
              className="w-full rounded-lg border border-sumi-700/40 bg-sumi-850 px-3 py-2 text-sm text-torinoko placeholder-sumi-600 outline-none transition-colors focus:border-botan/50"
            />
          </div>

          <div>
            <label className="mb-1.5 block text-[10px] font-semibold uppercase tracking-[0.12em] text-kitsurubami">
              Campaign / Mission
            </label>
            <input
              type="text"
              value={campaignId}
              onChange={(event) => setCampaignId(event.target.value)}
              placeholder="startup_world_facing"
              className="w-full rounded-lg border border-sumi-700/40 bg-sumi-850 px-3 py-2 text-sm text-torinoko placeholder-sumi-600 outline-none transition-colors focus:border-botan/50"
            />
          </div>

          <div className="md:col-span-2">
            <label className="mb-1.5 block text-[10px] font-semibold uppercase tracking-[0.12em] text-kitsurubami">
              Domain
            </label>
            <input
              type="text"
              value={domain}
              onChange={(event) => setDomain(event.target.value)}
              placeholder="artifact_publication, research, productization..."
              className="w-full rounded-lg border border-sumi-700/40 bg-sumi-850 px-3 py-2 text-sm text-torinoko placeholder-sumi-600 outline-none transition-colors focus:border-botan/50"
            />
          </div>
        </div>

        <div className="mt-6 flex items-center justify-between gap-3">
          <p className="text-xs text-sumi-600">
            Source is stored as <span className="font-mono text-kitsurubami">operator.dashboard</span>.
          </p>
          <div className="flex gap-3">
            <button
              onClick={onClose}
              className="rounded-lg px-4 py-2 text-sm text-sumi-600 hover:text-torinoko"
            >
              Cancel
            </button>
            <button
              onClick={handleSubmit}
              disabled={!title.trim() || createTask.isPending}
              className="inline-flex items-center gap-2 rounded-lg bg-botan/20 px-4 py-2 text-sm font-medium text-botan transition-all hover:bg-botan/30 disabled:opacity-40"
            >
              <Plus size={14} />
              {createTask.isPending ? "Creating..." : "Create Task"}
            </button>
          </div>
        </div>

        {createTask.isError && (
          <p className="mt-3 text-xs text-bengara">
            Failed to create task. Check the API server logs.
          </p>
        )}
      </motion.div>
    </>
  );
}
