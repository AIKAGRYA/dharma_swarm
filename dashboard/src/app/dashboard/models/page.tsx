"use client";

import Link from "next/link";
import { useState } from "react";
import { motion } from "framer-motion";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowUpRight,
  CheckCircle2,
  Cpu,
  ExternalLink,
  Link2,
  Loader2,
  RefreshCcw,
  Save,
  Sparkles,
  XCircle,
} from "lucide-react";
import { apiFetch, fetchRoutingManifest } from "@/lib/api";
import { colors } from "@/lib/theme";
import type { ModelProfileOut, RoutingManifestOut, TopModelOut, VerifyTop10Out } from "@/lib/types";

type DraftMap = Record<string, { custom_label: string; short_name: string }>;

function verificationTone(status: string): { color: string; border: string; bg: string } {
  if (status === "ok") {
    return {
      color: colors.rokusho,
      border: `color-mix(in srgb, ${colors.rokusho} 35%, transparent)`,
      bg: `color-mix(in srgb, ${colors.rokusho} 8%, transparent)`,
    };
  }
  if (status === "error" || status === "unexpected") {
    return {
      color: colors.bengara,
      border: `color-mix(in srgb, ${colors.bengara} 35%, transparent)`,
      bg: `color-mix(in srgb, ${colors.bengara} 8%, transparent)`,
    };
  }
  return {
    color: colors.kinpaku,
    border: `color-mix(in srgb, ${colors.kinpaku} 35%, transparent)`,
    bg: `color-mix(in srgb, ${colors.kinpaku} 8%, transparent)`,
  };
}

function VerificationBadge({ status }: { status: string }) {
  const tone = verificationTone(status);
  const Icon = status === "ok" ? CheckCircle2 : status === "error" || status === "unexpected" ? XCircle : Loader2;
  return (
    <span
      className="inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em]"
      style={{
        color: tone.color,
        borderColor: tone.border,
        backgroundColor: tone.bg,
      }}
    >
      <Icon size={12} className={status === "unverified" ? "animate-spin" : ""} />
      {status}
    </span>
  );
}

export default function ModelsPage() {
  const qc = useQueryClient();
  const [drafts, setDrafts] = useState<DraftMap>({});

  const { data: models = [], isLoading } = useQuery<TopModelOut[]>({
    queryKey: ["top10-model-status"],
    queryFn: () => apiFetch<TopModelOut[]>("/api/pool/top10/status"),
    refetchInterval: 30_000,
  });

  const { data: manifest } = useQuery<RoutingManifestOut>({
    queryKey: ["routing-manifest", "models-page"],
    queryFn: async () => {
      const response = await fetchRoutingManifest({
        provider: "codex",
        model: "gpt-5.4",
        strategy: "responsive",
      });
      if (response.status === "error") {
        throw new Error(response.error || "Failed to load routing manifest");
      }
      return response.data;
    },
    refetchInterval: 30_000,
  });

  const verifyMutation = useMutation({
    mutationFn: () => apiFetch<VerifyTop10Out>("/api/pool/top10/verify", { method: "POST" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["top10-model-status"] });
    },
  });

  const saveMutation = useMutation({
    mutationFn: async ({
      modelId,
      body,
    }: {
      modelId: string;
      body: { custom_label: string; short_name: string };
    }) =>
      apiFetch<ModelProfileOut>(`/api/pool/models/${encodeURIComponent(modelId)}/profile`, {
        method: "PATCH",
        body: JSON.stringify(body),
      }),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ["top10-model-status"] });
      setDrafts((prev) => ({
        ...prev,
        [vars.modelId]: {
          custom_label: vars.body.custom_label,
          short_name: vars.body.short_name,
        },
      }));
    },
  });

  const verifiedCount = models.filter((model) => model.verification?.status === "ok").length;
  const availableCount = models.filter((model) => model.available).length;
  const selectableRoutes = manifest?.selectable_routes ?? [];
  const catalogEntries = manifest?.adapter_catalog ?? [];
  const policyCatalogEntries = catalogEntries.filter((entry) => entry.policy_selectable);
  const catalogOnlyEntries = catalogEntries.filter((entry) => !entry.policy_selectable);

  return (
    <div className="space-y-6">
      <motion.section
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="relative overflow-hidden rounded-[28px] border border-sumi-700/40 bg-sumi-900/90 p-6"
      >
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(79,209,217,0.16),transparent_32%),radial-gradient(circle_at_78%_24%,rgba(212,125,181,0.12),transparent_24%),linear-gradient(180deg,rgba(13,14,19,0.25),rgba(13,14,19,0.8))]" />
        <div className="relative flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div className="space-y-3">
            <div className="flex items-center gap-3">
              <div className="rounded-2xl border border-aozora/30 bg-aozora/10 p-3 text-aozora">
                <Sparkles size={24} />
              </div>
              <div>
                <h1 className="glow-aozora font-heading text-3xl font-bold tracking-tight text-aozora">
                  Model Pool
                </h1>
                <p className="mt-1 max-w-3xl text-sm text-sumi-600">
                  One ranked surface for the ten models you actually care about: live routes, official links,
                  custom UI names, and verification evidence.
                </p>
              </div>
            </div>
            <div className="grid gap-3 sm:grid-cols-3">
              <MetricPill label="Selectable Routes" value={String(selectableRoutes.length || models.length)} accent={colors.aozora} />
              <MetricPill label="Adapter Catalog" value={String(catalogEntries.length || availableCount)} accent={colors.rokusho} />
              <MetricPill label="Drift Warnings" value={String(manifest?.counts.drift ?? 0)} accent={manifest?.counts.drift ? colors.bengara : colors.kinpaku} />
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <Link
              href="/dashboard/agents"
              className="inline-flex items-center gap-2 rounded-xl border border-sumi-700/40 bg-sumi-850/60 px-4 py-2 text-sm text-torinoko transition-colors hover:border-aozora/30 hover:text-aozora"
            >
              Agent Routing
              <ArrowUpRight size={14} />
            </Link>
            <button
              onClick={() => verifyMutation.mutate()}
              disabled={verifyMutation.isPending}
              className="inline-flex items-center gap-2 rounded-xl border border-aozora/35 bg-aozora/10 px-4 py-2 text-sm font-medium text-aozora transition-colors hover:border-aozora/50 hover:bg-aozora/15 disabled:opacity-50"
            >
              {verifyMutation.isPending ? <Loader2 size={14} className="animate-spin" /> : <RefreshCcw size={14} />}
              Verify All 10
            </button>
          </div>
        </div>
      </motion.section>

      {verifyMutation.data && (
        <div
          className="rounded-2xl border px-4 py-3 text-sm"
          style={{
            borderColor: `color-mix(in srgb, ${colors.rokusho} 30%, transparent)`,
            backgroundColor: `color-mix(in srgb, ${colors.rokusho} 6%, transparent)`,
            color: colors.torinoko,
          }}
        >
          Verification finished at {new Date(verifyMutation.data.verified_at).toLocaleString()} with{" "}
          {verifyMutation.data.ok_count}/10 success.
        </div>
      )}

      {manifest && (
        <motion.section
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35 }}
          className="grid gap-4 lg:grid-cols-[1.4fr_1fr]"
        >
          <div className="glass-panel p-5">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-sumi-600">
                  Canonical routing manifest
                </p>
                <h2 className="mt-1 font-heading text-xl font-semibold text-torinoko">
                  {manifest.selected_route || "unknown route"}
                </h2>
                <p className="mt-1 text-sm text-sumi-600">
                  Dashboard and TUI now share this route-policy contract. The picker should use selectable routes; the catalog is metadata.
                </p>
              </div>
              <span
                className="rounded-full border px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.12em]"
                style={{
                  color: manifest.counts.drift ? colors.bengara : colors.rokusho,
                  borderColor: `color-mix(in srgb, ${manifest.counts.drift ? colors.bengara : colors.rokusho} 35%, transparent)`,
                  backgroundColor: `color-mix(in srgb, ${manifest.counts.drift ? colors.bengara : colors.rokusho} 8%, transparent)`,
                }}
              >
                {manifest.counts.drift ? `${manifest.counts.drift} drift` : "aligned"}
              </span>
            </div>

            <div className="mt-5 grid gap-3 md:grid-cols-3">
              <ManifestStat label="Selectable" value={String(manifest.counts.selectable_routes)} />
              <ManifestStat label="Catalog" value={String(manifest.counts.adapter_catalog)} />
              <ManifestStat label="Legacy aliases" value={String(manifest.counts.legacy_targets)} />
            </div>

            <div className="mt-5 grid gap-2 sm:grid-cols-2">
              {selectableRoutes.slice(0, 8).map((route) => (
                <div key={`${route.provider}:${route.model}`} className="rounded-xl border border-sumi-700/35 bg-sumi-900/45 px-3 py-2">
                  <div className="flex items-center justify-between gap-3">
                    <span className="truncate font-mono text-xs text-torinoko">{route.provider}:{route.model}</span>
                    <span className="shrink-0 text-[10px] uppercase tracking-[0.12em] text-sumi-600">{route.tier ?? "tier"}</span>
                  </div>
                  <p className="mt-1 truncate text-[11px] text-sumi-600">{route.lane_role?.replaceAll("_", " ") ?? route.alias}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="glass-panel p-5">
            <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-sumi-600">
              Catalog split
            </p>
            <h3 className="mt-1 font-heading text-lg font-semibold text-torinoko">
              {policyCatalogEntries.length} route-backed, {catalogOnlyEntries.length} catalog-only
            </h3>
            <p className="mt-2 text-sm text-sumi-600">
              Catalog-only models are callable metadata, not first-class operating lanes unless promoted through policy.
            </p>
            <div className="mt-4 space-y-2">
              {catalogOnlyEntries.slice(0, 6).map((entry) => (
                <div key={entry.route_id} className="flex items-center justify-between gap-3 rounded-xl border border-sumi-700/30 bg-sumi-900/35 px-3 py-2">
                  <span className="min-w-0 truncate font-mono text-[11px] text-kitsurubami">{entry.route_id}</span>
                  <span className="shrink-0 text-[10px] text-sumi-600">catalog</span>
                </div>
              ))}
            </div>
          </div>
        </motion.section>
      )}

      <div className="grid gap-4 xl:grid-cols-2">
        {models.map((model, index) => {
          const draft = drafts[model.id] ?? {
            custom_label: model.custom_label ?? "",
            short_name: model.short_name ?? "",
          };
          return (
            <motion.article
              key={model.id}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.35, delay: index * 0.03 }}
              className="glass-panel p-5"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <span
                      className="rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-[0.14em]"
                      style={{
                        color: colors.kinpaku,
                        backgroundColor: `color-mix(in srgb, ${colors.kinpaku} 12%, transparent)`,
                      }}
                    >
                      #{model.rank}
                    </span>
                    <VerificationBadge status={model.verification?.status ?? "unverified"} />
                  </div>
                  <div>
                    <h2 className="font-heading text-xl font-semibold text-torinoko">{model.ui_label}</h2>
                    {model.ui_label !== model.display_name && (
                      <p className="mt-1 text-xs text-sumi-600">Base model: {model.display_name}</p>
                    )}
                  </div>
                </div>

                <div className="text-right text-xs text-sumi-600">
                  <div>{model.provider}</div>
                  <div>{model.max_context.toLocaleString()} ctx</div>
                </div>
              </div>

              <div className="mt-4 flex flex-wrap gap-2">
                {model.strengths.map((strength) => (
                  <span
                    key={strength}
                    className="rounded-full border px-2 py-1 text-[10px] uppercase tracking-[0.12em]"
                    style={{
                      borderColor: `color-mix(in srgb, ${colors.aozora} 22%, transparent)`,
                      color: colors.aozora,
                      backgroundColor: `color-mix(in srgb, ${colors.aozora} 7%, transparent)`,
                    }}
                  >
                    {strength.replaceAll("_", " ")}
                  </span>
                ))}
              </div>

              <div className="mt-4 grid gap-3 md:grid-cols-2">
                <div className="rounded-2xl border border-sumi-700/30 bg-sumi-900/45 p-3">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-sumi-600">
                    Route
                  </p>
                  <p className="mt-2 font-mono text-xs text-torinoko">
                    {model.available_routes?.[0] || model.routes?.[0] || model.provider}
                  </p>
                  <p className="mt-1 text-xs text-sumi-600">
                    {model.available ? "Callable now" : "Configured but currently unavailable"}
                  </p>
                  {model.verification?.verified_at && (
                    <p className="mt-2 text-[11px] text-sumi-600">
                      Verified {new Date(model.verification.verified_at).toLocaleString()}
                    </p>
                  )}
                </div>
                <div className="rounded-2xl border border-sumi-700/30 bg-sumi-900/45 p-3">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-sumi-600">
                    Verification
                  </p>
                  <p className="mt-2 text-xs text-torinoko">
                    {model.verification?.response_preview || model.notes || "No live probe saved yet."}
                  </p>
                  {model.verification?.error && (
                    <p className="mt-2 text-[11px] text-bengara">{model.verification.error}</p>
                  )}
                </div>
              </div>

              <div className="mt-4 flex flex-wrap gap-3">
                <a
                  href={model.docs_url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1.5 rounded-lg border border-sumi-700/40 px-3 py-1.5 text-xs text-torinoko transition-colors hover:border-aozora/35 hover:text-aozora"
                >
                  <Link2 size={12} />
                  Docs
                  <ExternalLink size={11} />
                </a>
                <a
                  href={model.provider_url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1.5 rounded-lg border border-sumi-700/40 px-3 py-1.5 text-xs text-torinoko transition-colors hover:border-aozora/35 hover:text-aozora"
                >
                  <ExternalLink size={12} />
                  Provider
                </a>
              </div>

              <div className="mt-5 grid gap-3 md:grid-cols-[1fr_180px_auto]">
                <label className="space-y-1">
                  <span className="block text-[10px] font-semibold uppercase tracking-[0.12em] text-sumi-600">
                    Custom Label
                  </span>
                  <input
                    value={draft.custom_label}
                    onChange={(e) =>
                      setDrafts((prev) => ({
                        ...prev,
                        [model.id]: {
                          ...draft,
                          custom_label: e.target.value,
                        },
                      }))
                    }
                    placeholder={model.display_name}
                    className="w-full rounded-xl border border-sumi-700/40 bg-sumi-900 px-3 py-2 text-sm text-torinoko outline-none transition-colors focus:border-aozora/45"
                  />
                </label>

                <label className="space-y-1">
                  <span className="block text-[10px] font-semibold uppercase tracking-[0.12em] text-sumi-600">
                    Short Name
                  </span>
                  <input
                    value={draft.short_name}
                    onChange={(e) =>
                      setDrafts((prev) => ({
                        ...prev,
                        [model.id]: {
                          ...draft,
                          short_name: e.target.value,
                        },
                      }))
                    }
                    placeholder="Opus / Codex / GLM"
                    className="w-full rounded-xl border border-sumi-700/40 bg-sumi-900 px-3 py-2 text-sm text-torinoko outline-none transition-colors focus:border-aozora/45"
                  />
                </label>

                <div className="flex items-end">
                  <button
                    onClick={() =>
                      saveMutation.mutate({
                        modelId: model.id,
                        body: {
                          custom_label: draft.custom_label,
                          short_name: draft.short_name,
                        },
                      })
                    }
                    disabled={saveMutation.isPending}
                    className="inline-flex w-full items-center justify-center gap-2 rounded-xl border border-kinpaku/30 bg-kinpaku/10 px-4 py-2 text-sm font-medium text-kinpaku transition-colors hover:border-kinpaku/45 hover:bg-kinpaku/15 disabled:opacity-50"
                  >
                    <Save size={14} />
                    Save
                  </button>
                </div>
              </div>
            </motion.article>
          );
        })}

        {!isLoading && models.length === 0 && (
          <div className="glass-panel col-span-full flex min-h-[220px] items-center justify-center text-sm text-sumi-600">
            No top-ten models loaded.
          </div>
        )}
      </div>
    </div>
  );
}

function MetricPill({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent: string;
}) {
  return (
    <div
      className="rounded-2xl border px-4 py-3"
      style={{
        borderColor: `color-mix(in srgb, ${accent} 28%, transparent)`,
        backgroundColor: `color-mix(in srgb, ${accent} 8%, transparent)`,
      }}
    >
      <div className="flex items-center gap-2">
        <Cpu size={14} style={{ color: accent }} />
        <span className="text-[10px] font-semibold uppercase tracking-[0.12em] text-sumi-600">{label}</span>
      </div>
      <p className="mt-2 text-lg font-semibold text-torinoko">{value}</p>
    </div>
  );
}

function ManifestStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-sumi-700/35 bg-sumi-900/40 px-4 py-3">
      <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-sumi-600">{label}</p>
      <p className="mt-1 font-mono text-lg font-semibold text-torinoko">{value}</p>
    </div>
  );
}
