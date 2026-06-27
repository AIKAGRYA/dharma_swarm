"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import type { ReactNode } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Clipboard,
  Download,
  ExternalLink,
  FileJson,
  Fingerprint,
  Globe2,
  KeyRound,
  Network,
  RadioTower,
  ShieldCheck,
} from "lucide-react";
import {
  agentCardBlocked,
  agentCardHandoffReady,
  agentCardLabel,
  countAgentCardFindings,
} from "@/lib/agentCards";
import { fetchAgentCardExportText } from "@/lib/api";
import { colors } from "@/lib/theme";
import type { AgentCardExportFormat, AgentCardOut } from "@/lib/types";

interface AgentCardDetailPanelProps {
  agent: AgentCardOut | null;
}

type CopyState = "idle" | "copied" | "downloaded" | "failed";

const EXPORT_EXTENSIONS: Record<AgentCardExportFormat, string> = {
  "public-json": "public.json",
  "extended-json": "extended.json",
  "operator-json": "operator.json",
  markdown: "md",
  jcard: "jcard.json",
  vcard: "vcf",
};

const EXPORT_MEDIA_TYPES: Record<AgentCardExportFormat, string> = {
  "public-json": "application/json",
  "extended-json": "application/json",
  "operator-json": "application/json",
  markdown: "text/markdown",
  jcard: "application/jcard+json",
  vcard: "text/vcard",
};

function compactValue(value: unknown): string {
  if (value == null || value === "") return "-";
  if (Array.isArray(value)) return value.join(", ") || "-";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function objectEntries(record: Record<string, unknown>): [string, unknown][] {
  return Object.entries(record).filter(([, value]) => {
    if (Array.isArray(value)) return value.length > 0;
    if (value && typeof value === "object") return Object.keys(value).length > 0;
    return value !== "" && value != null;
  });
}

function sourceEntries(agent: AgentCardOut): [string, string[]][] {
  return Object.entries(agent.sources).filter(([, paths]) => paths.length > 0);
}

export function AgentCardDetailPanel({ agent }: AgentCardDetailPanelProps) {
  const [copyState, setCopyState] = useState<CopyState>("idle");

  const handoffSubjects = useMemo(
    () => agent?.handoff.suggested_subjects ?? [],
    [agent],
  );

  async function copyText(value: string) {
    try {
      await navigator.clipboard.writeText(value);
      setCopyState("copied");
      window.setTimeout(() => setCopyState("idle"), 1500);
    } catch {
      setCopyState("failed");
      window.setTimeout(() => setCopyState("idle"), 1500);
    }
  }

  async function copyExport(format: AgentCardExportFormat) {
    if (!agent) return;
    try {
      const value = await fetchAgentCardExportText(agent.agent_uid, format);
      await copyText(value);
    } catch {
      setCopyState("failed");
      window.setTimeout(() => setCopyState("idle"), 1500);
    }
  }

  async function downloadExport(format: AgentCardExportFormat) {
    if (!agent) return;
    try {
      const value = await fetchAgentCardExportText(agent.agent_uid, format);
      const blob = new Blob([value], { type: EXPORT_MEDIA_TYPES[format] });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${agent.agent_uid}.${EXPORT_EXTENSIONS[format]}`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      setCopyState("downloaded");
      window.setTimeout(() => setCopyState("idle"), 1500);
    } catch {
      setCopyState("failed");
      window.setTimeout(() => setCopyState("idle"), 1500);
    }
  }

  if (!agent) {
    return (
      <aside className="min-h-[520px] rounded-lg border border-sumi-700/40 bg-sumi-950/60 p-5">
        <div className="font-heading text-sm font-semibold text-sumi-400">
          No Agent Card selected
        </div>
      </aside>
    );
  }

  const errors = countAgentCardFindings(agent, "error");
  const warnings = countAgentCardFindings(agent, "warning");
  const handoffReady = agentCardHandoffReady(agent);
  const blocked = agentCardBlocked(agent);

  return (
    <aside className="min-h-[720px] rounded-lg border border-sumi-700/40 bg-sumi-950/70">
      <div className="border-b border-sumi-800/80 p-5">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <Fingerprint size={17} className="text-aozora" />
              <h2 className="truncate font-heading text-lg font-semibold text-torinoko">
                {agentCardLabel(agent)}
              </h2>
            </div>
            <div className="mt-1 font-mono text-[11px] text-sumi-500">
              {agent.agent_uid}
            </div>
          </div>
          <Link
            href={`/dashboard/agents/${encodeURIComponent(agent.agent_uid)}`}
            className="inline-flex shrink-0 items-center gap-1.5 rounded-md border border-sumi-700/60 px-2.5 py-1.5 text-[11px] text-sumi-300 transition-colors hover:border-aozora/60 hover:text-aozora"
          >
            <ExternalLink size={12} />
            agent
          </Link>
        </div>

        <div className="mt-4 grid grid-cols-3 gap-2 text-center font-mono text-[10px]">
          <StatusPill
            label={agent.trust_grade}
            value="trust"
            color={blocked ? colors.bengara : colors.rokusho}
          />
          <StatusPill
            label={handoffReady ? "ready" : "partial"}
            value="handoff"
            color={handoffReady ? colors.rokusho : colors.kinpaku}
          />
          <StatusPill
            label={`${errors}/${warnings}`}
            value="err/warn"
            color={errors > 0 ? colors.bengara : warnings > 0 ? colors.kinpaku : colors.rokusho}
          />
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => copyText(JSON.stringify(agent, null, 2))}
            className="inline-flex items-center gap-1.5 rounded-md border border-sumi-700/60 px-2.5 py-1.5 text-[11px] text-sumi-300 transition-colors hover:border-aozora/60 hover:text-aozora"
          >
            <Clipboard size={12} />
            JSON
          </button>
          <button
            type="button"
            onClick={() => copyText(handoffSubjects.join("\n"))}
            disabled={handoffSubjects.length === 0}
            className="inline-flex items-center gap-1.5 rounded-md border border-sumi-700/60 px-2.5 py-1.5 text-[11px] text-sumi-300 transition-colors hover:border-aozora/60 hover:text-aozora disabled:opacity-40"
          >
            <RadioTower size={12} />
            subjects
          </button>
          <button
            type="button"
            onClick={() => copyExport("markdown")}
            className="inline-flex items-center gap-1.5 rounded-md border border-sumi-700/60 px-2.5 py-1.5 text-[11px] text-sumi-300 transition-colors hover:border-aozora/60 hover:text-aozora"
          >
            <Clipboard size={12} />
            MD
          </button>
          <button
            type="button"
            onClick={() => copyExport("vcard")}
            className="inline-flex items-center gap-1.5 rounded-md border border-sumi-700/60 px-2.5 py-1.5 text-[11px] text-sumi-300 transition-colors hover:border-aozora/60 hover:text-aozora"
          >
            <Clipboard size={12} />
            vCard
          </button>
          <button
            type="button"
            onClick={() => copyExport("jcard")}
            className="inline-flex items-center gap-1.5 rounded-md border border-sumi-700/60 px-2.5 py-1.5 text-[11px] text-sumi-300 transition-colors hover:border-aozora/60 hover:text-aozora"
          >
            <Clipboard size={12} />
            jCard
          </button>
          <button
            type="button"
            onClick={() => downloadExport("vcard")}
            className="inline-flex items-center gap-1.5 rounded-md border border-sumi-700/60 px-2.5 py-1.5 text-[11px] text-sumi-300 transition-colors hover:border-aozora/60 hover:text-aozora"
          >
            <Download size={12} />
            VCF
          </button>
          <span className="self-center font-mono text-[10px] text-sumi-600">
            {copyState === "copied"
              ? "copied"
              : copyState === "downloaded"
                ? "downloaded"
                : copyState === "failed"
                  ? "failed"
                  : ""}
          </span>
        </div>
      </div>

      <div className="space-y-3 p-5">
        <InfoGrid
          rows={[
            ["callsign", agent.callsign],
            ["role", agent.role],
            ["status", agent.status],
            ["model", agent.model || agent.provider],
            ["harness", agent.harness],
            ["endpoint", agent.endpoint],
            ["team", agent.team_id],
            ["squad", agent.squad_id],
            ["authority", agent.authority],
            ["department", agent.department],
          ]}
        />

        <Layer title="Handoff" icon={<RadioTower size={14} />} defaultOpen>
          <ReadinessGrid agent={agent} />
          <SubjectList subjects={handoffSubjects} />
        </Layer>

        <Layer title="A2A Envelope" icon={<Network size={14} />} defaultOpen>
          <RecordTable entries={objectEntries(agent.a2a)} />
        </Layer>

        <Layer title="Semantic Commons" icon={<Globe2 size={14} />}>
          <RecordTable entries={objectEntries(agent.semantic)} empty="unresolved" />
        </Layer>

        <Layer title="Authority" icon={<KeyRound size={14} />}>
          <RecordTable entries={objectEntries(agent.identity_invariant)} empty="no invariant" />
          <div className="mt-3">
            <RecordTable entries={objectEntries(agent.authority_passport)} empty="no passport" />
          </div>
        </Layer>

        <Layer title="Findings" icon={<AlertTriangle size={14} />}>
          {agent.findings.length > 0 ? (
            <div className="space-y-2">
              {agent.findings.map((finding, index) => (
                <div
                  key={`${finding.check}-${finding.path}-${index}`}
                  className="rounded-md border border-sumi-800/80 bg-sumi-900/40 px-3 py-2"
                >
                  <div className="flex items-center justify-between gap-3">
                    <span
                      className="font-mono text-[10px] uppercase tracking-[0.1em]"
                      style={{
                        color:
                          finding.severity === "error"
                            ? colors.bengara
                            : colors.kinpaku,
                      }}
                    >
                      {finding.severity}
                    </span>
                    <span className="truncate font-mono text-[10px] text-sumi-600">
                      {finding.check}
                    </span>
                  </div>
                  <div className="mt-1 text-xs text-sumi-300">{finding.detail}</div>
                  <div className="mt-1 truncate font-mono text-[10px] text-sumi-600">
                    {finding.path}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyLine icon={<CheckCircle2 size={13} />} label="clean" />
          )}
        </Layer>

        <Layer title="Sources" icon={<FileJson size={14} />}>
          <SourceList entries={sourceEntries(agent)} />
        </Layer>

        <Layer title="Raw" icon={<FileJson size={14} />}>
          <pre className="max-h-80 overflow-auto rounded-md bg-sumi-900/60 p-3 text-[10px] leading-relaxed text-sumi-400">
            {JSON.stringify(agent, null, 2)}
          </pre>
        </Layer>
      </div>
    </aside>
  );
}

function StatusPill({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color: string;
}) {
  return (
    <div
      className="rounded-md border px-2 py-2"
      style={{
        borderColor: `color-mix(in srgb, ${color} 35%, transparent)`,
        backgroundColor: `color-mix(in srgb, ${color} 8%, transparent)`,
      }}
    >
      <div className="truncate text-[11px] font-semibold uppercase" style={{ color }}>
        {label || "-"}
      </div>
      <div className="mt-0.5 text-[9px] uppercase tracking-[0.1em] text-sumi-600">
        {value}
      </div>
    </div>
  );
}

function InfoGrid({ rows }: { rows: [string, unknown][] }) {
  return (
    <div className="grid grid-cols-2 gap-2">
      {rows.map(([label, value]) => (
        <div
          key={label}
          className="min-w-0 rounded-md border border-sumi-800/80 bg-sumi-900/40 px-3 py-2"
        >
          <div className="font-mono text-[9px] uppercase tracking-[0.1em] text-sumi-600">
            {label}
          </div>
          <div className="mt-1 truncate text-xs text-sumi-300">
            {compactValue(value)}
          </div>
        </div>
      ))}
    </div>
  );
}

function Layer({
  title,
  icon,
  children,
  defaultOpen = false,
}: {
  title: string;
  icon: ReactNode;
  children: ReactNode;
  defaultOpen?: boolean;
}) {
  return (
    <details
      open={defaultOpen}
      className="group rounded-lg border border-sumi-800/80 bg-sumi-900/30"
    >
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-3 py-2.5">
        <span className="flex items-center gap-2 text-xs font-semibold text-sumi-300">
          {icon}
          {title}
        </span>
        <span className="font-mono text-[10px] text-sumi-600 group-open:hidden">
          open
        </span>
        <span className="hidden font-mono text-[10px] text-sumi-600 group-open:inline">
          close
        </span>
      </summary>
      <div className="border-t border-sumi-800/80 p-3">{children}</div>
    </details>
  );
}

function ReadinessGrid({ agent }: { agent: AgentCardOut }) {
  const rows = [
    ["public", agent.handoff.public_card_ready],
    ["extended", agent.handoff.extended_card_ready],
    ["operator", agent.handoff.operator_card_ready],
  ] as const;

  return (
    <div className="grid grid-cols-3 gap-2">
      {rows.map(([label, ready]) => (
        <div
          key={label}
          className="rounded-md border border-sumi-800/80 bg-sumi-950/50 px-2 py-2 text-center"
        >
          <div
            className="font-mono text-[10px] uppercase"
            style={{ color: ready ? colors.rokusho : colors.kinpaku }}
          >
            {ready ? "ready" : "partial"}
          </div>
          <div className="mt-0.5 font-mono text-[9px] uppercase tracking-[0.1em] text-sumi-600">
            {label}
          </div>
        </div>
      ))}
    </div>
  );
}

function SubjectList({ subjects }: { subjects: string[] }) {
  if (subjects.length === 0) {
    return <EmptyLine icon={<RadioTower size={13} />} label="no subjects" />;
  }

  return (
    <div className="mt-3 space-y-1.5">
      {subjects.map((subject) => (
        <div
          key={subject}
          className="truncate rounded-md bg-sumi-950/60 px-2 py-1.5 font-mono text-[10px] text-sumi-400"
        >
          {subject}
        </div>
      ))}
    </div>
  );
}

function RecordTable({
  entries,
  empty = "none",
}: {
  entries: [string, unknown][];
  empty?: string;
}) {
  if (entries.length === 0) {
    return <EmptyLine icon={<ShieldCheck size={13} />} label={empty} />;
  }

  return (
    <div className="space-y-1.5">
      {entries.map(([key, value]) => (
        <div
          key={key}
          className="grid grid-cols-[120px_minmax(0,1fr)] gap-2 rounded-md bg-sumi-950/50 px-2 py-1.5"
        >
          <div className="truncate font-mono text-[10px] text-sumi-600">{key}</div>
          <div className="truncate text-[11px] text-sumi-300">
            {compactValue(value)}
          </div>
        </div>
      ))}
    </div>
  );
}

function SourceList({ entries }: { entries: [string, string[]][] }) {
  if (entries.length === 0) {
    return <EmptyLine icon={<FileJson size={13} />} label="no sources" />;
  }

  return (
    <div className="space-y-3">
      {entries.map(([kind, paths]) => (
        <div key={kind}>
          <div className="font-mono text-[10px] uppercase tracking-[0.1em] text-sumi-600">
            {kind}
          </div>
          <div className="mt-1 space-y-1.5">
            {paths.map((path) => (
              <div
                key={path}
                className="truncate rounded-md bg-sumi-950/60 px-2 py-1.5 font-mono text-[10px] text-sumi-400"
              >
                {path}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function EmptyLine({ icon, label }: { icon: ReactNode; label: string }) {
  return (
    <div className="flex items-center gap-2 rounded-md bg-sumi-950/50 px-2 py-2 text-xs text-sumi-500">
      {icon}
      {label}
    </div>
  );
}
