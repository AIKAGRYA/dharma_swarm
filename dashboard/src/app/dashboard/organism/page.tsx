"use client";

import { useMemo } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { useQuery } from "@tanstack/react-query";
import {
  Background,
  Controls,
  MarkerType,
  Position,
  ReactFlow,
  type Edge,
  type Node,
  type NodeMouseHandler,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import {
  ArrowRight,
  Braces,
  CheckCircle2,
  CircleDashed,
  Network,
  Orbit,
  Route,
  ShieldCheck,
  Workflow,
} from "lucide-react";

import { apiFetch } from "@/lib/api";
import {
  AUTHORITY_STATES,
  authorityPresentation,
  cycleWitnessPresentation,
  humanizeIdentifier,
  orderedPortfolioNodes,
  portfolioNodeHref,
  promotionRuleLines,
  summarizePortfolio,
  type AutocatalyticNode,
  type AutocatalyticPortfolioResponse,
} from "@/lib/autocatalyticPortfolio";
import { accentAt, colors } from "@/lib/theme";
import {
  AuthorityBadge,
  CycleWitnessBadge,
  ErrorSurface,
  LoadingSurface,
  PanelHeading,
  TruthBoundaryNotice,
} from "./_components";

interface PortfolioGraphNodeData extends Record<string, unknown> {
  label: React.ReactNode;
  ordinal: number;
}

function GraphNodeLabel({ node }: { node: AutocatalyticNode }) {
  const authority = authorityPresentation(node.authority);
  return (
    <div
      className="w-[220px] rounded-xl border bg-sumi-850/95 p-3 text-left shadow-xl backdrop-blur-sm"
      style={{
        borderColor: `color-mix(in srgb, ${authority.color} 42%, transparent)`,
        boxShadow: `0 0 22px color-mix(in srgb, ${authority.color} 10%, transparent)`,
      }}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="font-mono text-[9px] uppercase tracking-[0.12em] text-sumi-600">
          Organ {String(node.ordinal).padStart(2, "0")}
        </span>
        <AuthorityBadge authority={node.authority} compact />
      </div>
      <p className="mt-2 truncate font-heading text-sm font-semibold text-torinoko">{node.label}</p>
      <p className="mt-1 line-clamp-2 min-h-8 text-[10px] leading-relaxed text-sumi-600">
        {node.role}
      </p>
      <div className="mt-2 flex items-center gap-1.5 border-t border-sumi-700/30 pt-2">
        <span className="truncate font-mono text-[9px] text-aozora">{node.output_signal}</span>
        <ArrowRight size={10} className="ml-auto shrink-0 text-sumi-600" />
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  detail,
  accent,
}: {
  label: string;
  value: string;
  detail: string;
  accent: string;
}) {
  return (
    <div className="glass-panel-subtle p-4">
      <p className="text-[9px] font-semibold uppercase tracking-[0.14em] text-sumi-600">{label}</p>
      <p className="mt-2 font-heading text-xl font-bold" style={{ color: accent }}>
        {value}
      </p>
      <p className="mt-1 text-[10px] leading-relaxed text-sumi-600">{detail}</p>
    </div>
  );
}

function formatTimestamp(value: string | undefined): string {
  if (!value) return "—";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
}

export default function OrganismPage() {
  const router = useRouter();
  const { data, isLoading, error } = useQuery<AutocatalyticPortfolioResponse>({
    queryKey: ["manifest", "autocatalytic"],
    queryFn: () =>
      apiFetch<AutocatalyticPortfolioResponse>("/api/manifest/autocatalytic"),
    refetchInterval: 30_000,
  });

  const portfolio = data?.portfolio;
  const orderedNodes = useMemo(
    () => (portfolio ? orderedPortfolioNodes(portfolio) : []),
    [portfolio],
  );
  const summary = useMemo(
    () => (portfolio ? summarizePortfolio(portfolio) : null),
    [portfolio],
  );

  const flowNodes = useMemo<Node<PortfolioGraphNodeData>[]>(
    () =>
      orderedNodes.map((node, index) => {
        const topRow = index < 5;
        const column = topRow ? index : 9 - index;
        let sourcePosition = topRow ? Position.Right : Position.Left;
        let targetPosition = topRow ? Position.Left : Position.Right;
        if (index === 4) sourcePosition = Position.Bottom;
        if (index === 5) targetPosition = Position.Top;
        if (index === 9) sourcePosition = Position.Top;
        if (index === 0) targetPosition = Position.Bottom;
        return {
          id: node.id,
          position: { x: column * 260, y: topRow ? 25 : 340 },
          data: { label: <GraphNodeLabel node={node} />, ordinal: node.ordinal },
          sourcePosition,
          targetPosition,
          draggable: false,
          style: { width: 220, border: "none", padding: 0, background: "transparent" },
        };
      }),
    [orderedNodes],
  );

  const flowEdges = useMemo<Edge[]>(() => {
    if (!portfolio) return [];
    const byId = new Map(portfolio.nodes.map((node) => [node.id, node]));
    return portfolio.edges.map((edge, index) => {
      const canonical = byId.get(edge.source)?.next_node === edge.target;
      const accent = canonical ? colors.aozora : colors.fuji;
      return {
        id: `${edge.source}-${edge.target}-${index}`,
        source: edge.source,
        target: edge.target,
        animated: false,
        label: canonical ? undefined : humanizeIdentifier(edge.kind),
        labelStyle: { fill: colors.sumi[600], fontSize: 9 },
        labelBgStyle: { fill: colors.sumi[950], fillOpacity: 0.9 },
        style: {
          stroke: accent,
          strokeWidth: canonical ? 1.8 : 1,
          strokeDasharray: canonical ? undefined : "5 5",
          opacity: canonical ? 0.72 : 0.45,
        },
        markerEnd: { type: MarkerType.ArrowClosed, color: accent, width: 14, height: 14 },
      };
    });
  }, [portfolio]);

  const onNodeClick: NodeMouseHandler = (_event, node) => {
    router.push(portfolioNodeHref(node.id));
  };

  if (isLoading) return <LoadingSurface />;
  if (error || !data || !portfolio || !summary) {
    return (
      <ErrorSurface
        message={
          error instanceof Error
            ? error.message
            : "The canonical autocatalytic manifest did not return a portfolio."
        }
      />
    );
  }
  if (data.topology.contract_valid !== true) {
    return (
      <ErrorSurface
        message={`The backend rejected the portfolio contract: ${
          data.topology.validation_errors.join("; ") || "unspecified validation failure"
        }`}
      />
    );
  }

  const witness = data.latest_cycle;
  const witnessPresentation = cycleWitnessPresentation(witness);
  const ruleLines = promotionRuleLines(portfolio.promotion_rule);

  return (
    <div className="space-y-6">
      <motion.header initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-3">
              <Orbit size={25} className="text-aozora" />
              <h1 className="glow-aozora font-heading text-2xl font-bold tracking-tight text-aozora">
                Autocatalytic Organism
              </h1>
            </div>
            <p className="mt-2 max-w-3xl text-sm leading-relaxed text-sumi-600">
              Ten load-bearing mechanisms expressed as typed signal transformations, each feeding
              the next organ and exposing its own evidence boundary.
            </p>
          </div>
          <div className="flex flex-wrap items-center justify-end gap-2">
            <AuthorityBadge authority={portfolio.claim_ceiling} />
            <CycleWitnessBadge witness={witness} />
          </div>
        </div>
      </motion.header>

      <TruthBoundaryNotice witness={witness} />

      <section className="grid grid-cols-2 gap-3 xl:grid-cols-4">
        <StatCard
          label="Declared organs"
          value={`${summary.nodeCount}/10`}
          detail="Exactly ten is the portfolio contract."
          accent={summary.nodeCount === 10 ? colors.rokusho : colors.bengara}
        />
        <StatCard
          label="Typed feeds"
          value={String(summary.edgeCount)}
          detail="Declared signal edges, including catalytic cross-feeds."
          accent={colors.aozora}
        />
        <StatCard
          label="Topology closure"
          value={summary.closedTenNodeRing ? "CLOSED" : "OPEN"}
          detail="Structural declaration only; this is not runtime proof."
          accent={summary.closedTenNodeRing ? colors.fuji : colors.bengara}
        />
        <StatCard
          label="Runtime witness"
          value={witnessPresentation.state === "receipt_consistent" ? "10 / 10" : "UNPROVEN"}
          detail={witnessPresentation.description}
          accent={witnessPresentation.color}
        />
      </section>

      <section className="glass-panel overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-sumi-700/30 px-5 py-4">
          <PanelHeading icon={Network}>Declared metabolic graph</PanelHeading>
          <div className="flex items-center gap-4 font-mono text-[9px] uppercase tracking-wider text-sumi-600">
            <span className="flex items-center gap-1.5">
              <span className="h-px w-5 bg-aozora" /> canonical feed
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-5 border-t border-dashed border-fuji" /> catalytic cross-feed
            </span>
          </div>
        </div>
        <div className="h-[610px] min-w-0">
          <ReactFlow
            nodes={flowNodes}
            edges={flowEdges}
            onNodeClick={onNodeClick}
            fitView
            fitViewOptions={{ padding: 0.12 }}
            minZoom={0.35}
            maxZoom={1.35}
            nodesConnectable={false}
            nodesDraggable={false}
            elementsSelectable
            proOptions={{ hideAttribution: true }}
            style={{ background: colors.sumi[950] }}
          >
            <Background color={colors.sumi[700]} gap={22} size={1} />
            <Controls
              showInteractive={false}
              style={{
                background: colors.sumi[850],
                borderColor: colors.sumi[700],
                borderRadius: 8,
              }}
            />
          </ReactFlow>
        </div>
        <div className="border-t border-sumi-700/30 px-5 py-3 text-[10px] text-sumi-600">
          Select any organ to inspect its typed contract, proof obligations, evidence references,
          predecessor, and consumer.
        </div>
      </section>

      <section className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1.35fr)_minmax(340px,0.65fr)]">
        <div className="glass-panel p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <PanelHeading icon={ShieldCheck}>Latest local consistency witness</PanelHeading>
              <p className="mt-2 text-xs leading-relaxed text-sumi-600">
                {witnessPresentation.description}
              </p>
            </div>
            <CycleWitnessBadge witness={witness} />
          </div>

          {witness ? (
            <div className="mt-5 space-y-4">
              <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                <WitnessDatum label="Mode" value={humanizeIdentifier(witness.mode)} />
                <WitnessDatum
                  label="Semantic hops"
                  value={`${witness.completed_hops}/${witness.required_hops}`}
                />
                <WitnessDatum label="Turns proven" value={String(witness.turns_proven)} />
                <WitnessDatum
                  label="External effects"
                  value={witness.external_effects_proven ? "Proven" : "Not proven"}
                  warning={!witness.external_effects_proven}
                />
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                <WitnessDatum label="Transport evidence" value={witness.transport_evidence} mono />
                <WitnessDatum
                  label="Execution evidence scope"
                  value={witness.execution_evidence_scope ?? "untrusted_or_stale"}
                  mono
                />
                <WitnessDatum label="Claim ceiling" value={witness.claim_ceiling} mono />
                <WitnessDatum label="Cycle ID" value={witness.cycle_id} mono />
                <WitnessDatum label="Trace ID" value={witness.trace_id} mono />
                <WitnessDatum label="Generated" value={formatTimestamp(witness.generated_at)} />
                <WitnessDatum label="Witness path" value={witness.witness_path} mono />
              </div>
              {!witness.external_effects_proven && (
                <div className="rounded-lg border border-kinpaku/25 bg-kinpaku/5 px-3 py-2 text-[10px] leading-relaxed text-kinpaku">
                  Local receipt consistency is mutable-store evidence, not authenticated execution
                  provenance; it also does not prove production peers, model-backed semantics, or
                  external-world effects.
                </div>
              )}
            </div>
          ) : (
            <div className="mt-5 rounded-lg border border-sumi-700/35 bg-sumi-850/40 px-4 py-7 text-center">
              <CircleDashed size={20} className="mx-auto text-sumi-600" />
              <p className="mt-2 text-xs text-sumi-600">
                No witness returned. The dashboard makes no runtime-liveness inference.
              </p>
            </div>
          )}
        </div>

        <div className="glass-panel p-5">
          <PanelHeading icon={Braces}>Promotion rule</PanelHeading>
          <p className="mt-2 text-xs leading-relaxed text-sumi-600">
            These are evaluator semantics, not decorative receipt labels.
          </p>
          <div className="mt-4 space-y-2">
            {ruleLines.length > 0 ? (
              ruleLines.map((line, index) => (
                <div
                  key={`${line}-${index}`}
                  className="flex items-start gap-2.5 rounded-lg border border-sumi-700/30 bg-sumi-850/45 px-3 py-2.5"
                >
                  <CheckCircle2 size={13} className="mt-0.5 shrink-0 text-rokusho" />
                  <p className="text-[10px] leading-relaxed text-kitsurubami">{line}</p>
                </div>
              ))
            ) : (
              <p className="text-xs text-sumi-600">No promotion rule declared.</p>
            )}
          </div>
        </div>
      </section>

      <section>
        <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
          <div>
            <PanelHeading icon={Workflow}>Ten dedicated organ records</PanelHeading>
            <p className="mt-1 text-xs text-sumi-600">
              Read-only project bindings, transformations, authority ceilings, and proof obligations.
            </p>
          </div>
          <span className="font-mono text-[9px] uppercase tracking-wider text-sumi-600">
            Schema {data.schema_version}
          </span>
        </div>
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-2 2xl:grid-cols-3">
          {orderedNodes.map((node, index) => {
            const accent = accentAt(index);
            return (
              <Link
                key={node.id}
                href={portfolioNodeHref(node.id)}
                className="group glass-panel-subtle relative overflow-hidden p-4 transition-all hover:-translate-y-0.5 hover:border-aozora/35"
              >
                <div
                  className="absolute inset-y-0 left-0 w-0.5"
                  style={{ backgroundColor: accent }}
                />
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="font-mono text-[9px] uppercase tracking-[0.14em] text-sumi-600">
                      Organ {String(node.ordinal).padStart(2, "0")}
                    </p>
                    <h3 className="mt-1 truncate font-heading text-sm font-semibold text-torinoko group-hover:text-aozora">
                      {node.label}
                    </h3>
                  </div>
                  <AuthorityBadge authority={node.authority} compact />
                </div>
                <p className="mt-2 line-clamp-2 min-h-9 text-[11px] leading-relaxed text-sumi-600">
                  {node.role}
                </p>
                <div className="mt-3 flex items-center gap-2 rounded-lg bg-sumi-850/55 px-2.5 py-2">
                  <span className="truncate font-mono text-[9px] text-kitsurubami">
                    {node.input_signal}
                  </span>
                  <ArrowRight size={11} className="shrink-0 text-aozora" />
                  <span className="truncate font-mono text-[9px] text-aozora">
                    {node.output_signal}
                  </span>
                </div>
                <div className="mt-3 flex items-center justify-between gap-3 text-[9px] text-sumi-600">
                  <span>{node.project_bindings.length} project binding(s)</span>
                  <span className="flex items-center gap-1 text-aozora">
                    Open record <ArrowRight size={10} />
                  </span>
                </div>
              </Link>
            );
          })}
        </div>
      </section>

      <section className="glass-panel-subtle p-4">
        <div className="flex flex-wrap items-center gap-x-5 gap-y-3">
          <div className="flex items-center gap-2">
            <Route size={13} className="text-sumi-600" />
            <span className="text-[9px] font-semibold uppercase tracking-[0.13em] text-sumi-600">
              Authority legend
            </span>
          </div>
          {AUTHORITY_STATES.map((state) => {
            const presentation = authorityPresentation(state);
            return (
              <div key={state} className="flex items-center gap-2" title={presentation.description}>
                <AuthorityBadge authority={state} compact />
                <span className="hidden text-[9px] text-sumi-600 2xl:inline">
                  {presentation.description}
                </span>
              </div>
            );
          })}
        </div>
      </section>
    </div>
  );
}

function WitnessDatum({
  label,
  value,
  mono = false,
  warning = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
  warning?: boolean;
}) {
  return (
    <div className="min-w-0 rounded-lg border border-sumi-700/30 bg-sumi-850/45 p-3">
      <p className="text-[9px] font-semibold uppercase tracking-[0.12em] text-sumi-600">{label}</p>
      <p
        className={`mt-1 truncate text-[11px] ${mono ? "font-mono" : "font-medium"} ${
          warning ? "text-kinpaku" : "text-torinoko"
        }`}
        title={value}
      >
        {value}
      </p>
    </div>
  );
}
