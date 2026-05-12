"use client";

/**
 * Zone 3: Evidence Drawer — structured provenance for the selected row.
 * Shows raw source refs, evidence items, gap codes, owner/authority.
 * No fake summaries — every field shows provenance.
 */

import { X, FileText, Code, AlertCircle, Link as LinkIcon } from "lucide-react";
import type { ControlSurfaceRow } from "@/lib/types";
import { colors } from "@/lib/theme";

interface EvidenceDrawerProps {
  row: ControlSurfaceRow;
  onClose: () => void;
}

type CoherenceState = "bound" | "partial" | "drifted" | "declared_only" | "unknown";

const COHERENCE_COLORS: Record<CoherenceState, string> = {
  bound: colors.rokusho,
  partial: colors.kinpaku,
  drifted: colors.bengara,
  declared_only: colors.fuji,
  unknown: colors.sumi[600],
};

function coherenceColor(state: string): string {
  return COHERENCE_COLORS[state as CoherenceState] ?? colors.sumi[600];
}

function guessRefKind(ref: string): "file" | "api" | "manifest" | "unknown" {
  if (ref.startsWith("/") || ref.includes(".py") || ref.includes(".ts") || ref.includes(".yaml")) {
    return "file";
  }
  if (ref.startsWith("/api/") || ref.includes("http")) {
    return "api";
  }
  if (ref.toLowerCase().includes("manifest") || ref.toLowerCase().includes("sovereign")) {
    return "manifest";
  }
  return "unknown";
}

function RefIcon({ kind }: { kind: ReturnType<typeof guessRefKind> }) {
  switch (kind) {
    case "file":
      return <FileText size={12} className="shrink-0 text-aozora" />;
    case "api":
      return <LinkIcon size={12} className="shrink-0 text-rokusho" />;
    case "manifest":
      return <Code size={12} className="shrink-0 text-kinpaku" />;
    default:
      return <FileText size={12} className="shrink-0 text-sumi-500" />;
  }
}

export function EvidenceDrawer({ row, onClose }: EvidenceDrawerProps) {
  const cc = coherenceColor(row.coherence_state);

  return (
    <div className="flex h-full flex-col bg-sumi-950/60">
      {/* Header */}
      <div className="flex items-start justify-between border-b border-sumi-800/40 px-4 py-3">
        <div className="min-w-0 flex-1">
          <div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-sumi-500">
            Evidence
          </div>
          <h3 className="mt-1 truncate text-sm font-semibold text-torinoko">
            {row.label}
          </h3>
          <div className="mt-1 flex flex-wrap items-center gap-2">
            <span
              className="rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.1em]"
              style={{
                borderColor: `color-mix(in srgb, ${cc} 40%, transparent)`,
                backgroundColor: `color-mix(in srgb, ${cc} 10%, transparent)`,
                color: cc,
              }}
            >
              {row.coherence_state}
            </span>
            <code className="rounded bg-sumi-800/50 px-1.5 py-0.5 text-[10px] text-sumi-400">
              {row.kind}
            </code>
            {row.human_decision_required && (
              <span className="text-[10px] font-semibold" style={{ color: colors.botan }}>
                Needs John
              </span>
            )}
          </div>
        </div>
        <button
          onClick={onClose}
          className="rounded-md p-1 text-sumi-500 hover:bg-sumi-800/50 hover:text-sumi-300"
        >
          <X size={14} />
        </button>
      </div>

      {/* Content — scrollable */}
      <div className="flex-1 space-y-4 overflow-auto p-4">
        {/* State comparison */}
        <section>
          <h4 className="text-[10px] font-semibold uppercase tracking-[0.12em] text-sumi-500">
            State
          </h4>
          <div className="mt-2 grid gap-2 text-xs">
            <div className="flex items-center justify-between rounded-md bg-sumi-900/50 px-3 py-2">
              <span className="text-sumi-500">Declared</span>
              <code className="text-sumi-300">{row.declared_state || "—"}</code>
            </div>
            <div className="flex items-center justify-between rounded-md bg-sumi-900/50 px-3 py-2">
              <span className="text-sumi-500">Desired</span>
              <code className="text-sumi-300">{row.desired_state || "—"}</code>
            </div>
            <div className="flex items-center justify-between rounded-md bg-sumi-900/50 px-3 py-2">
              <span className="text-sumi-500">Observed</span>
              <code className="text-sumi-300">{row.observed_state || "—"}</code>
            </div>
          </div>
        </section>

        {/* Authority */}
        <section>
          <h4 className="text-[10px] font-semibold uppercase tracking-[0.12em] text-sumi-500">
            Authority
          </h4>
          <div className="mt-2 grid gap-2 text-xs">
            <div className="flex items-center justify-between rounded-md bg-sumi-900/50 px-3 py-2">
              <span className="text-sumi-500">Owner Module</span>
              <code className="text-sumi-300">{row.owner_module || "—"}</code>
            </div>
            <div className="flex items-center justify-between rounded-md bg-sumi-900/50 px-3 py-2">
              <span className="text-sumi-500">Truth Owner</span>
              <code className="text-sumi-300">{row.truth_owner || "—"}</code>
            </div>
            <div className="flex items-center justify-between rounded-md bg-sumi-900/50 px-3 py-2">
              <span className="text-sumi-500">Authority Role</span>
              <code className="text-sumi-300">{row.authority_role || "—"}</code>
            </div>
            <div className="flex items-center justify-between rounded-md bg-sumi-900/50 px-3 py-2">
              <span className="text-sumi-500">Freshness</span>
              <code className="text-sumi-300">{row.freshness || "—"}</code>
            </div>
          </div>
        </section>

        {/* Next action */}
        {row.next_action && (
          <section>
            <h4 className="text-[10px] font-semibold uppercase tracking-[0.12em] text-sumi-500">
              Next Action
            </h4>
            <div className="mt-2 rounded-md border border-aozora/20 bg-aozora/5 px-3 py-2 text-xs text-aozora">
              {row.next_action}
            </div>
          </section>
        )}

        {/* Gap codes */}
        {row.gap_codes.length > 0 && (
          <section>
            <h4 className="text-[10px] font-semibold uppercase tracking-[0.12em] text-sumi-500">
              Gap Codes
            </h4>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {row.gap_codes.map((g, i) => (
                <code
                  key={i}
                  className="rounded bg-sumi-800/60 px-2 py-1 text-[10px] text-bengara"
                >
                  {g}
                </code>
              ))}
            </div>
          </section>
        )}

        {/* Evidence items */}
        {row.evidence.length > 0 && (
          <section>
            <h4 className="text-[10px] font-semibold uppercase tracking-[0.12em] text-sumi-500">
              Evidence ({row.evidence.length})
            </h4>
            <ul className="mt-2 space-y-1.5">
              {row.evidence.map((e, i) => (
                <li
                  key={i}
                  className="flex items-start gap-2 rounded-md bg-sumi-900/50 px-3 py-2 text-xs text-sumi-300"
                >
                  <AlertCircle size={12} className="mt-0.5 shrink-0 text-kinpaku" />
                  <span className="break-all">{e}</span>
                </li>
              ))}
            </ul>
          </section>
        )}

        {/* Source refs */}
        {row.source_refs.filter(Boolean).length > 0 && (
          <section>
            <h4 className="text-[10px] font-semibold uppercase tracking-[0.12em] text-sumi-500">
              Source Refs ({row.source_refs.filter(Boolean).length})
            </h4>
            <ul className="mt-2 space-y-1.5">
              {row.source_refs.filter(Boolean).map((ref, i) => {
                const kind = guessRefKind(ref);
                return (
                  <li
                    key={i}
                    className="flex items-center gap-2 rounded-md bg-sumi-900/50 px-3 py-2"
                  >
                    <RefIcon kind={kind} />
                    <code className="break-all text-[10px] text-sumi-300">{ref}</code>
                  </li>
                );
              })}
            </ul>
          </section>
        )}

        {/* Raw data (collapsible) */}
        {Object.keys(row.raw).length > 0 && (
          <details className="group">
            <summary className="cursor-pointer text-[10px] font-semibold uppercase tracking-[0.12em] text-sumi-500 hover:text-sumi-400">
              Raw Data
            </summary>
            <pre className="mt-2 max-h-48 overflow-auto rounded-md bg-sumi-900/50 p-3 text-[10px] text-sumi-400">
              {JSON.stringify(row.raw, null, 2)}
            </pre>
          </details>
        )}
      </div>
    </div>
  );
}
