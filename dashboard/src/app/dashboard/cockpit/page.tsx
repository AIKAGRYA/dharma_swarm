"use client";

/**
 * COCKPIT zone landing — live instrument variant.
 *
 * Unlike the other 6 zone landings (which use the shared ZoneLanding card
 * directory), COCKPIT pulls live useControlSurface data and renders the
 * active-state ribbon — Numerals are the protagonist, freshness is
 * pulsed, drift / fail counts are StatusBadges.
 *
 * This is the proof that zone landings can be living instruments. The
 * pattern can extend to WATCH (live observatory) and TALK (provider
 * availability) when their per-route hooks exist.
 */

import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { colors } from "@/lib/theme";
import { Numeral } from "@/components/primitives/Numeral";
import { StatusBadge, type StatusBadgeState } from "@/components/primitives/StatusBadge";
import { Glyph } from "@/components/primitives/Glyph";
import { ZONES } from "@/components/dashboard/ZoneTabs";
import {
  useControlSurfaceRows,
  useControlSurfaceSummary,
} from "@/hooks/useControlSurface";
import { useRepoTruth } from "@/hooks/useRepoTruth";

const ZONE = ZONES.find((z) => z.id === "cockpit")!;

export default function CockpitLandingPage() {
  const { rows, isLoading } = useControlSurfaceRows();
  const { summary } = useControlSurfaceSummary();
  const repo = useRepoTruth();

  const needsJohn = rows.filter((r) => r.human_decision_required);
  const top3NeedsJohn = needsJohn
    .sort((a, b) => {
      const order: Record<string, number> = { p0: 0, p1: 1, p2: 2, backlog: 3 };
      return (order[a.priority] ?? 9) - (order[b.priority] ?? 9);
    })
    .slice(0, 3);

  return (
    <div className="flex flex-col gap-6">
      {/* Zone header */}
      <header
        className="flex flex-col gap-2"
        style={{ borderLeft: `2px solid ${colors.aozora}`, paddingLeft: 16 }}
      >
        <div className="flex items-baseline gap-4">
          <h1
            className="font-mono text-3xl uppercase tabular-nums"
            style={{ color: colors.aozora, letterSpacing: "0.10em", fontWeight: 500 }}
          >
            {ZONE.label}
          </h1>
          <span
            className="font-mono text-sm uppercase"
            style={{ color: colors.sumi[600], letterSpacing: "0.14em" }}
          >
            {ZONE.verb}
          </span>
          <div className="flex-1" />
          {!isLoading && (
            <span className="flex items-center gap-2">
              <Glyph kind="dot" tone="ok" pulse title="Live" />
              <span
                className="font-mono text-[10px] uppercase tabular-nums"
                style={{ color: colors.sumi[600], letterSpacing: "0.12em" }}
              >
                LIVE
              </span>
            </span>
          )}
        </div>
        <p
          className="text-sm"
          style={{ color: colors.torinoko, opacity: 0.85, maxWidth: 720 }}
        >
          {ZONE.description}
        </p>
      </header>

      {/* Live instrument ribbon — Numerals are protagonist */}
      <section
        className="grid grid-cols-2 gap-3 md:grid-cols-4"
        style={{ borderTop: `1px solid ${colors.sumi[700]}`, paddingTop: 16 }}
      >
        <Stat
          label="ROWS"
          value={summary?.total ?? 0}
          tone="active"
          isLoading={isLoading}
        />
        <Stat
          label="BOUND"
          value={summary?.bound ?? 0}
          tone="ok"
          isLoading={isLoading}
        />
        <Stat
          label="DRIFT"
          value={summary?.drifted ?? 0}
          tone={summary && summary.drifted > 0 ? "warn" : "rest"}
          isLoading={isLoading}
        />
        <Stat
          label="NEEDS JOHN"
          value={summary?.human_decision_required_count ?? 0}
          tone={
            summary && summary.human_decision_required_count > 0 ? "fail" : "rest"
          }
          isLoading={isLoading}
        />
      </section>

      {/* REPO TRUTH — single source of truth for repo state */}
      <section className="flex flex-col gap-2">
        <div className="flex items-center justify-between">
          <h2
            className="font-mono text-xs uppercase"
            style={{ color: colors.sumi[600], letterSpacing: "0.14em" }}
          >
            REPO TRUTH · SSoT
          </h2>
          <span
            className="font-mono text-[10px] uppercase tabular-nums"
            style={{ color: colors.sumi[600], letterSpacing: "0.12em" }}
          >
            {repo.activeTrack?.companion_manifest ?? "ACTIVE_SURFACE_MANIFEST.yaml"} · ACTIVE_TRACK.yaml · git
          </span>
        </div>

        {/* Manifest health ribbon */}
        <div className="grid grid-cols-2 gap-3 md:grid-cols-6">
          <Stat
            label="MANIFEST"
            value={repo.summary?.summary.total ?? 0}
            tone="active"
            isLoading={repo.isLoading}
          />
          <Stat
            label="LIVE"
            value={repo.summary?.summary.live ?? 0}
            tone="ok"
            isLoading={repo.isLoading}
          />
          <Stat
            label="DEGRADED"
            value={repo.summary?.summary.degraded ?? 0}
            tone={repo.summary && repo.summary.summary.degraded > 0 ? "warn" : "rest"}
            isLoading={repo.isLoading}
          />
          <Stat
            label="BROKEN"
            value={repo.summary?.summary.broken ?? 0}
            tone={repo.summary && repo.summary.summary.broken > 0 ? "fail" : "rest"}
            isLoading={repo.isLoading}
          />
          <Stat
            label="STUB"
            value={repo.summary?.summary.stub ?? 0}
            tone="rest"
            isLoading={repo.isLoading}
          />
          <Stat
            label="UNKNOWN"
            value={repo.summary?.summary.unknown ?? 0}
            tone="rest"
            isLoading={repo.isLoading}
          />
        </div>

        {/* Active track + recent commits side by side */}
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {/* Active track card */}
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
              {repo.activeTrack?.status && (
                <StatusBadge
                  state={trackStatusBadge(repo.activeTrack.status)}
                  title={repo.activeTrack.status}
                />
              )}
            </div>
            {repo.activeTrack ? (
              <>
                <span
                  className="font-mono text-sm tabular-nums"
                  style={{ color: colors.aozora, letterSpacing: "0.04em" }}
                >
                  {repo.activeTrack.id ?? "unknown"}
                </span>
                <p
                  className="text-xs"
                  style={{ color: colors.torinoko, opacity: 0.85, lineHeight: 1.4 }}
                >
                  {repo.activeTrack.description ?? "—"}
                </p>
                <div
                  className="flex items-center gap-3 font-mono text-[10px] tabular-nums"
                  style={{ color: colors.sumi[600], letterSpacing: "0.10em" }}
                >
                  <span>OWNER {repo.activeTrack.owner ?? "—"}</span>
                  <span>·</span>
                  <span>VERIFIED {repo.activeTrack.verified_at ?? "—"}</span>
                  <span>·</span>
                  <span>TTL {repo.activeTrack.ttl_days ?? "—"}d</span>
                  <span>·</span>
                  <span>{repo.activeTrack.completion_criteria_count} CRITERIA</span>
                  <span>·</span>
                  <span>{repo.activeTrack.surfaces_count} SURFACES</span>
                </div>
              </>
            ) : (
              <span
                className="font-mono text-xs uppercase"
                style={{ color: colors.sumi[600], letterSpacing: "0.12em" }}
              >
                {repo.isLoading ? "Loading…" : "No active track"}
              </span>
            )}
          </div>

          {/* Recent commits card */}
          <div
            style={{
              padding: "12px 16px",
              border: `1px solid ${colors.sumi[700]}`,
              backgroundColor: colors.sumi[900],
              display: "flex",
              flexDirection: "column",
              gap: 6,
            }}
          >
            <div className="flex items-center justify-between">
              <span
                className="font-mono text-[10px] uppercase tabular-nums"
                style={{ color: colors.sumi[600], letterSpacing: "0.14em" }}
              >
                RECENT COMMITS
              </span>
              {repo.recentCommits?.branch && (
                <span
                  className="font-mono text-[10px] tabular-nums"
                  style={{ color: colors.aozora, letterSpacing: "0.06em" }}
                >
                  {repo.recentCommits.branch}
                </span>
              )}
            </div>
            <div className="flex flex-col gap-1" style={{ minHeight: 80 }}>
              {repo.recentCommits?.commits.slice(0, 6).map((c) => (
                <div
                  key={c.sha}
                  className="flex items-center gap-2 font-mono text-xs tabular-nums"
                  style={{ height: 18, lineHeight: 1.2 }}
                  title={`${c.subject} (by ${c.author}, ${c.relative})`}
                >
                  <span style={{ color: colors.aozora, width: 70 }}>
                    {c.short_sha}
                  </span>
                  <span
                    className="truncate"
                    style={{ color: colors.torinoko, opacity: 0.92, flex: 1 }}
                  >
                    {c.subject}
                  </span>
                  <span
                    style={{ color: colors.sumi[600], whiteSpace: "nowrap" }}
                  >
                    {c.relative}
                  </span>
                </div>
              ))}
              {!repo.recentCommits && (
                <span
                  className="font-mono text-xs uppercase"
                  style={{ color: colors.sumi[600], letterSpacing: "0.12em" }}
                >
                  {repo.isLoading ? "Loading…" : "git log unavailable"}
                </span>
              )}
            </div>
            {repo.recentCommits && (
              <span
                className="font-mono text-[10px] uppercase tabular-nums"
                style={{ color: colors.sumi[600], letterSpacing: "0.12em" }}
              >
                showing {Math.min(6, repo.recentCommits.count)} of {repo.recentCommits.count}
              </span>
            )}
          </div>
        </div>
      </section>

      {/* Top 3 needs-john preview */}
      {top3NeedsJohn.length > 0 && (
        <section className="flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <h2
              className="font-mono text-xs uppercase"
              style={{ color: colors.sumi[600], letterSpacing: "0.14em" }}
            >
              TOP {top3NeedsJohn.length} · NEEDS JOHN
            </h2>
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
            {top3NeedsJohn.map((row) => (
              <Link
                key={row.id}
                href="/dashboard/control-surface"
                className="flex items-center gap-2 px-2"
                style={{
                  height: 26,
                  borderBottom: `1px solid ${colors.sumi[800]}`,
                  textDecoration: "none",
                  color: colors.torinoko,
                }}
              >
                <StatusBadge
                  state={
                    row.priority === "p0"
                      ? "fail"
                      : row.priority === "p1"
                        ? "stale"
                        : "drift"
                  }
                  title={row.priority.toUpperCase()}
                />
                <span className="truncate text-sm" style={{ opacity: 0.92 }}>
                  {row.label}
                </span>
                <span
                  className="truncate text-xs ml-auto"
                  style={{ color: colors.sumi[600] }}
                >
                  {row.next_action || "inspect"}
                </span>
              </Link>
            ))}
          </div>
        </section>
      )}

      {/* Constituent surface cards */}
      <section className="flex flex-col gap-2">
        <h2
          className="font-mono text-xs uppercase"
          style={{ color: colors.sumi[600], letterSpacing: "0.14em" }}
        >
          SURFACES · {ZONE.routes.length}
        </h2>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          {ZONE.routes.map((route) => (
            <Link
              key={route.path}
              href={route.path}
              className="group flex flex-col gap-2"
              style={{
                padding: "14px 16px",
                border: `1px solid ${colors.sumi[700]}`,
                backgroundColor: colors.sumi[900],
                textDecoration: "none",
                minHeight: 110,
              }}
            >
              <div className="flex items-center justify-between">
                <span
                  className="font-mono text-xs uppercase tabular-nums"
                  style={{
                    color: colors.aozora,
                    letterSpacing: "0.12em",
                    fontWeight: 500,
                  }}
                >
                  {route.label}
                </span>
                <ArrowRight
                  size={14}
                  style={{ color: colors.sumi[600] }}
                  className="transition-transform group-hover:translate-x-1"
                />
              </div>
              <p
                className="text-xs"
                style={{ color: colors.torinoko, opacity: 0.85, lineHeight: 1.5 }}
              >
                {route.description}
              </p>
              <span
                className="font-mono text-[10px] tabular-nums"
                style={{ color: colors.sumi[600], marginTop: "auto" }}
              >
                {route.path}
              </span>
            </Link>
          ))}
        </div>
      </section>

      {/* Freshness footer */}
      <footer
        className="font-mono text-[10px] uppercase flex items-center justify-between"
        style={{
          color: colors.sumi[600],
          letterSpacing: "0.12em",
          borderTop: `1px solid ${colors.sumi[700]}`,
          paddingTop: 12,
        }}
      >
        <span>⌘K to jump anywhere · 7 zones</span>
        {summary?.generated_at && (
          <span className="tabular-nums">
            generated {summary.generated_at} · sources {summary.sources_consulted.length}
          </span>
        )}
      </footer>
    </div>
  );
}

function trackStatusBadge(status: string): StatusBadgeState {
  const s = status.toUpperCase();
  if (s === "ACTIVE" || s === "SHIPPABLE" || s === "SHIPPED") return "pass";
  if (s === "QUEUED" || s === "DRAFT" || s === "DEFERRED") return "drift";
  if (s === "STALE" || s === "TTL_EXPIRED") return "stale";
  if (s === "FAILED" || s === "BLOCKED") return "fail";
  return "drift";
}

function Stat({
  label,
  value,
  tone,
  isLoading,
}: {
  label: string;
  value: number;
  tone: "active" | "rest" | "ok" | "warn" | "fail";
  isLoading: boolean;
}) {
  return (
    <div
      className="flex flex-col gap-1"
      style={{
        padding: "12px 16px",
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
      {isLoading ? (
        <span
          className="font-mono text-xl"
          style={{ color: colors.sumi[700], fontFeatureSettings: "'tnum' 1" }}
        >
          ···
        </span>
      ) : (
        <Numeral value={value} tone={tone} size="xl" />
      )}
    </div>
  );
}
