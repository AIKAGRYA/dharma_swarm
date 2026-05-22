"use client";

/**
 * WATCH zone landing — live instrument variant.
 *
 * Pulls useTelemetry to render the observability ribbon:
 * agents / active / cost / revenue / routing decisions. Pattern matches
 * /dashboard/cockpit but data source is the telemetry stack.
 */

import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { colors } from "@/lib/theme";
import { Numeral } from "@/components/primitives/Numeral";
import { Glyph } from "@/components/primitives/Glyph";
import { ZONES } from "@/components/dashboard/ZoneTabs";
import { useTelemetry } from "@/hooks/useTelemetry";

const ZONE = ZONES.find((z) => z.id === "watch")!;

export default function WatchLandingPage() {
  const { overview, routing, economics, isLoading } = useTelemetry();

  const net = economics?.net_usd ?? 0;
  const netTone: "ok" | "warn" | "rest" = net > 0 ? "ok" : net < 0 ? "warn" : "rest";

  return (
    <div className="flex flex-col gap-6">
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
                10s refresh
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

      {/* Live instrument ribbon */}
      <section
        className="grid grid-cols-2 gap-3 md:grid-cols-5"
        style={{ borderTop: `1px solid ${colors.sumi[700]}`, paddingTop: 16 }}
      >
        <Stat label="AGENTS" value={overview?.agent_count ?? 0} tone="active" isLoading={isLoading} />
        <Stat label="ACTIVE" value={overview?.active_agents ?? 0} tone="ok" isLoading={isLoading} />
        <Stat
          label="ROUTING"
          value={routing?.total_decisions ?? 0}
          tone="rest"
          isLoading={isLoading}
        />
        <Stat
          label="COST·USD"
          value={economics?.total_cost_usd ?? 0}
          tone="rest"
          isLoading={isLoading}
          formatter={fmtUsd}
        />
        <Stat
          label="NET·USD"
          value={economics?.net_usd ?? 0}
          tone={netTone}
          isLoading={isLoading}
          formatter={fmtUsd}
        />
      </section>

      {/* Top routing paths preview */}
      {routing && Object.keys(routing.path_counts).length > 0 && (
        <section className="flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <h2
              className="font-mono text-xs uppercase"
              style={{ color: colors.sumi[600], letterSpacing: "0.14em" }}
            >
              TOP ROUTING PATHS
            </h2>
            <Link
              href="/dashboard/telemetry"
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
            {Object.entries(routing.path_counts)
              .sort(([, a], [, b]) => b - a)
              .slice(0, 5)
              .map(([path, count]) => (
                <div
                  key={path}
                  className="flex items-center gap-2 px-2"
                  style={{
                    height: 26,
                    borderBottom: `1px solid ${colors.sumi[800]}`,
                  }}
                >
                  <span
                    className="truncate text-sm"
                    style={{ color: colors.torinoko, opacity: 0.92 }}
                  >
                    {path || "unknown"}
                  </span>
                  <Numeral value={count} tone="rest" size="sm" className="ml-auto" />
                </div>
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

      <footer
        className="font-mono text-[10px] uppercase"
        style={{
          color: colors.sumi[600],
          letterSpacing: "0.12em",
          borderTop: `1px solid ${colors.sumi[700]}`,
          paddingTop: 12,
        }}
      >
        ⌘K to jump anywhere · 7 zones
      </footer>
    </div>
  );
}

function fmtUsd(v: number): string {
  const sign = v < 0 ? "-" : "";
  const abs = Math.abs(v);
  if (abs >= 1000) return `${sign}$${(abs / 1000).toFixed(1)}k`;
  return `${sign}$${abs.toFixed(2)}`;
}

function Stat({
  label,
  value,
  tone,
  isLoading,
  formatter,
}: {
  label: string;
  value: number;
  tone: "active" | "rest" | "ok" | "warn" | "fail";
  isLoading: boolean;
  formatter?: (v: number) => string;
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
        <Numeral value={formatter ? formatter(value) : value} tone={tone} size="xl" />
      )}
    </div>
  );
}
