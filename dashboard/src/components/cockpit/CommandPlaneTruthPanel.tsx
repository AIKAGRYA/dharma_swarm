"use client";

/**
 * CommandPlaneTruthPanel — the single panel that renders the full
 * /api/manifest/command-plane contract. Owns six bands top to bottom:
 *
 *   1. Manifest health ribbon (6 Numerals + source chip)
 *   2. Active track + evidence (id, status, SHIPPABLE/PENDING-CLOSEOUT badge,
 *      progress N/M, top 3 criteria pass/fail)
 *   3. Needs-human queue (top operator decisions cross-source)
 *   4. Broken Register rows (P0/P1 with next_action)
 *   5. PR queue (placeholder honest about "not_wired")
 *   6. Next PR ladder (codex's 3 ranked next slices)
 *
 * Per the handoff brief: no fake green, source chips on every signal,
 * stale/timeout/unknown visually distinct from broken, "ACTIVE but
 * SHIPPABLE" unmistakable.
 */

import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { colors } from "@/lib/theme";
import { Numeral } from "@/components/primitives/Numeral";
import { Glyph } from "@/components/primitives/Glyph";
import {
  StatusBadge,
  type StatusBadgeState,
} from "@/components/primitives/StatusBadge";
import {
  useCommandPlaneTruth,
  type ActiveTrack,
  type BrokenRegisterRow,
  type NeedsHumanRow,
  type NextPrLadderItem,
} from "@/hooks/useCommandPlaneTruth";

function priorityBadge(p: string): StatusBadgeState {
  const k = p.toLowerCase();
  if (k === "p0") return "fail";
  if (k === "p1") return "stale";
  return "drift";
}

function coherenceBadge(s: string): StatusBadgeState {
  const k = s.toLowerCase();
  if (k === "bound") return "pass";
  if (k === "partial") return "stale";
  if (k === "drifted" || k === "declared_only") return "drift";
  return "drift";
}

function trackBadge(track: ActiveTrack): { state: StatusBadgeState; label: string; tone: string } {
  // The big move: surface ACTIVE-but-SHIPPABLE so the operator sees closeout
  // is pending, not "still working on it."
  if (track.evidence?.shippable && track.status?.toUpperCase() === "ACTIVE") {
    return {
      state: "pass",
      label: "PENDING CLOSEOUT",
      tone: "Active track meets all criteria — operator can close it.",
    };
  }
  if (track.evidence?.shippable) {
    return { state: "pass", label: "SHIPPABLE", tone: "All completion criteria pass." };
  }
  const s = (track.status ?? "").toUpperCase();
  if (s === "ACTIVE") return { state: "drift", label: "ACTIVE", tone: "In progress." };
  if (s === "QUEUED") return { state: "drift", label: "QUEUED", tone: "Waiting." };
  if (s === "STALE") return { state: "stale", label: "STALE", tone: "TTL expired." };
  if (s === "FAILED" || s === "BLOCKED") return { state: "fail", label: s, tone: "Blocked." };
  return { state: "drift", label: s || "UNKNOWN", tone: "Status unclear." };
}

function SourceChip({ children }: { children: React.ReactNode }) {
  return (
    <span
      className="font-mono text-[10px] uppercase tabular-nums"
      style={{
        color: colors.sumi[600],
        letterSpacing: "0.10em",
        border: `1px solid ${colors.sumi[700]}`,
        padding: "1px 6px",
      }}
    >
      {children}
    </span>
  );
}

export function CommandPlaneTruthPanel() {
  const { data, isLoading } = useCommandPlaneTruth();

  if (isLoading && !data) {
    return (
      <section
        style={{
          padding: "16px",
          border: `1px solid ${colors.sumi[700]}`,
          backgroundColor: colors.sumi[900],
          color: colors.sumi[600],
        }}
        className="font-mono text-xs uppercase tabular-nums"
      >
        LOADING COMMAND PLANE…
      </section>
    );
  }

  if (!data) {
    return (
      <section
        style={{
          padding: "16px",
          border: `1px solid ${colors.sumi[700]}`,
          backgroundColor: colors.sumi[900],
          color: colors.shu,
        }}
        className="font-mono text-xs uppercase tabular-nums"
      >
        /api/manifest/command-plane unreachable
      </section>
    );
  }

  const m = data.repo_build.manifest;
  const track = data.repo_build.active_track;
  const badge = trackBadge(track);
  const needs = data.repo_build.needs_human ?? [];
  const br = data.repo_build.broken_register ?? [];
  const ladder = data.next_pr_ladder ?? [];
  const pr = data.repo_build.pr_queue;

  return (
    <section className="flex flex-col gap-4">
      {/* Section header */}
      <div className="flex items-center justify-between">
        <h2
          className="font-mono text-xs uppercase"
          style={{ color: colors.sumi[600], letterSpacing: "0.14em" }}
        >
          COMMAND PLANE · SSoT
        </h2>
        <div className="flex items-center gap-2">
          <SourceChip>{`/api/manifest/command-plane`}</SourceChip>
          <SourceChip>{`schema ${data.schema_version}`}</SourceChip>
        </div>
      </div>

      {/* 1. Manifest health ribbon */}
      <div className="flex flex-col gap-2">
        <div className="flex items-center justify-between">
          <span
            className="font-mono text-[10px] uppercase tabular-nums"
            style={{ color: colors.sumi[600], letterSpacing: "0.14em" }}
          >
            MANIFEST · declared vs observed
          </span>
          <SourceChip>{`ACTIVE_SURFACE_MANIFEST.yaml · ${m.last_updated}`}</SourceChip>
        </div>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-6">
          <Stat label="TOTAL" value={m.summary.total} tone="active" />
          <Stat label="LIVE" value={m.summary.live} tone="ok" />
          <Stat
            label="DEGRADED"
            value={m.summary.degraded}
            tone={m.summary.degraded > 0 ? "warn" : "rest"}
          />
          <Stat
            label="BROKEN"
            value={m.summary.broken}
            tone={m.summary.broken > 0 ? "fail" : "rest"}
          />
          <Stat label="STUB" value={m.summary.stub} tone="rest" />
          <Stat label="UNKNOWN" value={m.summary.unknown} tone="rest" />
        </div>
      </div>

      {/* Broken entities (the 2 actually-broken from manifest) */}
      {m.broken_entities.length > 0 && (
        <div className="flex flex-col gap-1">
          <span
            className="font-mono text-[10px] uppercase tabular-nums"
            style={{ color: colors.sumi[600], letterSpacing: "0.14em" }}
          >
            BROKEN ENTITIES · {m.broken_entities.length}
          </span>
          <div
            style={{
              border: `1px solid ${colors.sumi[700]}`,
              backgroundColor: colors.sumi[900],
            }}
          >
            {m.broken_entities.map((b) => (
              <div
                key={b.id}
                className="flex items-center gap-2 px-2"
                style={{
                  height: 26,
                  borderBottom: `1px solid ${colors.sumi[800]}`,
                  color: colors.torinoko,
                }}
                title={b.gap}
              >
                <StatusBadge state="fail" title={b.observed_status} />
                <span className="truncate text-sm" style={{ opacity: 0.92 }}>
                  {b.label}
                </span>
                <span
                  className="truncate text-xs ml-auto"
                  style={{ color: colors.sumi[600] }}
                >
                  {b.entity_type} · {b.gap}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 2. Active track + evidence */}
      <div
        style={{
          padding: "12px 16px",
          border: `1px solid ${colors.sumi[700]}`,
          backgroundColor: colors.sumi[900],
          display: "flex",
          flexDirection: "column",
          gap: 8,
        }}
      >
        <div className="flex items-center justify-between">
          <span
            className="font-mono text-[10px] uppercase tabular-nums"
            style={{ color: colors.sumi[600], letterSpacing: "0.14em" }}
          >
            ACTIVE TRACK
          </span>
          <div className="flex items-center gap-2">
            <StatusBadge state={badge.state} title={badge.tone} />
            <span
              className="font-mono text-[10px] uppercase tabular-nums"
              style={{ color: colors.aozora, letterSpacing: "0.12em" }}
            >
              {badge.label}
            </span>
          </div>
        </div>
        <span
          className="font-mono text-sm tabular-nums"
          style={{ color: colors.aozora, letterSpacing: "0.04em" }}
        >
          {track.id ?? "unknown"}
        </span>
        <p
          className="text-xs"
          style={{ color: colors.torinoko, opacity: 0.85, lineHeight: 1.4 }}
        >
          {track.description ?? "—"}
        </p>
        <div
          className="flex items-center gap-3 font-mono text-[10px] tabular-nums flex-wrap"
          style={{ color: colors.sumi[600], letterSpacing: "0.10em" }}
        >
          <span>OWNER {track.owner ?? "—"}</span>
          <span>·</span>
          <span>VERIFIED {track.verified_at ?? "—"}</span>
          <span>·</span>
          <span>TTL {track.ttl_days ?? "—"}d</span>
          <span>·</span>
          <span>
            CRITERIA{" "}
            <span style={{ color: colors.aozora }}>
              {track.evidence?.completion_progress?.passed ?? 0}/
              {track.evidence?.completion_progress?.total ??
                track.completion_criteria_count}
            </span>
          </span>
          <span>·</span>
          <span>{track.surfaces_count} SURFACES</span>
        </div>
        {/* Top 3 criteria pass/fail */}
        {track.evidence?.criteria && track.evidence.criteria.length > 0 && (
          <div className="flex flex-col gap-0.5" style={{ marginTop: 4 }}>
            {track.evidence.criteria.slice(0, 4).map((c) => (
              <div
                key={c.id}
                className="flex items-center gap-2 font-mono text-[10px] tabular-nums"
                style={{ height: 16, color: colors.sumi[600] }}
                title={c.detail}
              >
                <Glyph
                  kind={c.passed ? "check" : "cross"}
                  tone={c.passed ? "ok" : "fail"}
                />
                <span style={{ color: colors.torinoko, opacity: 0.85 }}>
                  {c.id}
                </span>
                <span className="truncate" style={{ marginLeft: "auto" }}>
                  {c.kind}
                </span>
              </div>
            ))}
            {track.evidence.criteria.length > 4 && (
              <span
                className="font-mono text-[10px] uppercase tabular-nums"
                style={{ color: colors.sumi[600], letterSpacing: "0.10em" }}
              >
                + {track.evidence.criteria.length - 4} more
              </span>
            )}
          </div>
        )}
      </div>

      {/* 3. Needs-human queue */}
      {needs.length > 0 && (
        <div className="flex flex-col gap-1">
          <div className="flex items-center justify-between">
            <span
              className="font-mono text-[10px] uppercase tabular-nums"
              style={{ color: colors.sumi[600], letterSpacing: "0.14em" }}
            >
              NEEDS JOHN · {needs.length}
            </span>
            <Link
              href="/dashboard/control-surface"
              className="font-mono text-[10px] uppercase flex items-center gap-1"
              style={{ color: colors.aozora, letterSpacing: "0.12em" }}
            >
              VIEW ALL <ArrowRight size={11} />
            </Link>
          </div>
          <div
            style={{
              border: `1px solid ${colors.sumi[700]}`,
              backgroundColor: colors.sumi[900],
            }}
          >
            {needs.slice(0, 5).map((r: NeedsHumanRow) => (
              <Link
                key={r.id}
                href="/dashboard/control-surface"
                className="flex items-center gap-2 px-2"
                style={{
                  height: 26,
                  borderBottom: `1px solid ${colors.sumi[800]}`,
                  textDecoration: "none",
                  color: colors.torinoko,
                }}
                title={`${r.next_action} · ${r.owner_module}`}
              >
                <StatusBadge
                  state={priorityBadge(r.priority)}
                  title={r.priority.toUpperCase()}
                />
                <span className="truncate text-sm" style={{ opacity: 0.92 }}>
                  {r.label}
                </span>
                <span
                  className="truncate text-xs"
                  style={{ color: colors.sumi[600] }}
                  title={r.next_action}
                >
                  {r.next_action}
                </span>
                <span
                  className="font-mono text-[10px] uppercase tabular-nums ml-auto"
                  style={{ color: colors.sumi[600], letterSpacing: "0.10em" }}
                >
                  {r.kind}
                </span>
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* 4. Broken Register */}
      {br.length > 0 && (
        <div className="flex flex-col gap-1">
          <div className="flex items-center justify-between">
            <span
              className="font-mono text-[10px] uppercase tabular-nums"
              style={{ color: colors.sumi[600], letterSpacing: "0.14em" }}
            >
              BROKEN REGISTER · {br.length}
            </span>
            <SourceChip>docs/state/BROKEN_REGISTER.md</SourceChip>
          </div>
          <div
            style={{
              border: `1px solid ${colors.sumi[700]}`,
              backgroundColor: colors.sumi[900],
            }}
          >
            {br.map((row: BrokenRegisterRow) => (
              <div
                key={row.id}
                className="flex items-center gap-2 px-2"
                style={{
                  height: 26,
                  borderBottom: `1px solid ${colors.sumi[800]}`,
                  color: colors.torinoko,
                }}
                title={row.next_action}
              >
                <StatusBadge
                  state={priorityBadge(row.priority)}
                  title={row.priority.toUpperCase()}
                />
                <StatusBadge
                  state={coherenceBadge(row.coherence_state)}
                  title={row.coherence_state}
                />
                <span className="truncate text-sm" style={{ opacity: 0.92 }}>
                  {row.label}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 5. PR queue + 6. Next PR ladder side by side */}
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        {/* PR queue (honest placeholder) */}
        <div
          style={{
            padding: "12px 16px",
            border: `1px solid ${colors.sumi[700]}`,
            backgroundColor: colors.sumi[900],
            display: "flex",
            flexDirection: "column",
            gap: 8,
            minHeight: 140,
          }}
        >
          <div className="flex items-center justify-between">
            <span
              className="font-mono text-[10px] uppercase tabular-nums"
              style={{ color: colors.sumi[600], letterSpacing: "0.14em" }}
            >
              PR QUEUE
            </span>
            <StatusBadge state="drift" title={pr.status} />
          </div>
          <span
            className="font-mono text-xs uppercase tabular-nums"
            style={{ color: colors.aozora, letterSpacing: "0.10em" }}
          >
            {pr.status}
          </span>
          <p
            className="text-xs"
            style={{ color: colors.torinoko, opacity: 0.85, lineHeight: 1.4 }}
          >
            {pr.next_action}
          </p>
          <SourceChip>{pr.source}</SourceChip>
        </div>

        {/* Next PR ladder */}
        <div
          style={{
            padding: "12px 16px",
            border: `1px solid ${colors.sumi[700]}`,
            backgroundColor: colors.sumi[900],
            display: "flex",
            flexDirection: "column",
            gap: 6,
            minHeight: 140,
          }}
        >
          <div className="flex items-center justify-between">
            <span
              className="font-mono text-[10px] uppercase tabular-nums"
              style={{ color: colors.sumi[600], letterSpacing: "0.14em" }}
            >
              NEXT PR LADDER · {ladder.length}
            </span>
            <SourceChip>codex+devin reconciled</SourceChip>
          </div>
          <div className="flex flex-col gap-1">
            {ladder.map((item: NextPrLadderItem) => (
              <div
                key={item.id}
                className="flex items-start gap-2"
                style={{ paddingTop: 4, paddingBottom: 4, borderTop: `1px solid ${colors.sumi[800]}` }}
                title={item.why}
              >
                <span
                  className="font-mono text-xs tabular-nums"
                  style={{
                    color: colors.aozora,
                    width: 18,
                    fontWeight: 500,
                  }}
                >
                  {item.rank}
                </span>
                <div className="flex flex-col" style={{ flex: 1 }}>
                  <span
                    className="text-sm truncate"
                    style={{ color: colors.torinoko, opacity: 0.92 }}
                  >
                    {item.title}
                  </span>
                  <span
                    className="font-mono text-[10px] tabular-nums"
                    style={{ color: colors.sumi[600], letterSpacing: "0.06em" }}
                  >
                    {item.id}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

function Stat({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: "active" | "rest" | "ok" | "warn" | "fail";
}) {
  return (
    <div
      className="flex flex-col gap-1"
      style={{
        padding: "10px 14px",
        border: `1px solid ${colors.sumi[700]}`,
        backgroundColor: colors.sumi[900],
      }}
    >
      <span
        className="font-mono text-[10px] uppercase tabular-nums"
        style={{ color: colors.sumi[600], letterSpacing: "0.14em" }}
      >
        {label}
      </span>
      <Numeral value={value} tone={tone} size="xl" />
    </div>
  );
}
