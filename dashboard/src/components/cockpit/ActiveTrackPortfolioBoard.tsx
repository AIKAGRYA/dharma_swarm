"use client";

import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  ArrowRight,
  CircleCheck,
  Clock3,
  Copy,
  FileText,
  GitCommit,
  GitPullRequest,
  Layers3,
  ListTree,
  Maximize2,
  Minimize2,
  Users,
  X,
} from "lucide-react";
import { useActiveTrackPortfolio } from "@/hooks/useControlSurface";
import type { ActiveTrackLayer, ActiveTrackMovement, ActiveTrackSlot } from "@/lib/types";
import { colors } from "@/lib/theme";

type BoardMode = "normal" | "compact" | "focus";

function statusTone(status: string): { color: string; border: string; bg: string } {
  if (status === "shippable") {
    return {
      color: colors.rokusho,
      border: "border-rokusho/50",
      bg: "bg-rokusho/10",
    };
  }
  if (status === "stale" || status === "blocked") {
    return {
      color: colors.bengara,
      border: "border-bengara/60",
      bg: "bg-bengara/10",
    };
  }
  if (status === "needs_declaration") {
    return {
      color: colors.kinpaku,
      border: "border-kinpaku/60",
      bg: "bg-kinpaku/10",
    };
  }
  return {
    color: colors.aozora,
    border: "border-aozora/50",
    bg: "bg-aozora/10",
  };
}

function statusLabel(status: string): string {
  return status.replaceAll("_", " ");
}

function statusIcon(status: string) {
  if (status === "shippable") {
    return <CircleCheck size={13} />;
  }
  if (status === "stale" || status === "blocked" || status === "needs_declaration") {
    return <AlertTriangle size={13} />;
  }
  return <Clock3 size={13} />;
}

function movementLabel(movement: ActiveTrackMovement): string {
  const age = movement.age && movement.age !== "unknown" ? movement.age : "time unknown";
  return `${age} - ${movement.title}`;
}

function prRefs(movements: ActiveTrackMovement[]): string[] {
  const refs = new Set<string>();
  movements.forEach((movement) => {
    movement.pr_refs.forEach((ref) => refs.add(ref));
  });
  return Array.from(refs).slice(0, 5);
}

function layerByDepth(slot: ActiveTrackSlot, depth: number): ActiveTrackLayer {
  return slot.layers.find((layer) => layer.depth === depth) ?? slot.layers[0];
}

function TrackStatusBadge({ status }: { status: string }) {
  const tone = statusTone(status);
  return (
    <span
      className={`inline-flex shrink-0 items-center gap-1 rounded-md border px-2 py-1 text-[10px] font-semibold uppercase ${tone.border} ${tone.bg}`}
      style={{ color: tone.color }}
    >
      {statusIcon(status)}
      {statusLabel(status)}
    </span>
  );
}

function TrackRow({
  slot,
  selected,
  onSelect,
}: {
  slot: ActiveTrackSlot;
  selected: boolean;
  onSelect: () => void;
}) {
  const tone = statusTone(slot.status);
  return (
    <button
      type="button"
      onClick={onSelect}
      onContextMenu={(event) => {
        event.preventDefault();
        onSelect();
      }}
      className={`min-w-0 w-full rounded-md border px-3 py-2.5 text-left transition ${
        selected
          ? `${tone.border} bg-sumi-850/90 shadow-[0_0_0_1px_rgba(255,255,255,0.04)]`
          : "border-sumi-800/50 bg-sumi-900/45 hover:border-sumi-700/80 hover:bg-sumi-850/70"
      }`}
    >
      <div className="flex min-w-0 flex-wrap items-start justify-between gap-2">
        <div className="flex min-w-0 items-start gap-3">
          <div
            className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-md border text-xs font-semibold ${tone.border} ${tone.bg}`}
            style={{ color: tone.color }}
          >
            {String(slot.slot).padStart(2, "0")}
          </div>
          <div className="min-w-0">
            <div className="truncate text-sm font-semibold text-torinoko">{slot.title}</div>
            <div className="mt-1 line-clamp-2 text-[11px] leading-4 text-sumi-500">
              {slot.theme}
            </div>
          </div>
        </div>
        <TrackStatusBadge status={slot.status} />
      </div>

      <div className="mt-3 grid gap-2 lg:grid-cols-[112px_minmax(0,1fr)]">
        <div>
          <div className="h-1.5 overflow-hidden rounded-full bg-sumi-800">
            <div
              className="h-full rounded-full"
              style={{
                width: `${Math.min(100, slot.progress.percent)}%`,
                backgroundColor: tone.color,
              }}
            />
          </div>
          <div className="mt-1 text-[10px] text-sumi-500">
            {slot.progress.total
              ? `${slot.progress.passed}/${slot.progress.total} gates`
              : "gates unset"}
          </div>
        </div>
        <div className="min-w-0 space-y-1">
          {slot.last_movements.slice(0, 3).map((movement) => (
            <div
              key={`${slot.id}-${movement.id}`}
              className="flex min-w-0 items-center gap-2 text-[11px] text-sumi-400"
            >
              <GitCommit size={11} className="shrink-0 text-sumi-600" />
              <span className="min-w-0 truncate">{movementLabel(movement)}</span>
            </div>
          ))}
        </div>
      </div>
    </button>
  );
}

function CompactTrackStrip({
  slots,
  selectedId,
  onSelect,
}: {
  slots: ActiveTrackSlot[];
  selectedId: string;
  onSelect: (slot: ActiveTrackSlot) => void;
}) {
  return (
    <div className="grid grid-cols-2 gap-1.5 md:grid-cols-5 xl:grid-cols-10">
      {slots.map((slot) => {
        const tone = statusTone(slot.status);
        return (
          <button
            key={slot.id}
            type="button"
            onClick={() => onSelect(slot)}
            className={`flex min-w-0 items-center gap-2 rounded-md border px-2 py-1.5 text-left ${
              selectedId === slot.id ? tone.border : "border-sumi-800/50"
            } bg-sumi-900/60`}
          >
            <span className="shrink-0 text-[10px] font-semibold" style={{ color: tone.color }}>
              {String(slot.slot).padStart(2, "0")}
            </span>
            <span className="min-w-0 flex-1 truncate text-[11px] font-medium text-sumi-200">{slot.title}</span>
            {slot.status === "stale" || slot.status === "needs_declaration" ? (
              <AlertTriangle size={12} className="ml-auto shrink-0" style={{ color: tone.color }} />
            ) : null}
          </button>
        );
      })}
    </div>
  );
}

function LayerSelector({
  layers,
  activeDepth,
  onDepth,
}: {
  layers: ActiveTrackLayer[];
  activeDepth: number;
  onDepth: (depth: number) => void;
}) {
  return (
    <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
      {layers.map((layer) => (
        <button
          key={layer.depth}
          type="button"
          onClick={() => onDepth(layer.depth)}
          className={`rounded-md border px-3 py-2 text-left ${
            activeDepth === layer.depth
              ? "border-aozora/60 bg-aozora/10 text-aozora"
              : "border-sumi-800/50 bg-sumi-900/45 text-sumi-400 hover:border-sumi-700"
          }`}
        >
          <div className="flex items-center gap-2 text-[10px] font-semibold uppercase">
            <Layers3 size={12} />
            Depth {layer.depth}
          </div>
          <div className="mt-1 truncate text-xs font-medium">{layer.label}</div>
        </button>
      ))}
    </div>
  );
}

function MovementList({ movements }: { movements: ActiveTrackMovement[] }) {
  return (
    <div className="space-y-2">
      {movements.map((movement) => (
        <div
          key={`${movement.id}-${movement.source_ref}`}
          className="rounded-md border border-sumi-800/50 bg-sumi-950/35 px-3 py-2"
        >
          <div className="flex min-w-0 flex-wrap items-start justify-between gap-2">
            <div className="flex min-w-0 gap-2">
              {movement.kind === "commit" ? (
                <GitCommit size={14} className="mt-0.5 shrink-0 text-aozora" />
              ) : (
                <FileText size={14} className="mt-0.5 shrink-0 text-kinpaku" />
              )}
              <div className="min-w-0">
                <div className="line-clamp-2 text-xs font-medium text-sumi-200">{movement.title}</div>
                <div className="mt-1 truncate text-[10px] text-sumi-500">{movement.detail}</div>
              </div>
            </div>
            <div className="shrink-0 text-right text-[10px] text-sumi-500">
              <div>{movement.age}</div>
              <div className="max-w-[160px] truncate">{movement.actor}</div>
            </div>
          </div>
          {movement.pr_refs.length ? (
            <div className="mt-2 flex flex-wrap gap-1">
              {movement.pr_refs.map((ref) => (
                <span
                  key={`${movement.id}-${ref}`}
                  className="inline-flex items-center gap-1 rounded-md border border-fuji/40 bg-fuji/10 px-1.5 py-0.5 text-[10px] text-fuji"
                >
                  <GitPullRequest size={10} />
                  {ref}
                </span>
              ))}
            </div>
          ) : null}
        </div>
      ))}
    </div>
  );
}

function DetailPanel({
  slot,
  activeDepth,
  onDepth,
  onCopy,
  copied,
}: {
  slot: ActiveTrackSlot;
  activeDepth: number;
  onDepth: (depth: number) => void;
  onCopy: (text: string) => void;
  copied: boolean;
}) {
  const layer = layerByDepth(slot, activeDepth);
  const tone = statusTone(slot.status);
  const refs = prRefs(layer.movements);

  return (
    <div className="flex min-h-[560px] min-w-0 overflow-hidden flex-col rounded-md border border-sumi-800/50 bg-sumi-900/45">
      <div className="border-b border-sumi-800/50 px-4 py-3">
        <div className="flex min-w-0 flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2 text-[10px] font-semibold uppercase text-sumi-500">
              <ListTree size={13} />
              Slot {String(slot.slot).padStart(2, "0")} drilldown
            </div>
            <h2 className="mt-1 truncate text-lg font-semibold text-torinoko">{slot.title}</h2>
            <p className="mt-1 line-clamp-2 text-xs leading-5 text-sumi-400">{slot.theme}</p>
          </div>
          <TrackStatusBadge status={slot.status} />
        </div>

        <div className="mt-3 grid gap-2 md:grid-cols-4">
          <div className="rounded-md border border-sumi-800/40 bg-sumi-950/35 px-3 py-2">
            <div className="text-[10px] uppercase text-sumi-600">Progress</div>
            <div className="mt-1 text-sm font-semibold text-sumi-200">
              {slot.progress.total ? `${slot.progress.percent}%` : "unset"}
            </div>
          </div>
          <div className="rounded-md border border-sumi-800/40 bg-sumi-950/35 px-3 py-2">
            <div className="text-[10px] uppercase text-sumi-600">Freshness</div>
            <div className="mt-1 truncate text-sm font-semibold text-sumi-200">
              {slot.freshness.latest_age}
            </div>
          </div>
          <div className="rounded-md border border-sumi-800/40 bg-sumi-950/35 px-3 py-2">
            <div className="text-[10px] uppercase text-sumi-600">Agents</div>
            <div className="mt-1 truncate text-sm font-semibold text-sumi-200">
              {slot.agents.length || "unknown"}
            </div>
          </div>
          <div className="rounded-md border border-sumi-800/40 bg-sumi-950/35 px-3 py-2">
            <div className="text-[10px] uppercase text-sumi-600">PR refs</div>
            <div className="mt-1 truncate text-sm font-semibold text-sumi-200">
              {refs.length ? refs.join(", ") : "none"}
            </div>
          </div>
        </div>
      </div>

      <div className="flex-1 space-y-4 overflow-auto p-4">
        <LayerSelector layers={slot.layers} activeDepth={activeDepth} onDepth={onDepth} />

        {slot.freshness.stale ? (
          <div className="rounded-md border border-bengara/50 bg-bengara/10 px-3 py-2 text-xs text-bengara">
            {slot.freshness.stale_reasons.join(" ")}
          </div>
        ) : null}

        <div className="grid gap-4 xl:grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)]">
          <div className="space-y-4">
            <div>
              <div className="flex items-center gap-2 text-[10px] font-semibold uppercase text-sumi-500">
                <ArrowRight size={12} style={{ color: tone.color }} />
                {layer.label}
              </div>
              <p className="mt-2 text-sm leading-6 text-sumi-300">{layer.summary}</p>
            </div>

            <div className="space-y-2">
              {layer.items.slice(0, 12).map((item) => (
                <div
                  key={`${slot.id}-${layer.depth}-${item}`}
                  className="rounded-md border border-sumi-800/45 bg-sumi-950/30 px-3 py-2 text-xs leading-5 text-sumi-300"
                >
                  {item}
                </div>
              ))}
            </div>

            <div className="rounded-md border border-sumi-800/50 bg-sumi-950/35 p-3">
              <div className="flex items-center gap-2 text-[10px] font-semibold uppercase text-sumi-500">
                <Users size={12} />
                Agents
              </div>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {(slot.agents.length ? slot.agents : ["unknown"]).map((agent) => (
                  <span
                    key={`${slot.id}-${agent}`}
                    className="rounded-md border border-sumi-700/50 px-2 py-1 text-[10px] text-sumi-300"
                  >
                    {agent}
                  </span>
                ))}
              </div>
            </div>
          </div>

          <div className="space-y-4">
            <div>
              <div className="mb-2 flex items-center gap-2 text-[10px] font-semibold uppercase text-sumi-500">
                <GitCommit size={12} />
                Movements
              </div>
              <MovementList movements={layer.movements} />
            </div>

            <div>
              <div className="mb-2 flex items-center gap-2 text-[10px] font-semibold uppercase text-sumi-500">
                <FileText size={12} />
                Evidence and logs
              </div>
              <div className="space-y-2">
                {layer.evidence.slice(0, activeDepth >= 4 ? 12 : 5).map((item) => (
                  <div
                    key={`${slot.id}-${item.kind}-${item.path}-${item.label}`}
                    className="rounded-md border border-sumi-800/45 bg-sumi-950/30 px-3 py-2"
                  >
                    <div className="flex min-w-0 flex-wrap items-start justify-between gap-2">
                      <div className="min-w-0">
                        <div className="truncate text-xs font-medium text-sumi-200">{item.label}</div>
                        <div className="mt-1 truncate text-[10px] text-sumi-500">{item.path}</div>
                      </div>
                      <div className="shrink-0 text-[10px] text-sumi-500">{item.age}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-md border border-aozora/35 bg-aozora/5">
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-aozora/20 px-3 py-2">
                <div className="flex items-center gap-2 text-[10px] font-semibold uppercase text-aozora">
                  <Copy size={12} />
                  Proposed handoff prompt
                </div>
                <button
                  type="button"
                  onClick={() => onCopy(layer.handoff_prompt)}
                  className="rounded-md border border-aozora/35 px-2 py-1 text-[10px] font-semibold uppercase text-aozora hover:bg-aozora/10"
                >
                  {copied ? "Copied" : "Copy"}
                </button>
              </div>
              <pre className="max-h-[260px] overflow-auto whitespace-pre-wrap break-words p-3 text-[11px] leading-5 text-sumi-300">
                {layer.handoff_prompt}
              </pre>
            </div>
          </div>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2 border-t border-sumi-800/50 px-4 py-3">
        <button
          type="button"
          onClick={() => onCopy(layer.handoff_prompt)}
          className="rounded-md border border-sumi-700/60 px-3 py-1.5 text-[10px] font-semibold uppercase text-sumi-300 hover:border-aozora/50 hover:text-aozora"
        >
          Copy handoff
        </button>
        <button
          type="button"
          disabled
          className="rounded-md border border-sumi-800/60 px-3 py-1.5 text-[10px] font-semibold uppercase text-sumi-600"
        >
          Send to LLM planned
        </button>
      </div>
    </div>
  );
}

export function ActiveTrackPortfolioBoard() {
  const { portfolio, slots, isLoading, error, refetch } = useActiveTrackPortfolio();
  const [mode, setMode] = useState<BoardMode>("normal");
  const [selectedId, setSelectedId] = useState("");
  const [activeDepth, setActiveDepth] = useState(1);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!selectedId && slots.length) {
      setSelectedId(slots[0].id);
    }
  }, [selectedId, slots]);

  const selected = useMemo(
    () => slots.find((slot) => slot.id === selectedId) ?? slots[0] ?? null,
    [selectedId, slots],
  );

  const shellClass =
    mode === "focus"
      ? "fixed inset-3 z-50 flex max-w-full flex-col overflow-hidden rounded-md border border-aozora/50 bg-sumi-950 p-3 shadow-2xl"
      : "w-full max-w-full overflow-hidden rounded-md border border-sumi-700/35 bg-sumi-950/70";

  const copyPrompt = (text: string) => {
    void navigator.clipboard?.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1600);
  };

  if (error) {
    return (
      <section className="rounded-md border border-bengara/50 bg-bengara/10 p-4 text-sm text-bengara">
        Active track portfolio unavailable: {String(error)}
      </section>
    );
  }

  return (
    <section className={shellClass}>
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-sumi-800/50 px-4 py-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-[10px] font-semibold uppercase text-aozora">
            <ListTree size={14} />
            Target operating model
          </div>
          <div className="mt-1 flex min-w-0 flex-wrap items-center gap-2">
            <h1 className="truncate text-xl font-semibold text-torinoko">10-track command board</h1>
            <span className="rounded-md border border-sumi-700/50 px-2 py-1 text-[10px] text-sumi-400">
              {portfolio?.occupied_slot_count ?? 0}/{portfolio?.slot_count ?? 10} linked
            </span>
            <span className="rounded-md border border-sumi-700/50 px-2 py-1 text-[10px] text-sumi-400">
              {portfolio?.declared_active_track_count ?? 0} declared nodes
            </span>
            {portfolio?.policy_slot_capacity && portfolio.policy_slot_capacity !== portfolio.slot_count ? (
              <span className="rounded-md border border-kinpaku/50 px-2 py-1 text-[10px] text-kinpaku">
                policy cap {portfolio.policy_slot_capacity}
              </span>
            ) : null}
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => void refetch()}
            className="rounded-md border border-sumi-700/60 px-3 py-1.5 text-[10px] font-semibold uppercase text-sumi-300 hover:border-aozora/50 hover:text-aozora"
          >
            Refresh
          </button>
          <button
            type="button"
            onClick={() => setMode(mode === "compact" ? "normal" : "compact")}
            className="rounded-md border border-sumi-700/60 px-3 py-1.5 text-[10px] font-semibold uppercase text-sumi-300 hover:border-aozora/50 hover:text-aozora"
          >
            {mode === "compact" ? "Expand" : "Compact"}
          </button>
          <button
            type="button"
            onClick={() => setMode(mode === "focus" ? "normal" : "focus")}
            className="rounded-md border border-sumi-700/60 p-1.5 text-sumi-300 hover:border-aozora/50 hover:text-aozora"
            aria-label={mode === "focus" ? "Exit focus" : "Focus board"}
          >
            {mode === "focus" ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
          </button>
          {mode === "focus" ? (
            <button
              type="button"
              onClick={() => setMode("normal")}
              className="rounded-md border border-sumi-700/60 p-1.5 text-sumi-300 hover:border-bengara/50 hover:text-bengara"
              aria-label="Close focus board"
            >
              <X size={14} />
            </button>
          ) : null}
        </div>
      </div>

      <div className={mode === "focus" ? "max-w-full flex-1 overflow-auto p-4" : "max-w-full overflow-hidden p-4"}>
        {portfolio?.warnings.length ? (
          <div className="mb-3 rounded-md border border-kinpaku/50 bg-kinpaku/10 px-3 py-2 text-xs text-kinpaku">
            {portfolio.warnings.join(" · ")}
          </div>
        ) : null}

        {mode === "compact" ? (
          <CompactTrackStrip
            slots={slots}
            selectedId={selected?.id ?? ""}
            onSelect={(slot) => {
              setSelectedId(slot.id);
              setMode("normal");
              setActiveDepth(1);
            }}
          />
        ) : isLoading && !slots.length ? (
          <div className="flex min-h-[220px] items-center text-sm text-sumi-500">
            Loading active track portfolio...
          </div>
        ) : selected ? (
          <div className="flex w-full max-w-full min-w-0 flex-col gap-3 overflow-hidden xl:flex-row">
            <div className="min-w-0 space-y-2 overflow-hidden xl:w-[46%] xl:max-w-[720px] xl:shrink-0">
              <CompactTrackStrip
                slots={slots}
                selectedId={selected.id}
                onSelect={(slot) => {
                  setSelectedId(slot.id);
                  setActiveDepth(1);
                }}
              />
              <div className="space-y-2">
                {slots.map((slot) => (
                  <TrackRow
                    key={slot.id}
                    slot={slot}
                    selected={selected.id === slot.id}
                    onSelect={() => {
                      setSelectedId(slot.id);
                      setActiveDepth(1);
                    }}
                  />
                ))}
              </div>
            </div>

            <div className="min-w-0 overflow-hidden xl:flex-1">
              <DetailPanel
                slot={selected}
                activeDepth={activeDepth}
                onDepth={setActiveDepth}
                onCopy={copyPrompt}
                copied={copied}
              />
            </div>
          </div>
        ) : (
          <div className="flex min-h-[220px] items-center text-sm text-sumi-500">
            No active track slots projected.
          </div>
        )}
      </div>
    </section>
  );
}
