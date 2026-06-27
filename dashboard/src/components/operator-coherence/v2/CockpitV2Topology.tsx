"use client";

import { useMemo } from "react";
import {
  Background,
  BackgroundVariant,
  Controls,
  Handle,
  MiniMap,
  Position,
  ReactFlow,
  type Edge,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { OperatorCoherenceReport } from "@/lib/operatorCoherence";
import {
  buildTopology,
  CLUSTER_ORDER,
  freshnessLabel,
  nodeMatchesFilter,
  type CockpitGraph,
  type CockpitNode,
  type InspectItem,
  type TruthTone,
} from "./cockpitV2Model";

const TONE_HEX: Record<TruthTone, string> = {
  ok: "#8FA89B",
  warn: "#D4A855",
  danger: "#C19392",
  info: "#4FD1D9",
  muted: "#4E5060",
};

const CLUSTER_LABEL: Record<string, string> = {
  system: "System",
  readiness: "Readiness categories",
  tracks: "Tracks / organs",
  actions: "Proposal actions",
  live_ops: "Live ops surfaces",
  receipts: "Receipts",
  uncertainty: "Uncertain / unavailable",
};

type RFNodeData = {
  node: CockpitNode;
  selected: boolean;
  dimmed: boolean;
  onInspect: (item: InspectItem) => void;
};

function CockpitFlowNode({ data }: NodeProps) {
  const { node, selected, dimmed, onInspect } = data as unknown as RFNodeData;
  const hex = TONE_HEX[node.tone];
  // Node size encodes evidence + risk (spec 8.5). Opacity encodes freshness.
  const riskBoost = node.risk === "critical" ? 18 : node.risk === "high" ? 12 : node.risk === "medium" ? 6 : 0;
  const size = Math.min(120, 46 + node.evidenceCount * 5 + riskBoost);
  const freshnessOpacity = node.freshness === "fresh" ? 1 : node.freshness === "aging" ? 0.82 : node.freshness === "stale" ? 0.6 : 0.4;
  const opacity = dimmed ? Math.min(0.22, freshnessOpacity) : freshnessOpacity;
  const operatorRing = node.authority === "operator_required";
  return (
    <button
      type="button"
      onClick={() => onInspect(node.inspect)}
      title={`${node.label} · ${node.status} · ${freshnessLabel(node.freshness)}`}
      style={{
        width: size,
        height: size,
        opacity,
        borderColor: selected ? "#D4A855" : hex,
        borderWidth: selected || operatorRing ? 2 : 1,
        boxShadow: selected ? "0 0 0 3px rgba(212,168,85,0.35)" : operatorRing ? "0 0 0 2px rgba(212,168,85,0.25)" : "none",
      }}
      className={`flex flex-col items-center justify-center gap-0.5 rounded-full border bg-sumi-950/85 px-1 text-center ${
        node.pulse ? "cockpit-pulse" : ""
      }`}
    >
      <Handle type="target" position={Position.Top} className="!h-1 !w-1 !border-0 !bg-sumi-700" />
      <span className="block max-w-[100px] truncate text-[9px] font-semibold text-torinoko">{node.label}</span>
      <span className="block text-[8px] uppercase tracking-[0.08em]" style={{ color: hex }}>
        {node.kind === "source_error" ? "uncertain" : node.status}
      </span>
      {node.freshness === "stale" || node.freshness === "unknown" ? (
        <span className="block text-[7px] text-sumi-500">{freshnessLabel(node.freshness)}</span>
      ) : null}
      <Handle type="source" position={Position.Bottom} className="!h-1 !w-1 !border-0 !bg-sumi-700" />
    </button>
  );
}

const nodeTypes = { cockpit: CockpitFlowNode };

function layout(graph: CockpitGraph): Node[] {
  // Deterministic layered layout by cluster (spec 15.4: layout must be deterministic).
  const byCluster = new Map<string, CockpitNode[]>();
  for (const node of graph.nodes) {
    const list = byCluster.get(node.cluster) ?? [];
    list.push(node);
    byCluster.set(node.cluster, list);
  }
  const clusters = [
    ...CLUSTER_ORDER.filter((c) => byCluster.has(c)),
    ...[...byCluster.keys()].filter((c) => !CLUSTER_ORDER.includes(c as (typeof CLUSTER_ORDER)[number])),
  ];
  const colGap = 240;
  const rowGap = 96;
  const nodes: Node[] = [];
  clusters.forEach((cluster, col) => {
    const list = byCluster.get(cluster) ?? [];
    list.forEach((node, row) => {
      nodes.push({
        id: node.id,
        type: "cockpit",
        position: { x: col * colGap, y: row * rowGap - (list.length * rowGap) / 2 },
        data: { node },
      });
    });
  });
  return nodes;
}

export function CockpitTopology({
  report,
  selectedId,
  filterText,
  onInspect,
  onSelect,
}: {
  report: OperatorCoherenceReport;
  selectedId: string | null;
  filterText: string;
  onInspect: (item: InspectItem) => void;
  onSelect: (id: string) => void;
}) {
  const graph = useMemo(() => buildTopology(report), [report]);
  const visibleNodeIds = useMemo(() => {
    const matches = graph.nodes.filter((node) => nodeMatchesFilter(node, filterText)).map((node) => node.id);
    return new Set(matches);
  }, [graph.nodes, filterText]);

  const nodes = useMemo<Node[]>(() => {
    return layout(graph).map((rfNode) => {
      const node = (rfNode.data as { node: CockpitNode }).node;
      return {
        ...rfNode,
        data: {
          node,
          selected: node.id === selectedId,
          dimmed: filterText.trim() ? !visibleNodeIds.has(node.id) : false,
          onInspect: (item: InspectItem) => {
            onSelect(node.id);
            onInspect(item);
          },
        },
      };
    });
  }, [graph, selectedId, onInspect, onSelect, filterText, visibleNodeIds]);

  const edges = useMemo<Edge[]>(() => {
    return graph.edges.map((edge) => {
      const hex = TONE_HEX[
        edge.status === "blocked" || edge.status === "danger"
          ? "danger"
          : edge.status === "stale" || edge.status === "needs"
            ? "warn"
            : edge.status === "unknown"
              ? "muted"
              : edge.status === "safe" || edge.status === "live" || edge.status === "done"
                ? "ok"
                : "info"
      ];
      const touchesSelected = edge.source === selectedId || edge.target === selectedId;
      const matchesFilter = !filterText.trim() || visibleNodeIds.has(edge.source) || visibleNodeIds.has(edge.target);
      return {
        id: edge.id,
        source: edge.source,
        target: edge.target,
        animated: edge.status === "live" && !edge.uncertain,
        style: {
          stroke: hex,
          strokeWidth: 0.6 + edge.strength * 2.6,
          strokeDasharray: edge.uncertain ? "4 4" : undefined,
          opacity: !matchesFilter ? 0.12 : touchesSelected ? 1 : edge.freshness === "stale" ? 0.4 : edge.freshness === "unknown" ? 0.3 : 0.6,
        },
      };
    });
  }, [graph.edges, selectedId, filterText, visibleNodeIds]);

  const legend: { label: string; tone: TruthTone }[] = [
    { label: "ok/live", tone: "ok" },
    { label: "needs/stale", tone: "warn" },
    { label: "dirty/blocked", tone: "danger" },
    { label: "system/track", tone: "info" },
    { label: "uncertain", tone: "muted" },
  ];

  return (
    <section className="rounded-md border border-sumi-800/60 bg-sumi-950/45 p-4">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-sumi-600">report-derived nodes + edges</div>
          <h2 className="mt-1 text-base font-semibold text-torinoko">Repo topology</h2>
          {filterText.trim() ? (
            <div className="mt-1 text-[10px] text-kinpaku">
              filter active: {visibleNodeIds.size}/{graph.nodes.length} nodes matching “{filterText}”
            </div>
          ) : null}
        </div>
        <div className="flex flex-wrap items-center gap-2 text-[10px]">
          {legend.map((item) => (
            <span key={item.label} className="inline-flex items-center gap-1 text-sumi-500">
              <span className="h-2 w-2 rounded-full" style={{ background: TONE_HEX[item.tone] }} />
              {item.label}
            </span>
          ))}
          <span className="inline-flex items-center gap-1 text-sumi-500">
            <span className="inline-block h-0 w-4 border-t border-dashed border-sumi-500" /> uncertain edge
          </span>
        </div>
      </div>
      <div className="mb-2 flex flex-wrap gap-2 text-[9px] uppercase tracking-[0.1em] text-sumi-600">
        {CLUSTER_ORDER.map((cluster) => (
          <span key={cluster} className="rounded border border-sumi-800/70 bg-sumi-900/40 px-1.5 py-0.5">
            {CLUSTER_LABEL[cluster] ?? cluster}
          </span>
        ))}
      </div>
      <div className="h-[560px] w-full overflow-hidden rounded-md border border-sumi-800/55 bg-[#0A0E1A]">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          fitView
          minZoom={0.2}
          maxZoom={1.8}
          proOptions={{ hideAttribution: true }}
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable
        >
          <Background variant={BackgroundVariant.Dots} gap={26} size={1} color="#1E2028" />
          <MiniMap
            pannable
            zoomable
            maskColor="rgba(10,14,26,0.7)"
            style={{ backgroundColor: "#0D0E13", border: "1px solid #252730" }}
            nodeColor={(n) => TONE_HEX[((n.data as { node?: CockpitNode })?.node?.tone) ?? "muted"]}
          />
          <Controls showInteractive={false} className="!border-sumi-800 !bg-sumi-900" />
        </ReactFlow>
      </div>
      <div className="mt-2 text-[10px] text-sumi-600">
        {graph.nodes.length} nodes · {graph.edges.length} edges · node size = evidence + risk · opacity = freshness/filter · dashed = uncertain
      </div>
    </section>
  );
}

/* ============================================================
   Recursive mandala — spec 11.7. Same nodes, nested rings.
   ring1 readiness · ring2 tracks · ring3 cards · ring4 evidence/errors
   ============================================================ */

const RING_FOR_CLUSTER: Record<string, number> = {
  system: 0,
  readiness: 1,
  actions: 1,
  tracks: 2,
  live_ops: 3,
  receipts: 4,
  uncertainty: 4,
};

const RING_RADII = [0, 92, 170, 248, 300] as const;

export function RecursiveMandala({
  report,
  selectedId,
  filterText,
  onInspect,
  onSelect,
}: {
  report: OperatorCoherenceReport;
  selectedId: string | null;
  filterText: string;
  onInspect: (item: InspectItem) => void;
  onSelect: (id: string) => void;
}) {
  const graph = useMemo(() => buildTopology(report), [report]);
  const matching = useMemo(() => new Set(graph.nodes.filter((node) => nodeMatchesFilter(node, filterText)).map((node) => node.id)), [graph.nodes, filterText]);
  const size = 640;
  const center = size / 2;


  const placed = useMemo(() => {
    const byRing = new Map<number, CockpitNode[]>();
    for (const node of graph.nodes) {
      const ring = RING_FOR_CLUSTER[node.cluster] ?? 4;
      const list = byRing.get(ring) ?? [];
      list.push(node);
      byRing.set(ring, list);
    }
    const result: { node: CockpitNode; x: number; y: number; r: number }[] = [];
    for (const [ring, list] of byRing.entries()) {
      const radius = RING_RADII[ring] ?? 300;
      list.forEach((node, index) => {
        if (ring === 0) {
          result.push({ node, x: center, y: center, r: 30 });
          return;
        }
        const angle = (index / list.length) * Math.PI * 2 - Math.PI / 2;
        result.push({
          node,
          x: center + radius * Math.cos(angle),
          y: center + radius * Math.sin(angle),
          r: node.risk === "critical" || node.risk === "high" ? 11 : 8,
        });
      });
    }
    return result;
  }, [graph.nodes, center]);

  return (
    <section className="rounded-md border border-sumi-800/60 bg-sumi-950/45 p-4">
      <div className="mb-3">
        <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-sumi-600">same objects · nested rings</div>
        <h2 className="mt-1 text-base font-semibold text-torinoko">Recursive mandala</h2>
        <p className="mt-1 text-xs text-sumi-500">
          ring 1 readiness · ring 2 tracks/organs · ring 3 live surfaces · ring 4 cards/uncertainty. Selection is shared with Linear and Topology.
        </p>
        {filterText.trim() ? (
          <div className="mt-1 text-[10px] text-kinpaku">
            filter active: {matching.size}/{graph.nodes.length} nodes matching “{filterText}”
          </div>
        ) : null}
      </div>
      <div className="flex justify-center overflow-x-auto">
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="max-w-full">
          {RING_RADII.slice(1).map((radius) => (
            <circle key={radius} cx={center} cy={center} r={radius} fill="none" stroke="#1E2028" strokeWidth={1} />
          ))}
          {placed.map(({ node, x, y, r }) => {
            const hex = TONE_HEX[node.tone];
            const isSelected = node.id === selectedId;
            const freshOpacity = node.freshness === "fresh" ? 1 : node.freshness === "aging" ? 0.8 : node.freshness === "stale" ? 0.55 : 0.4;
            const opacity = filterText.trim() && !matching.has(node.id) ? Math.min(0.18, freshOpacity) : freshOpacity;
            const uncertain = node.kind === "source_error" || node.freshness === "unknown";
            return (
              <g
                key={node.id}
                role="button"
                tabIndex={0}
                onClick={() => {
                  onSelect(node.id);
                  onInspect(node.inspect);
                }}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    onSelect(node.id);
                    onInspect(node.inspect);
                  }
                }}
                style={{ cursor: "pointer" }}
              >
                {node.pulse ? (
                  <circle cx={x} cy={y} r={r + 4} fill="none" stroke={hex} strokeWidth={1} className="cockpit-pulse-ring" />
                ) : null}
                <circle
                  cx={x}
                  cy={y}
                  r={r}
                  fill={hex}
                  fillOpacity={opacity * 0.85}
                  stroke={isSelected ? "#D4A855" : hex}
                  strokeWidth={isSelected ? 3 : 1}
                  strokeDasharray={uncertain ? "3 3" : undefined}
                />
                {isSelected || r > 10 ? (
                  <title>{`${node.label} · ${node.status} · ${freshnessLabel(node.freshness)}`}</title>
                ) : (
                  <title>{node.label}</title>
                )}
              </g>
            );
          })}
          <text x={center} y={center + 4} textAnchor="middle" className="fill-torinoko" style={{ fontSize: 11, fontWeight: 600 }}>
            {report.readiness?.score ?? 0}%
          </text>
        </svg>
      </div>
      <div className="mt-2 text-[10px] text-sumi-600">
        {graph.nodes.length} nodes shared with topology · dashed = uncertain · faded = stale
      </div>
    </section>
  );
}
