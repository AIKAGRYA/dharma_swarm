"use client";

import { useMemo, useState } from "react";
import type { ReactNode } from "react";
import {
  AlertTriangle,
  IdCard,
  RefreshCw,
  Search,
  ShieldAlert,
  ShieldCheck,
  Users,
} from "lucide-react";
import { AgentCardDetailPanel } from "@/components/agent-cards/AgentCardDetailPanel";
import { AgentCardMeishi } from "@/components/agent-cards/AgentCardMeishi";
import { useAgentCards } from "@/hooks/useAgentCards";
import {
  AGENT_CARD_TRUST_GRADES,
  filterAgentCards,
  uniqueAgentCardRoles,
  type AgentCardReadinessFilter,
} from "@/lib/agentCards";
import { colors } from "@/lib/theme";

export default function AgentCardsPage() {
  const { agents, summary, isLoading, isFetching, error, refetch } =
    useAgentCards();
  const [search, setSearch] = useState("");
  const [trustGrade, setTrustGrade] = useState("all");
  const [role, setRole] = useState("all");
  const [readiness, setReadiness] = useState<AgentCardReadinessFilter>("all");
  const [selectedUid, setSelectedUid] = useState<string | null>(null);

  const roles = useMemo(() => uniqueAgentCardRoles(agents), [agents]);
  const filteredAgents = useMemo(
    () =>
      filterAgentCards(agents, {
        search,
        trustGrade,
        role,
        readiness,
      }),
    [agents, search, trustGrade, role, readiness],
  );
  const selectedAgent =
    filteredAgents.find((agent) => agent.agent_uid === selectedUid) ??
    filteredAgents[0] ??
    null;

  const trustCounts = summary?.trust_grade_counts ?? {};
  const errorMessage = error instanceof Error ? error.message : String(error ?? "");

  return (
    <main className="min-h-screen space-y-5 p-6">
      <section className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <IdCard size={20} className="text-aozora" />
            <h1 className="font-heading text-2xl font-semibold text-torinoko">
              Agent Cards
            </h1>
          </div>
          <div className="mt-1 font-mono text-[11px] uppercase tracking-[0.14em] text-sumi-600">
            portable identity rolodex
          </div>
        </div>

        <button
          type="button"
          onClick={() => void refetch()}
          className="inline-flex h-9 items-center gap-2 self-start rounded-md border border-sumi-700/60 px-3 text-xs text-sumi-300 transition-colors hover:border-aozora/60 hover:text-aozora lg:self-auto"
        >
          <RefreshCw size={14} className={isFetching ? "animate-spin" : ""} />
          Refresh
        </button>
      </section>

      <section className="grid gap-3 md:grid-cols-5">
        <Metric label="Total" value={summary?.agent_count ?? agents.length} icon={<Users size={15} />} color={colors.aozora} />
        <Metric label="Verified" value={trustCounts.verified ?? 0} icon={<ShieldCheck size={15} />} color={colors.rokusho} />
        <Metric label="Registered" value={trustCounts.registered ?? 0} icon={<IdCard size={15} />} color={colors.aozora} />
        <Metric label="Quarantine" value={trustCounts.quarantine ?? 0} icon={<ShieldAlert size={15} />} color={colors.bengara} />
        <Metric label="Findings" value={summary?.finding_count ?? 0} icon={<AlertTriangle size={15} />} color={(summary?.error_count ?? 0) > 0 ? colors.bengara : colors.kinpaku} />
      </section>

      <section className="rounded-lg border border-sumi-700/40 bg-sumi-950/60 p-3">
        <div className="grid gap-3 lg:grid-cols-[minmax(220px,1fr)_170px_170px_170px]">
          <label className="relative block">
            <Search
              size={14}
              className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-sumi-600"
            />
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search uid, model, role, capability"
              className="h-9 w-full rounded-md border border-sumi-700/50 bg-sumi-900/70 pl-9 pr-3 text-sm text-torinoko placeholder-sumi-600 outline-none transition-colors focus:border-aozora/60"
            />
          </label>

          <Select value={trustGrade} onChange={setTrustGrade} label="Trust">
            <option value="all">All trust</option>
            {AGENT_CARD_TRUST_GRADES.map((grade) => (
              <option key={grade} value={grade}>
                {grade}
              </option>
            ))}
          </Select>

          <Select value={role} onChange={setRole} label="Role">
            <option value="all">All roles</option>
            {roles.map((entry) => (
              <option key={entry} value={entry}>
                {entry}
              </option>
            ))}
          </Select>

          <Select
            value={readiness}
            onChange={(value) => setReadiness(value as AgentCardReadinessFilter)}
            label="Readiness"
          >
            <option value="all">All readiness</option>
            <option value="handoff">Handoff ready</option>
            <option value="public">Public ready</option>
            <option value="blocked">Blocked</option>
          </Select>
        </div>
      </section>

      {error ? (
        <section className="rounded-lg border border-bengara/40 bg-bengara/10 px-4 py-3 text-sm text-bengara">
          {errorMessage || "Agent Card API unavailable"}
        </section>
      ) : null}

      <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_460px]">
        <div className="min-w-0">
          <div className="mb-3 flex items-center justify-between gap-3">
            <div className="font-mono text-[11px] uppercase tracking-[0.14em] text-sumi-600">
              {filteredAgents.length} shown
            </div>
            <div
              className="rounded-md border px-2 py-1 font-mono text-[10px] uppercase tracking-[0.1em]"
              style={{
                borderColor:
                  summary?.status === "pass"
                    ? `color-mix(in srgb, ${colors.rokusho} 35%, transparent)`
                    : `color-mix(in srgb, ${colors.bengara} 35%, transparent)`,
                color: summary?.status === "pass" ? colors.rokusho : colors.bengara,
              }}
            >
              {summary?.status ?? "loading"}
            </div>
          </div>

          {isLoading ? (
            <LoadingGrid />
          ) : filteredAgents.length > 0 ? (
            <div className="grid grid-cols-[repeat(auto-fill,minmax(278px,1fr))] gap-3">
              {filteredAgents.map((agent) => (
                <AgentCardMeishi
                  key={agent.agent_uid}
                  agent={agent}
                  selected={agent.agent_uid === selectedAgent?.agent_uid}
                  onSelect={(nextAgent) => setSelectedUid(nextAgent.agent_uid)}
                />
              ))}
            </div>
          ) : (
            <div className="rounded-lg border border-sumi-700/40 bg-sumi-950/60 px-4 py-12 text-center text-sm text-sumi-500">
              No cards match the current filters.
            </div>
          )}
        </div>

        <div className="xl:sticky xl:top-6 xl:self-start">
          <AgentCardDetailPanel agent={selectedAgent} />
        </div>
      </section>
    </main>
  );
}

function Metric({
  label,
  value,
  icon,
  color,
}: {
  label: string;
  value: number;
  icon: ReactNode;
  color: string;
}) {
  return (
    <div
      className="rounded-lg border bg-sumi-950/60 px-4 py-3"
      style={{
        borderColor: `color-mix(in srgb, ${color} 24%, transparent)`,
      }}
    >
      <div className="flex items-center justify-between gap-3">
        <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-sumi-600">
          {label}
        </span>
        <span style={{ color }}>{icon}</span>
      </div>
      <div className="mt-2 font-heading text-2xl font-semibold text-torinoko">
        {value}
      </div>
    </div>
  );
}

function Select({
  value,
  onChange,
  label,
  children,
}: {
  value: string;
  onChange: (value: string) => void;
  label: string;
  children: ReactNode;
}) {
  return (
    <label className="block">
      <span className="sr-only">{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="h-9 w-full rounded-md border border-sumi-700/50 bg-sumi-900/70 px-3 text-sm text-torinoko outline-none transition-colors focus:border-aozora/60"
      >
        {children}
      </select>
    </label>
  );
}

function LoadingGrid() {
  return (
    <div className="grid grid-cols-[repeat(auto-fill,minmax(278px,1fr))] gap-3">
      {Array.from({ length: 8 }).map((_, index) => (
        <div
          key={index}
          className="min-h-[244px] animate-pulse rounded-lg border border-sumi-800/80 bg-sumi-950/60"
        />
      ))}
    </div>
  );
}
