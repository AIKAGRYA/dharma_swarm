"use client";

import { useEffect, useState, type ReactNode, type Ref } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Circle,
  Copy,
  ExternalLink,
  FileText,
  RadioTower,
  Search,
  ShieldAlert,
  X,
} from "lucide-react";
import type { CoherenceCard } from "@/lib/operatorCoherence";
import {
  buildHandoff,
  cardFacetBadges,
  cardToInspect,
  cardTone,
  classifyCardTruth,
  humanKind,
  humanRisk,
  type CockpitMode,
  type CockpitPanelDatum,
  type InspectItem,
} from "./cockpitV2Model";

const TONE_CLASS: Record<CockpitPanelDatum["tone"], string> = {
  ok: "border-rokusho/35 bg-rokusho/8 text-rokusho",
  warn: "border-kinpaku/40 bg-kinpaku/8 text-kinpaku",
  danger: "border-bengara/45 bg-bengara/10 text-bengara",
  info: "border-aozora/35 bg-aozora/8 text-aozora",
  muted: "border-sumi-800/60 bg-sumi-900/35 text-sumi-400",
};

const DOT_CLASS: Record<CockpitPanelDatum["tone"], string> = {
  ok: "bg-rokusho",
  warn: "bg-kinpaku",
  danger: "bg-bengara",
  info: "bg-aozora",
  muted: "bg-sumi-600",
};

export function toneClass(tone: CockpitPanelDatum["tone"]): string {
  return TONE_CLASS[tone] ?? TONE_CLASS.muted;
}

function miniIcon(tone: CockpitPanelDatum["tone"]) {
  if (tone === "danger") return <ShieldAlert size={14} />;
  if (tone === "warn") return <AlertTriangle size={14} />;
  if (tone === "ok") return <CheckCircle2 size={14} />;
  return <Circle size={12} />;
}

export function V2Panel({
  panel,
  onInspect,
}: {
  panel: CockpitPanelDatum;
  onInspect: (item: InspectItem) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onInspect(panel.inspect)}
      className={`group min-h-[132px] rounded-md border bg-sumi-950/40 p-3 text-left transition hover:-translate-y-0.5 hover:border-aozora/50 hover:bg-sumi-900/60 ${toneClass(panel.tone)}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.16em] opacity-75">
            {miniIcon(panel.tone)}
            {panel.eyebrow}
          </div>
          <div className="mt-2 text-sm font-semibold text-torinoko">{panel.title}</div>
        </div>
        <ExternalLink size={13} className="text-sumi-600 opacity-0 transition group-hover:opacity-100" />
      </div>
      <div className="mt-4 font-mono text-4xl font-semibold leading-none tabular-nums text-torinoko">
        {panel.value}
      </div>
      <div className="mt-3 line-clamp-2 text-xs leading-5 text-sumi-400">{panel.detail}</div>
    </button>
  );
}

export function V2CardRow({ card, onInspect }: { card: CoherenceCard; onInspect: (item: InspectItem) => void }) {
  const tone = cardTone(card);
  const truth = classifyCardTruth(card);
  const facetBadges = cardFacetBadges(card);
  return (
    <button
      type="button"
      onClick={() => onInspect(cardToInspect(card))}
      className="group grid w-full grid-cols-[minmax(0,1fr)_142px_122px] gap-3 rounded-md border border-sumi-800/55 bg-sumi-950/35 px-3 py-2.5 text-left text-xs transition hover:border-aozora/50 hover:bg-sumi-900/60 max-lg:grid-cols-1"
    >
      <div className="min-w-0">
        <div className="flex min-w-0 items-center gap-2">
          <span className={`h-2 w-2 shrink-0 rounded-full ${DOT_CLASS[tone]}`} />
          <span className="truncate font-semibold text-torinoko">{card.title}</span>
        </div>
        <div className="mt-1 line-clamp-1 text-sumi-500">
          {humanKind(card.kind)} · {humanRisk(card.risk)} · {card.evidence?.[0]?.source ?? "no evidence"}
        </div>
        <div className="mt-2 flex flex-wrap gap-1">
          {facetBadges.slice(0, 6).map((badge) => (
            <span key={badge} className="rounded border border-sumi-800/70 bg-sumi-900/45 px-1.5 py-0.5 text-[9px] uppercase tracking-[0.1em] text-sumi-500">
              {badge}
            </span>
          ))}
        </div>
      </div>
      <div className="self-center max-lg:flex max-lg:gap-2">
        <TruthBadge truth={truth} />
      </div>
      <div className="self-center text-right text-[10px] uppercase tracking-[0.12em] text-sumi-500 max-lg:text-left">
        {card.lane}<br />
        <span className="text-sumi-600">{card.facets.operator_decision ? "decision" : "engineering"}</span>
      </div>
    </button>
  );
}

export function TruthBadge({ truth }: { truth: ReturnType<typeof classifyCardTruth> }) {
  return (
    <span className={`inline-flex items-center rounded border px-2 py-1 text-[9px] font-semibold uppercase tracking-[0.12em] ${toneClass(truth.tone)}`} title={truth.detail}>
      {truth.label}
    </span>
  );
}

export function V2FilterBar({
  modes,
  activeMode,
  query,
  onMode,
  onQuery,
  inputRef,
}: {
  modes: { id: CockpitMode; label: string; hint: string }[];
  activeMode: CockpitMode;
  query: string;
  onMode: (mode: CockpitMode) => void;
  onQuery: (query: string) => void;
  inputRef?: Ref<HTMLInputElement>;
}) {
  return (
    <div className="rounded-md border border-sumi-800/60 bg-sumi-950/55 p-2">
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative min-w-[260px] flex-1">
          <Search size={14} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-sumi-600" />
          <input
            ref={inputRef}
            value={query}
            onChange={(event) => onQuery(event.target.value)}
            placeholder="Search cards, evidence, tracks, branches…"
            className="h-10 w-full rounded-md border border-sumi-800/70 bg-sumi-950/80 pl-9 pr-3 text-sm text-torinoko outline-none placeholder:text-sumi-600 focus:border-aozora/60"
          />
        </div>
        <div className="flex flex-wrap gap-1">
          {modes.map((mode) => (
            <button
              key={mode.id}
              type="button"
              onClick={() => onMode(mode.id)}
              className={`rounded-md border px-3 py-2 text-left transition ${
                activeMode === mode.id
                  ? "border-aozora/60 bg-aozora/10 text-aozora"
                  : "border-sumi-800/60 bg-sumi-900/35 text-sumi-400 hover:border-sumi-700 hover:text-sumi-200"
              }`}
            >
              <div className="text-xs font-semibold">{mode.label}</div>
              <div className="text-[9px] uppercase tracking-[0.12em] opacity-60">{mode.hint}</div>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

export function V2Section({
  title,
  eyebrow,
  children,
  action,
}: {
  title: string;
  eyebrow?: string;
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <section className="rounded-md border border-sumi-800/60 bg-sumi-950/45 p-4">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          {eyebrow ? <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-sumi-600">{eyebrow}</div> : null}
          <h2 className="mt-1 text-base font-semibold text-torinoko">{title}</h2>
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

export function V2Drawer({ item, onClose }: { item: InspectItem | null; onClose: () => void }) {
  const [copied, setCopied] = useClipboardFlag();
  useEffect(() => {
    if (!item) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [item, onClose]);
  if (!item) return null;
  const handoff = buildHandoff(item);
  return (
    <>
      <button
        type="button"
        aria-label="Close inspect drawer"
        onClick={onClose}
        className="fixed inset-0 z-40 cursor-default bg-black/40 backdrop-blur-[1px]"
      />
      <div
        role="dialog"
        aria-modal="true"
        className="fixed inset-y-0 right-0 z-50 flex w-[480px] max-w-[calc(100vw-24px)] flex-col border-l border-sumi-700/70 bg-[#0A0E1A]/95 shadow-2xl shadow-black/40 backdrop-blur-xl"
      >
      <div className="border-b border-sumi-800/70 p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-aozora">
              <RadioTower size={13} /> Inspect
            </div>
            <h3 className="mt-2 text-lg font-semibold text-torinoko">{item.title}</h3>
            {item.subtitle ? <div className="mt-1 text-xs text-sumi-500">{item.subtitle}</div> : null}
          </div>
          <button type="button" onClick={onClose} title="Close (Esc)" className="rounded-md p-1.5 text-sumi-500 hover:bg-sumi-800/80 hover:text-torinoko">
            <X size={16} />
          </button>
        </div>
      </div>
      <div className="flex-1 space-y-4 overflow-y-auto p-4">
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div className="rounded-md border border-sumi-800/60 bg-sumi-900/35 p-3">
            <div className="text-[10px] uppercase tracking-[0.12em] text-sumi-600">Status</div>
            <div className="mt-1 font-semibold text-sumi-200">{item.status ?? "—"}</div>
          </div>
          <div className="rounded-md border border-sumi-800/60 bg-sumi-900/35 p-3">
            <div className="text-[10px] uppercase tracking-[0.12em] text-sumi-600">Risk</div>
            <div className="mt-1 font-semibold text-sumi-200">{item.risk ?? "—"}</div>
          </div>
        </div>

        {item.nextAction ? (
          <div className="rounded-md border border-kinpaku/30 bg-kinpaku/8 p-3 text-sm text-kinpaku">
            <div className="text-[10px] font-semibold uppercase tracking-[0.12em] opacity-75">Recommended next action</div>
            <div className="mt-1 leading-5">{item.nextAction}</div>
          </div>
        ) : null}

        <div>
          <div className="mb-2 flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-sumi-500">
              <FileText size={13} /> Evidence
            </div>
            <button
              type="button"
              onClick={async () => {
                await navigator.clipboard?.writeText(JSON.stringify(item.evidence ?? [], null, 2));
                setCopied(true);
              }}
              className="rounded border border-sumi-800/70 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-sumi-500 hover:border-aozora/50 hover:text-aozora"
            >
              Copy evidence
            </button>
          </div>
          <div className="space-y-2">
            {(item.evidence ?? []).length ? (
              item.evidence?.map((ev, index) => (
                <div key={`${ev.source}-${index}`} className="rounded-md border border-sumi-800/60 bg-sumi-900/35 p-3 text-xs">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <div className="truncate font-semibold text-sumi-200">{ev.source}</div>
                      {ev.path ? <div className="mt-1 break-all font-mono text-[10px] text-sumi-600">{ev.path}</div> : null}
                    </div>
                    <span className="rounded border border-sumi-800/70 px-1.5 py-0.5 text-[9px] uppercase tracking-[0.1em] text-sumi-500">
                      {ev.status ?? ev.kind}
                    </span>
                  </div>
                  <div className="mt-2 text-sumi-500">{ev.detail ?? ev.kind}</div>
                  {ev.age_hours != null ? <div className="mt-1 text-[10px] text-sumi-600">age {ev.age_hours}h</div> : null}
                </div>
              ))
            ) : (
              <div className="rounded-md border border-dashed border-sumi-800 p-3 text-xs text-sumi-600">No evidence attached.</div>
            )}
          </div>
        </div>

        <div>
          <div className="mb-2 flex items-center justify-between gap-2">
            <div className="text-xs font-semibold uppercase tracking-[0.14em] text-sumi-500">Raw</div>
            <button
              type="button"
              onClick={async () => {
                await navigator.clipboard?.writeText(JSON.stringify(item.raw ?? item, null, 2));
                setCopied(true);
              }}
              className="rounded border border-sumi-800/70 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-sumi-500 hover:border-aozora/50 hover:text-aozora"
            >
              Copy raw
            </button>
          </div>
          <pre className="max-h-[260px] overflow-auto rounded-md border border-sumi-800/60 bg-black/25 p-3 text-[10px] leading-4 text-sumi-400">
            {JSON.stringify(item.raw ?? item, null, 2)}
          </pre>
        </div>
      </div>
      <div className="border-t border-sumi-800/70 p-4">
        <button
          type="button"
          onClick={async () => {
            await navigator.clipboard?.writeText(handoff);
            setCopied(true);
          }}
          className="inline-flex w-full items-center justify-center gap-2 rounded-md border border-aozora/45 bg-aozora/10 px-3 py-2 text-sm font-semibold text-aozora hover:bg-aozora/15"
        >
          <Copy size={14} /> {copied ? "Copied handoff" : "Copy scoped handoff"}
        </button>
      </div>
      </div>
    </>
  );
}

function useClipboardFlag(): [boolean, (value: boolean) => void] {
  const [copied, setCopied] = useState(false);
  useEffect(() => {
    if (!copied) return;
    const id = window.setTimeout(() => setCopied(false), 1600);
    return () => window.clearTimeout(id);
  }, [copied]);
  return [copied, setCopied];
}
