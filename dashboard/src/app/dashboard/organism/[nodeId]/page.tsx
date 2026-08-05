"use client";

import { use, useMemo } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowLeft,
  ArrowRight,
  BookOpen,
  Braces,
  CheckCircle2,
  FileCheck2,
  GitMerge,
  Link2,
  Network,
  Orbit,
  Route,
  ShieldCheck,
  Workflow,
} from "lucide-react";

import { apiFetch } from "@/lib/api";
import {
  authorityPresentation,
  canonicalConsumer,
  canonicalPredecessor,
  cycleWitnessPresentation,
  findPortfolioNode,
  humanizeIdentifier,
  incomingPortfolioEdges,
  outgoingPortfolioEdges,
  portfolioNodeHref,
  promotionRuleLines,
  type AutocatalyticEdge,
  type AutocatalyticNode,
  type AutocatalyticPortfolio,
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
} from "../_components";

function connectionNode(
  portfolio: AutocatalyticPortfolio,
  edge: AutocatalyticEdge,
  direction: "incoming" | "outgoing",
): AutocatalyticNode | undefined {
  return findPortfolioNode(portfolio, direction === "incoming" ? edge.source : edge.target);
}

function SignalStage({
  eyebrow,
  value,
  detail,
  accent,
}: {
  eyebrow: string;
  value: string;
  detail: string;
  accent: string;
}) {
  return (
    <div
      className="min-w-0 flex-1 rounded-xl border bg-sumi-850/55 p-4"
      style={{ borderColor: `color-mix(in srgb, ${accent} 28%, transparent)` }}
    >
      <p className="text-[9px] font-semibold uppercase tracking-[0.14em] text-sumi-600">{eyebrow}</p>
      <p className="mt-2 break-words font-mono text-xs font-semibold" style={{ color: accent }}>
        {value}
      </p>
      <p className="mt-2 text-[10px] leading-relaxed text-sumi-600">{detail}</p>
    </div>
  );
}

function ConnectionCard({
  label,
  node,
  signal,
  direction,
}: {
  label: string;
  node: AutocatalyticNode | undefined;
  signal: string;
  direction: "incoming" | "outgoing";
}) {
  if (!node) {
    return (
      <div className="rounded-xl border border-bengara/25 bg-bengara/5 p-4">
        <p className="text-[9px] font-semibold uppercase tracking-[0.14em] text-bengara">{label}</p>
        <p className="mt-2 text-xs text-sumi-600">Unresolved manifest reference</p>
      </div>
    );
  }
  return (
    <Link
      href={portfolioNodeHref(node.id)}
      className="group rounded-xl border border-sumi-700/35 bg-sumi-850/45 p-4 transition-colors hover:border-aozora/35 hover:bg-sumi-850/70"
    >
      <p className="text-[9px] font-semibold uppercase tracking-[0.14em] text-sumi-600">{label}</p>
      <div className="mt-2 flex items-center gap-2">
        {direction === "outgoing" ? null : <ArrowRight size={13} className="shrink-0 text-aozora" />}
        <div className="min-w-0 flex-1">
          <p className="truncate text-xs font-semibold text-torinoko group-hover:text-aozora">
            {String(node.ordinal).padStart(2, "0")} · {node.label}
          </p>
          <p className="mt-1 truncate font-mono text-[9px] text-sumi-600" title={signal}>
            {signal}
          </p>
        </div>
        {direction === "outgoing" ? <ArrowRight size={13} className="shrink-0 text-aozora" /> : null}
      </div>
    </Link>
  );
}

export default function OrganismNodePage({
  params,
}: {
  params: Promise<{ nodeId: string }>;
}) {
  const { nodeId } = use(params);
  const { data, isLoading, error } = useQuery<AutocatalyticPortfolioResponse>({
    queryKey: ["manifest", "autocatalytic"],
    queryFn: () =>
      apiFetch<AutocatalyticPortfolioResponse>("/api/manifest/autocatalytic"),
    refetchInterval: 30_000,
  });

  const portfolio = data?.portfolio;
  const node = portfolio ? findPortfolioNode(portfolio, nodeId) : undefined;
  const incoming = useMemo(
    () => (portfolio ? incomingPortfolioEdges(portfolio, nodeId) : []),
    [portfolio, nodeId],
  );
  const outgoing = useMemo(
    () => (portfolio ? outgoingPortfolioEdges(portfolio, nodeId) : []),
    [portfolio, nodeId],
  );

  if (isLoading) return <LoadingSurface label="Loading organ record…" />;
  if (error || !portfolio) {
    return (
      <ErrorSurface
        message={error instanceof Error ? error.message : "The portfolio contract is unavailable."}
      />
    );
  }
  if (data?.topology.contract_valid !== true) {
    return (
      <ErrorSurface
        message={`The backend rejected the portfolio contract: ${
          data?.topology.validation_errors.join("; ") || "unspecified validation failure"
        }`}
      />
    );
  }
  if (!node) {
    return (
      <div className="space-y-4">
        <ErrorSurface message={`No declared organ has id “${nodeId}”.`} />
        <Link
          href="/dashboard/organism"
          className="inline-flex items-center gap-2 text-xs text-aozora hover:text-torinoko"
        >
          <ArrowLeft size={13} /> Return to organism
        </Link>
      </div>
    );
  }

  const predecessor = canonicalPredecessor(portfolio, node.id);
  const consumer = canonicalConsumer(portfolio, node);
  const authority = authorityPresentation(node.authority);
  const accent = accentAt(Math.max(0, node.ordinal - 1));
  const promotionLines = promotionRuleLines(portfolio.promotion_rule);
  const witnessPresentation = cycleWitnessPresentation(data?.latest_cycle);
  const latestProof =
    witnessPresentation.state === "receipt_consistent"
      ? data?.latest_cycle?.proofs[data.latest_cycle.proofs.length - 1]
      : undefined;
  const latestHop = latestProof?.hops?.find((hop) => hop.node_id === node.id);
  const projectEvidence = latestHop?.artifact.project_evidence;
  const promotionGate = projectEvidence?.promotion_gate;
  const extraIncoming = incoming.filter((edge) => edge.source !== predecessor?.id);
  const extraOutgoing = outgoing.filter((edge) => edge.target !== consumer?.id);

  return (
    <div className="space-y-6">
      <motion.header initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
        <Link
          href="/dashboard/organism"
          className="mb-4 inline-flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-sumi-600 transition-colors hover:text-aozora"
        >
          <ArrowLeft size={12} /> Autocatalytic organism
        </Link>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex min-w-0 items-start gap-4">
            <div
              className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl border font-mono text-sm font-bold"
              style={{
                color: accent,
                borderColor: `color-mix(in srgb, ${accent} 35%, transparent)`,
                backgroundColor: `color-mix(in srgb, ${accent} 10%, transparent)`,
              }}
            >
              {String(node.ordinal).padStart(2, "0")}
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <Orbit size={18} className="shrink-0 text-aozora" />
                <p className="font-mono text-[9px] uppercase tracking-[0.14em] text-sumi-600">
                  {node.id}
                </p>
              </div>
              <h1 className="mt-1 font-heading text-2xl font-bold tracking-tight text-torinoko">
                {node.label}
              </h1>
              <p className="mt-2 max-w-3xl text-sm leading-relaxed text-sumi-600">{node.role}</p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <AuthorityBadge authority={node.authority} />
            <CycleWitnessBadge witness={data?.latest_cycle} />
          </div>
        </div>
      </motion.header>

      <TruthBoundaryNotice witness={data?.latest_cycle} />

      <section className="glass-panel p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <PanelHeading icon={FileCheck2}>Latest project adapter projection</PanelHeading>
            <p className="mt-2 text-xs leading-relaxed text-sumi-600">
              The verifier recomputes this read-only project evidence; a hop-authored hash cannot
              promote its own authority.
            </p>
          </div>
          {projectEvidence ? (
            <span className="rounded-full border border-fuji/25 bg-fuji/5 px-2.5 py-1 font-mono text-[9px] uppercase tracking-wider text-fuji">
              {humanizeIdentifier(projectEvidence.signal.state)}
            </span>
          ) : (
            <span className="rounded-full border border-sumi-700/35 px-2.5 py-1 font-mono text-[9px] uppercase tracking-wider text-sumi-600">
              No adapter witness
            </span>
          )}
        </div>
        {projectEvidence ? (
          <div className="mt-4 space-y-4">
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              <EvidenceDatum label="Adapter" value={projectEvidence.adapter_id} mono />
              <EvidenceDatum label="Modality" value={projectEvidence.signal.modality} mono />
              <EvidenceDatum
                label="Input state"
                value={projectEvidence.input_ref.signal_state}
                mono
              />
              <EvidenceDatum
                label="Side effects"
                value={projectEvidence.side_effects_performed ? "performed" : "none"}
                warning={projectEvidence.side_effects_performed}
              />
            </div>
            <div className="grid gap-3 xl:grid-cols-2">
              <div className="rounded-xl border border-sumi-700/30 bg-sumi-850/45 p-4">
                <p className="text-[9px] font-semibold uppercase tracking-[0.14em] text-sumi-600">
                  Content-addressed sources
                </p>
                <div className="mt-3 space-y-2">
                  {projectEvidence.sources.map((source) => (
                    <div key={source.path} className="rounded-lg bg-sumi-900/55 px-3 py-2">
                      <p className="break-all font-mono text-[9px] text-kitsurubami">
                        {source.path}
                      </p>
                      <p className="mt-1 font-mono text-[8px] text-sumi-600">
                        {source.present ? source.sha256?.slice(0, 16) : "MISSING"}
                        {source.declared_digest_valid === false ? " · INVALID DIGEST" : ""}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
              <div className="rounded-xl border border-kinpaku/20 bg-kinpaku/5 p-4">
                <p className="text-[9px] font-semibold uppercase tracking-[0.14em] text-kinpaku">
                  Promotion blockers
                </p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {projectEvidence.signal.blockers.map((blocker) => (
                    <span
                      key={blocker}
                      className="rounded-md border border-kinpaku/20 px-2 py-1 font-mono text-[9px] text-kinpaku"
                    >
                      {humanizeIdentifier(blocker)}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </div>
        ) : (
          <p className="mt-4 rounded-lg border border-sumi-700/30 bg-sumi-850/40 px-4 py-5 text-center text-xs text-sumi-600">
            No locally receipt-consistent adapter projection is available for this organ yet.
          </p>
        )}
      </section>

      <section className="glass-panel p-5">
        <PanelHeading icon={Workflow}>Typed metabolic contract</PanelHeading>
        <div className="mt-4 flex flex-col items-stretch gap-3 lg:flex-row lg:items-center">
          <SignalStage
            eyebrow="Consumes"
            value={node.input_signal}
            detail="The predecessor must supply this typed signal before the transform can run."
            accent={colors.kinpaku}
          />
          <ArrowRight size={20} className="mx-auto shrink-0 rotate-90 text-sumi-600 lg:rotate-0" />
          <SignalStage
            eyebrow="Transforms"
            value={node.transform}
            detail="Declared semantic work; a stronger execution claim requires independent provenance."
            accent={accent}
          />
          <ArrowRight size={20} className="mx-auto shrink-0 rotate-90 text-sumi-600 lg:rotate-0" />
          <SignalStage
            eyebrow="Emits"
            value={node.output_signal}
            detail="This typed result becomes the canonical consumer’s input."
            accent={colors.aozora}
          />
        </div>
      </section>

      <section className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <div className="glass-panel p-5">
          <PanelHeading icon={Route}>Canonical ring position</PanelHeading>
          <p className="mt-2 text-xs leading-relaxed text-sumi-600">
            These two links define this organ’s load-bearing place in the closed declaration.
          </p>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            <ConnectionCard
              label="Predecessor"
              node={predecessor}
              signal={node.input_signal}
              direction="incoming"
            />
            <ConnectionCard
              label="Consumer"
              node={consumer}
              signal={node.output_signal}
              direction="outgoing"
            />
          </div>
        </div>

        <div className="glass-panel p-5">
          <PanelHeading icon={GitMerge}>Catalytic cross-feeds</PanelHeading>
          <p className="mt-2 text-xs leading-relaxed text-sumi-600">
            Additional declared dependencies. They are not evidence of observed message traffic.
          </p>
          <div className="mt-4 space-y-2">
            {extraIncoming.map((edge) => {
              const source = connectionNode(portfolio, edge, "incoming");
              return (
                <ConnectionLine
                  key={`in-${edge.source}-${edge.target}-${edge.signal}`}
                  node={source}
                  signal={edge.signal}
                  kind={`incoming · ${edge.kind}`}
                />
              );
            })}
            {extraOutgoing.map((edge) => {
              const target = connectionNode(portfolio, edge, "outgoing");
              return (
                <ConnectionLine
                  key={`out-${edge.source}-${edge.target}-${edge.signal}`}
                  node={target}
                  signal={edge.signal}
                  kind={`outgoing · ${edge.kind}`}
                />
              );
            })}
            {extraIncoming.length === 0 && extraOutgoing.length === 0 && (
              <p className="rounded-lg border border-sumi-700/30 bg-sumi-850/40 px-3 py-4 text-center text-xs text-sumi-600">
                No additional cross-feed edges declared.
              </p>
            )}
          </div>
        </div>
      </section>

      <section className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(300px,0.7fr)_minmax(0,1.3fr)]">
        <div className="glass-panel p-5">
          <PanelHeading icon={Network}>Project bindings</PanelHeading>
          <p className="mt-2 text-xs leading-relaxed text-sumi-600">
            Existing projects this organ connects; no parallel substrate is implied.
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            {node.project_bindings.length > 0 ? (
              node.project_bindings.map((binding) => (
                <span
                  key={binding}
                  className="rounded-lg border border-aozora/20 bg-aozora/5 px-2.5 py-1.5 font-mono text-[10px] text-aozora"
                >
                  {binding}
                </span>
              ))
            ) : (
              <p className="text-xs text-sumi-600">No project bindings declared.</p>
            )}
          </div>
        </div>

        <div className="glass-panel p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <PanelHeading icon={ShieldCheck}>Authority ceiling</PanelHeading>
              <p className="mt-2 text-xs leading-relaxed text-sumi-600">
                Authority is an evaluator ceiling, not a health score or confidence decoration.
              </p>
            </div>
            <AuthorityBadge authority={node.authority} />
          </div>
          <div
            className="mt-4 rounded-xl border p-4"
            style={{
              borderColor: `color-mix(in srgb, ${authority.color} 30%, transparent)`,
              backgroundColor: `color-mix(in srgb, ${authority.color} 7%, transparent)`,
            }}
          >
            <p className="text-xs font-semibold" style={{ color: authority.color }}>
              {authority.label}
            </p>
            <p className="mt-1 text-[11px] leading-relaxed text-sumi-600">
              {authority.description}
            </p>
          </div>
        </div>
      </section>

      <section className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <div className="glass-panel p-5">
          <PanelHeading icon={CheckCircle2}>Proof obligations</PanelHeading>
          <div className="mt-4 space-y-2">
            {node.proof_obligations.length > 0 ? (
              node.proof_obligations.map((obligation, index) => (
                <div
                  key={`${obligation}-${index}`}
                  className="flex items-start gap-2.5 rounded-lg border border-sumi-700/30 bg-sumi-850/45 px-3 py-2.5"
                >
                  <span className="mt-0.5 font-mono text-[9px] text-rokusho">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  <p className="text-[11px] leading-relaxed text-kitsurubami">{obligation}</p>
                </div>
              ))
            ) : (
              <p className="text-xs text-sumi-600">No proof obligations declared.</p>
            )}
          </div>
        </div>

        <div className="glass-panel p-5">
          <PanelHeading icon={FileCheck2}>Evidence references</PanelHeading>
          <p className="mt-2 text-xs leading-relaxed text-sumi-600">
            Repository references are displayed as evidence pointers, not as proof that they passed.
          </p>
          <div className="mt-4 space-y-2">
            {node.proof_refs.map((reference) => (
              <div
                key={reference}
                className="flex min-w-0 items-start gap-2 rounded-lg border border-sumi-700/30 bg-sumi-850/45 px-3 py-2.5"
              >
                <Link2 size={12} className="mt-0.5 shrink-0 text-fuji" />
                <code className="break-all text-[10px] leading-relaxed text-kitsurubami">
                  {reference}
                </code>
              </div>
            ))}
            {node.proof_refs.length === 0 && (
              <p className="text-xs text-sumi-600">No evidence references declared.</p>
            )}
          </div>
          <div className="mt-3 rounded-lg border border-sumi-700/30 bg-sumi-850/45 px-3 py-2.5">
            <div className="flex items-start gap-2">
              <BookOpen size={12} className="mt-0.5 shrink-0 text-aozora" />
              <div className="min-w-0">
                <p className="text-[9px] uppercase tracking-[0.12em] text-sumi-600">
                  Canonical page
                </p>
                <code className="mt-1 block break-all text-[10px] text-aozora">{node.page}</code>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <div className="glass-panel p-5">
          <PanelHeading icon={Braces}>Portfolio promotion semantics</PanelHeading>
          <p className="mt-2 text-xs leading-relaxed text-sumi-600">
            Machine-evaluated future evidence requirements are displayed below. They are not
            current proof and cannot upgrade this node&apos;s authority.
          </p>
          <div className="mt-4 space-y-2">
            {(node.promotion_checks ?? []).map((predicate) => {
              const evaluation = promotionGate?.checks.find(
                (check) => check.predicate === predicate,
              );
              return (
                <div
                  key={predicate}
                  className="flex items-center justify-between gap-3 rounded-lg border border-sumi-700/30 bg-sumi-850/45 px-3 py-2.5"
                >
                  <code className="break-all text-[10px] text-kitsurubami">{predicate}</code>
                  <span
                    className={`shrink-0 font-mono text-[9px] uppercase tracking-wider ${
                      evaluation?.passed ? "text-rokusho" : "text-kinpaku"
                    }`}
                  >
                    {evaluation ? (evaluation.passed ? "satisfied" : "required") : "not evaluated"}
                  </span>
                </div>
              );
            })}
          </div>
          <p className="mt-3 text-[10px] leading-relaxed text-sumi-600">
            Authority upgrade authorized: {promotionGate?.authority_upgrade_authorized ? "yes" : "no"}.
            A new authority-bearing evaluator and work packet are required.
          </p>
          <div className="mt-4 space-y-2">
            {promotionLines.map((line, index) => (
              <div key={`${line}-${index}`} className="flex items-start gap-2.5">
                <CheckCircle2 size={13} className="mt-0.5 shrink-0 text-rokusho" />
                <p className="text-[11px] leading-relaxed text-kitsurubami">{line}</p>
              </div>
            ))}
            {promotionLines.length === 0 && (
              <p className="text-xs text-sumi-600">No promotion rule declared.</p>
            )}
          </div>
        </div>

        <div className="glass-panel p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <PanelHeading icon={FileCheck2}>Portfolio-level witness</PanelHeading>
            <CycleWitnessBadge witness={data?.latest_cycle} />
          </div>
          <p className="mt-3 text-xs leading-relaxed text-sumi-600">
            {witnessPresentation.description} This is a portfolio-level statement; this page does
            not derive an independent per-organ health claim from it.
          </p>
          {data?.latest_cycle && (
            <div className="mt-4 grid grid-cols-2 gap-3">
              <Datum label="Cycle" value={data.latest_cycle.cycle_id} />
              <Datum
                label="Semantic hops"
                value={`${data.latest_cycle.completed_hops}/${data.latest_cycle.required_hops}`}
              />
              <Datum label="Mode" value={humanizeIdentifier(data.latest_cycle.mode)} />
              <Datum
                label="External effects"
                value={data.latest_cycle.external_effects_proven ? "Proven" : "Not proven"}
              />
            </div>
          )}
        </div>
      </section>

      <div className="glass-panel-subtle flex flex-wrap items-center justify-between gap-3 px-4 py-3 text-[9px] text-sumi-600">
        <span>
          <span className="uppercase tracking-wider">Portfolio</span>{" "}
          <span className="font-mono text-kitsurubami">{portfolio.id}</span>
        </span>
        <span>
          <span className="uppercase tracking-wider">Next node</span>{" "}
          <span className="font-mono text-kitsurubami">{node.next_node}</span>
        </span>
        <span>
          <span className="uppercase tracking-wider">Schema</span>{" "}
          <span className="font-mono text-kitsurubami">{data?.schema_version}</span>
        </span>
      </div>
    </div>
  );
}

function ConnectionLine({
  node,
  signal,
  kind,
}: {
  node: AutocatalyticNode | undefined;
  signal: string;
  kind: string;
}) {
  if (!node) return null;
  return (
    <Link
      href={portfolioNodeHref(node.id)}
      className="group flex min-w-0 items-center gap-3 rounded-lg border border-sumi-700/30 bg-sumi-850/45 px-3 py-2.5 transition-colors hover:border-fuji/30"
    >
      <Network size={12} className="shrink-0 text-fuji" />
      <div className="min-w-0 flex-1">
        <p className="truncate text-[10px] font-medium text-torinoko group-hover:text-fuji">
          {node.label}
        </p>
        <p className="mt-0.5 truncate font-mono text-[9px] text-sumi-600" title={signal}>
          {signal}
        </p>
      </div>
      <span className="shrink-0 font-mono text-[8px] uppercase tracking-wider text-sumi-600">
        {kind}
      </span>
    </Link>
  );
}

function Datum({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 rounded-lg border border-sumi-700/30 bg-sumi-850/45 p-3">
      <p className="text-[9px] uppercase tracking-[0.12em] text-sumi-600">{label}</p>
      <p className="mt-1 truncate font-mono text-[10px] text-kitsurubami" title={value}>
        {value}
      </p>
    </div>
  );
}

function EvidenceDatum({
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
    <div
      className={`min-w-0 rounded-lg border p-3 ${
        warning
          ? "border-kinpaku/30 bg-kinpaku/5"
          : "border-sumi-700/30 bg-sumi-850/45"
      }`}
    >
      <p className="text-[9px] uppercase tracking-[0.12em] text-sumi-600">{label}</p>
      <p
        className={`mt-1 truncate text-[10px] ${
          warning ? "text-kinpaku" : "text-kitsurubami"
        } ${mono ? "font-mono" : ""}`}
        title={value}
      >
        {value}
      </p>
    </div>
  );
}
