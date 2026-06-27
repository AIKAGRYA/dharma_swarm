"use client";

import { useState } from "react";
import type {
  TelemetryPolicyDecision,
  TelemetryRouteDecision,
  TelemetryRouteTraceStage,
} from "@/lib/telemetry";
import { colors } from "@/lib/theme";
import { timeAgo } from "@/lib/utils";

const LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ".split("");
const VIEWBOX = 920;
const CENTER = VIEWBOX / 2;
const RADII = [384, 297.6, 211.2, 124.8, 38.4];

const STAGE_COLORS: Record<string, string> = {
  decision_path: "#da1e28",
  frontier_precision: "#8a3ffc",
  candidate_seed: "#f1c21b",
  availability_filter: "#ff7eb6",
  smart_router: "#8d8d8d",
  telemetry_overlay: "#42be65",
  selection: "#fa4d56",
};

const RING_LABELS = [
  { label: "Plugboard", stage: "decision_path" },
  { label: "Rotor 1", stage: "candidate_seed" },
  { label: "Rotor 2", stage: "availability_filter" },
  { label: "Rotor 3", stage: "smart_router" },
  { label: "Reflector", stage: "telemetry_overlay" },
] as const;

function isRouteTraceStage(value: unknown): value is TelemetryRouteTraceStage {
  if (!value || typeof value !== "object") return false;
  const stage = (value as { stage?: unknown }).stage;
  return typeof stage === "string" && stage.trim().length > 0;
}

function routeTraceFromMetadata(
  metadata: Record<string, unknown>,
): TelemetryRouteTraceStage[] {
  const rawTrace = metadata.route_trace;
  if (!Array.isArray(rawTrace)) return [];
  return rawTrace.filter(isRouteTraceStage).slice(0, 8);
}

function fallbackTrace(route: TelemetryRouteDecision): TelemetryRouteTraceStage[] {
  const chain = Array.isArray(route.metadata.candidate_chain)
    ? route.metadata.candidate_chain
        .map((item) => (typeof item === "string" ? item : ""))
        .filter(Boolean)
    : [];
  const selected = route.selected_provider ? [route.selected_provider] : [];
  const routed = chain.length > 0 ? chain : selected;
  return [
    {
      stage: "decision_path",
      applied: true,
      reasons: route.reasons.slice(0, 4),
      metadata: {
        path: route.route_path,
        confidence: Number(route.confidence.toFixed(3)),
        requires_human: route.requires_human,
      },
    },
    {
      stage: "candidate_seed",
      output_providers: routed,
      metadata: { path: route.route_path, legacy_projection: true },
    },
    {
      stage: "availability_filter",
      input_providers: routed,
      output_providers: routed,
      metadata: {
        path: route.metadata.source === "session_event" ? "session event" : "available",
        legacy_projection: true,
      },
    },
    {
      stage: "smart_router",
      input_providers: routed,
      output_providers: routed,
      applied: false,
      reasons: ["no smart-router trace on legacy telemetry row"],
      metadata: { path: "bypass", legacy_projection: true },
    },
    {
      stage: "telemetry_overlay",
      input_providers: routed,
      output_providers: routed,
      applied: false,
      reasons: ["awaiting provider-policy trace row"],
      metadata: { path: "pending", legacy_projection: true },
    },
    {
      stage: "selection",
      output_providers: selected,
      metadata: {
        selected_provider: route.selected_provider || "unassigned",
        selected_model_hint: route.selected_model_hint || "",
      },
    },
  ];
}

function latestRoute(routes: TelemetryRouteDecision[]): TelemetryRouteDecision | null {
  if (routes.length === 0) return null;
  return [...routes].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
  )[0];
}

function latestPolicyForRoute(
  route: TelemetryRouteDecision | null,
  policies: TelemetryPolicyDecision[],
): TelemetryPolicyDecision | null {
  if (!route) return null;
  const matches = policies.filter((policy) => {
    if (route.task_id && policy.task_id === route.task_id) return true;
    if (route.run_id && policy.run_id === route.run_id) return true;
    return false;
  });
  return matches.sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
  )[0] ?? null;
}

function stageColor(stage: string): string {
  return STAGE_COLORS[stage] ?? "#da1e28";
}

function selectedMetadata(stage: TelemetryRouteTraceStage): string {
  const metadata = stage.metadata ?? {};
  const selected = metadata.selected_provider;
  if (typeof selected === "string" && selected) return selected;
  const path = metadata.path;
  if (typeof path === "string" && path) return path;
  const tier = metadata.cost_tier;
  if (typeof tier === "string" && tier) return tier;
  return stage.applied === false ? "bypass" : "active";
}

function hashText(value: string): number {
  return [...value].reduce((hash, char) => {
    return (hash * 31 + char.charCodeAt(0)) % 9973;
  }, 23);
}

function letterIndexFromText(value: string, offset = 0): number {
  const clean = value.toUpperCase().replace(/[^A-Z]/g, "");
  const seed = clean || "ENIGMA";
  const charCode = seed.charCodeAt(Math.abs(offset) % seed.length);
  return (charCode + hashText(seed) + offset) % LETTERS.length;
}

function pointOnRing(radius: number, index: number, phase = 0): { x: number; y: number } {
  const angle = Math.PI * 2 * ((index + phase) / LETTERS.length);
  return {
    x: CENTER + Math.cos(angle) * radius,
    y: CENTER + Math.sin(angle) * radius,
  };
}

function wirePath(
  outerRadius: number,
  innerRadius: number,
  source: number,
  target: number,
  wobble: number,
): string {
  const start = pointOnRing(outerRadius, source);
  const end = pointOnRing(innerRadius, target);
  const midRadius = (outerRadius + innerRadius) / 2;
  const c1 = pointOnRing(midRadius, source + wobble * 0.55, wobble * 0.05);
  const c2 = pointOnRing(midRadius, target - wobble * 0.45, -wobble * 0.04);
  return `M ${start.x.toFixed(2)} ${start.y.toFixed(2)} C ${c1.x.toFixed(2)} ${c1.y.toFixed(2)}, ${c2.x.toFixed(2)} ${c2.y.toFixed(2)}, ${end.x.toFixed(2)} ${end.y.toFixed(2)}`;
}

function reflectorPath(index: number): string {
  const source = pointOnRing(RADII[4], index);
  const target = pointOnRing(RADII[4], (index + 13) % LETTERS.length);
  const c1 = pointOnRing(RADII[4] * 1.9, index + 2.5);
  const c2 = pointOnRing(RADII[4] * 1.9, index + 10.5);
  return `M ${source.x.toFixed(2)} ${source.y.toFixed(2)} C ${c1.x.toFixed(2)} ${c1.y.toFixed(2)}, ${c2.x.toFixed(2)} ${c2.y.toFixed(2)}, ${target.x.toFixed(2)} ${target.y.toFixed(2)}`;
}

interface RouteTraceMatrixProps {
  routes: TelemetryRouteDecision[];
  policies: TelemetryPolicyDecision[];
  isLoading: boolean;
}

export function RouteTraceMatrix({
  routes,
  policies,
  isLoading,
}: RouteTraceMatrixProps) {
  const [showLabels, setShowLabels] = useState(false);
  const [output, setOutput] = useState("");
  const route = latestRoute(routes);
  const policy = latestPolicyForRoute(route, policies);
  const routeTrace = route ? routeTraceFromMetadata(route.metadata) : [];
  const traced = routeTrace.length > 0;
  const trace = route ? (traced ? routeTrace : fallbackTrace(route)) : [];
  const selected = route?.selected_provider || "none";
  const inputText = route?.action_name ? route.action_name.replace(/[^a-zA-Z]/g, " ").trim() : "Hello world";
  const outputLetter = LETTERS[
    letterIndexFromText(selected !== "none" ? selected : route?.route_path ?? "Swarm", 11)
  ];

  const signalIndexes = [
    letterIndexFromText(inputText, 0),
    letterIndexFromText(selectedMetadata(trace[0] ?? { stage: "decision_path" }), 4),
    letterIndexFromText(selectedMetadata(trace[1] ?? { stage: "candidate_seed" }), 8),
    letterIndexFromText(selectedMetadata(trace[2] ?? { stage: "availability_filter" }), 12),
    letterIndexFromText(selectedMetadata(trace[3] ?? { stage: "smart_router" }), 16),
    letterIndexFromText(selectedMetadata(trace[4] ?? { stage: "telemetry_overlay" }), 20),
  ];

  return (
    <section
      className="overflow-hidden border border-[#e5e5e5] bg-white text-[#242424]"
      data-route-visual="observable-enigma"
    >
      <div
        className="grid gap-5 px-6 py-6 lg:grid-cols-[235px_minmax(720px,1fr)]"
        style={{
          fontFamily:
            "'IBM Plex Mono', 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
        }}
      >
        <aside className="text-[15px] leading-tight">
          <h2 className="mb-2 text-[28px] font-bold tracking-tight text-[#2a2a2a]">
            Enigma machine
          </h2>

          <label className="mb-5 flex items-center gap-1 text-[17px]">
            <input
              checked={showLabels}
              onChange={(event) => setShowLabels(event.target.checked)}
              type="checkbox"
              className="h-4 w-4 appearance-none border border-[#777] bg-white checked:bg-[#333]"
            />
            Labels
          </label>

          <div className="mb-4">
            <div className="mb-2 text-[19px] font-bold">Rotors</div>
            <div className="flex gap-2">
              {["I", "II", "III"].map((value) => (
                <select
                  key={value}
                  aria-label={`Rotor ${value}`}
                  defaultValue={value}
                  className="h-6 w-[58px] border border-[#d6d6d6] bg-[#f1f1f1] px-2 text-sm text-[#222]"
                >
                  <option>{value}</option>
                </select>
              ))}
            </div>
          </div>

          <div className="mb-4">
            <div className="mb-2 text-[19px] font-bold">Reflector</div>
            <select
              aria-label="Reflector"
              defaultValue="B"
              className="h-6 w-[54px] border border-[#d6d6d6] bg-[#f1f1f1] px-2 text-sm text-[#222]"
            >
              <option>B</option>
            </select>
          </div>

          <label className="mb-4 block">
            <div className="mb-2 text-[19px] font-bold">Plugboard</div>
            <input
              value="AB HK"
              readOnly
              className="h-9 w-[196px] border border-[#d6d6d6] bg-white px-3 text-lg font-bold"
            />
          </label>

          <label className="mb-5 block">
            <div className="mb-2 text-[19px] font-bold">Speed</div>
            <input type="range" min={1} max={16} value={1} readOnly className="w-[196px]" />
          </label>

          <label className="mb-2 block">
            <div className="mb-2 text-[19px] font-bold">Input</div>
            <input
              value={inputText.slice(0, 20) || "Hello world"}
              readOnly
              className="h-9 w-[196px] border border-[#d6d6d6] bg-white px-3 text-lg font-bold"
            />
          </label>

          <button
            className="mb-4 h-8 w-[196px] bg-black text-lg font-bold text-white"
            onClick={() => setOutput(outputLetter)}
            type="button"
          >
            Encrypt
          </button>

          <div className="mb-4">
            <div className="mb-2 text-[19px] font-bold">Output</div>
            <div className="h-8 w-[286px] max-w-full border border-black bg-white px-2 py-1 text-lg">
              {output || "\u00a0"}
            </div>
          </div>

          <p className="max-w-[205px] text-[14px] leading-[1.45] text-[#343434]">
            This is a simulated route machine. Signals enter at the boundary,
            move through the wire matrix, and exit.
          </p>

          <div className="mt-5 border-t border-[#e5e5e5] pt-3 text-[12px] leading-relaxed text-[#666]">
            <div>{isLoading ? "Syncing" : "Live"} telemetry</div>
            <div>{traced ? "Trace source" : "Legacy projection"}</div>
            <div>{route ? timeAgo(route.created_at) : "No route pulse"}</div>
            <div>{policy?.decision ?? "policy pending"}</div>
          </div>
        </aside>

        <div className="min-w-[720px] overflow-x-auto">
          <svg
            aria-label="Circular Enigma-style live route wiring diagram"
            className="block h-auto w-full max-w-[920px]"
            data-capture="observable-enigma-chart"
            viewBox={`0 0 ${VIEWBOX} ${VIEWBOX}`}
          >
            <rect width={VIEWBOX} height={VIEWBOX} fill="#fff" />

            {RADII.map((radius, index) => (
              <circle
                key={`ring-${radius}`}
                cx={CENTER}
                cy={CENTER}
                r={radius}
                fill="none"
                stroke={index === 0 ? "#000" : "#888"}
                strokeWidth={index === 0 ? 1.8 : 1.5}
                opacity={index === 0 ? 1 : 0.78}
              />
            ))}

            {LETTERS.map((_, sourceIndex) => {
              return RADII.slice(0, -1).map((radius, ringIndex) => {
                const target = (sourceIndex * (ringIndex * 4 + 5) + ringIndex * 7 + 3) % 26;
                return (
                  <path
                    key={`wire-${ringIndex}-${sourceIndex}`}
                    d={wirePath(radius, RADII[ringIndex + 1], sourceIndex, target, ringIndex + 1)}
                    fill="none"
                    stroke="#777"
                    strokeWidth={ringIndex === 0 ? 0.9 : 0.75}
                    opacity={ringIndex === 0 ? 0.58 : 0.48}
                  />
                );
              });
            })}

            {LETTERS.slice(0, 13).map((_, index) => (
              <path
                key={`reflector-${index}`}
                d={reflectorPath(index)}
                fill="none"
                stroke="#777"
                strokeWidth="0.8"
                opacity="0.52"
              />
            ))}

            {LETTERS.map((letter, index) => {
              const point = pointOnRing(RADII[0], index);
              const innerPoint = pointOnRing(RADII[1], index);
              const label = pointOnRing(RADII[0] + 31, index);
              return (
                <g key={letter}>
                  <line
                    x1={innerPoint.x}
                    y1={innerPoint.y}
                    x2={point.x}
                    y2={point.y}
                    stroke="#999"
                    strokeWidth="0.9"
                    opacity="0.58"
                  />
                  <circle
                    cx={point.x}
                    cy={point.y}
                    r={12.5}
                    fill="#fff"
                    stroke="#000"
                    strokeWidth="1"
                  />
                  <text
                    x={label.x}
                    y={label.y}
                    dominantBaseline="middle"
                    fill="#000"
                    fontFamily="IBM Plex Mono, ui-monospace, monospace"
                    fontSize="25"
                    textAnchor="middle"
                  >
                    {letter}
                  </text>
                </g>
              );
            })}

            {showLabels &&
              RING_LABELS.map((ring, index) => {
                const outer = RADII[index];
                const inner = RADII[index + 1] ?? 0;
                const y = CENTER - (outer + inner) / 2;
                return (
                  <g key={`label-${ring.label}`} opacity="0.92">
                    <rect x={CENTER - 12} y={y - 14} width={126} height={26} fill="#111" />
                    <text
                      x={CENTER}
                      y={y}
                      dominantBaseline="middle"
                      fill="#fff"
                      fontFamily="IBM Plex Mono, ui-monospace, monospace"
                      fontSize="17"
                      fontWeight="700"
                    >
                      {ring.label}
                    </text>
                  </g>
                );
              })}

            {trace.slice(0, 5).map((stage, index) => {
              const source = signalIndexes[index];
              const target = signalIndexes[index + 1] ?? signalIndexes[index];
              const color = stageColor(stage.stage);
              return (
                <path
                  key={`signal-${stage.stage}-${index}`}
                  d={wirePath(RADII[index], RADII[index + 1], source, target, index + 1)}
                  fill="none"
                  stroke={color}
                  strokeDasharray={stage.applied === false ? "7 7" : undefined}
                  strokeLinecap="round"
                  strokeWidth="4.4"
                  opacity="0.88"
                />
              );
            })}

            {signalIndexes.map((letterIndex, index) => {
              const ringIndex = Math.min(index, RADII.length - 1);
              const point = pointOnRing(RADII[ringIndex], letterIndex);
              const stage = trace[Math.max(0, Math.min(index, trace.length - 1))];
              const color = stage ? stageColor(stage.stage) : "#da1e28";
              return (
                <circle
                  key={`signal-dot-${index}`}
                  cx={point.x}
                  cy={point.y}
                  r={index === 0 ? 8 : 6.5}
                  fill={index === 0 ? "#da1e28" : "#fff"}
                  stroke={color}
                  strokeWidth="3"
                />
              );
            })}

            <text
              x={CENTER}
              y={CENTER + RADII[0] + 58}
              fill={colors.sumi[600]}
              fontFamily="IBM Plex Mono, ui-monospace, monospace"
              fontSize="12"
              textAnchor="middle"
            >
              {route
                ? `${route.route_path} / ${selected} / ${route.confidence.toFixed(2)}`
                : "Awaiting routed telemetry"}
            </text>
          </svg>
        </div>
      </div>
    </section>
  );
}
