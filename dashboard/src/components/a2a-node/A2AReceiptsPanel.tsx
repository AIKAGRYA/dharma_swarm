"use client";

import { AlertTriangle, ShieldCheck } from "lucide-react";
import {
  readEvidenceField,
  readReceiptEvidence,
  type ReceiptLadder,
} from "@/lib/a2aNodeModel";
import {
  PanelHeader,
  SurfaceMessage,
  ageFrom,
  errorText,
} from "./A2ANodePanels";

const tierDetail: Record<string, string> = {
  DOMAIN_RECEIPTED: "Target-owned domain receipt observed.",
  HANDLER_ACKED: "Target handler acknowledged consumption.",
  CORE_FLUSH_ONLY: "Core client flushed; handler contact unproven.",
  PUBLISH_ACCEPTED: "Broker accepted publish; delivery unproven.",
  NO_CONTACT: "No live contact established.",
};

export function ReceiptsPanel({
  cards,
  ladder,
  nowMs,
  isLoading,
  error,
}: {
  cards: readonly unknown[];
  ladder: ReceiptLadder;
  nowMs: number;
  isLoading: boolean;
  error: unknown;
}) {
  return (
    <div>
      <PanelHeader
        eyebrow="Receipts"
        title="Evidence, without inflation"
        detail="Strongest to weakest. Counts come only from explicit contact tiers; card status never upgrades a receipt."
        action={{ href: "/dashboard/command-post", label: "Command post" }}
      />
      {error ? (
        <SurfaceMessage
          kind="error"
          title="Receipt projection unreachable"
          detail={errorText(error)}
        />
      ) : isLoading ? (
        <SurfaceMessage
          kind="loading"
          title="Reading receipt evidence"
          detail="Waiting for the existing A2A card projection."
        />
      ) : (
        <>
          <ol className="overflow-hidden rounded-2xl border border-sumi-700/35 bg-sumi-900/60">
            {ladder.tiers.map((item, index) => (
              <li
                key={item.tier}
                className="flex items-center gap-3 border-b border-sumi-800/70 px-4 py-3 last:border-b-0"
              >
                <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full border border-sumi-700/40 bg-sumi-950 font-mono text-xs text-kitsurubami/75">
                  {index + 1}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate font-mono text-xs font-semibold text-torinoko">
                    {item.tier}
                  </p>
                  <p className="mt-0.5 text-xs text-kitsurubami/75">
                    {tierDetail[item.tier]}
                  </p>
                </div>
                <span className="min-w-7 rounded-lg bg-sumi-950/70 px-2 py-1 text-center font-mono text-xs text-kitsurubami">
                  {item.count}
                </span>
              </li>
            ))}
          </ol>

          {ladder.unknown.length ? (
            <div
              className="mt-3 rounded-2xl border border-bengara/40 bg-bengara/[0.08] p-4"
              role="alert"
            >
              <div className="flex items-center gap-2 text-bengara">
                <AlertTriangle size={15} aria-hidden="true" />
                <h2 className="text-xs font-semibold uppercase tracking-[0.12em]">
                  Unknown evidence · {ladder.unknown.length}
                </h2>
              </div>
              <ul className="mt-3 space-y-2">
                {ladder.unknown.map((item) => (
                  <li
                    key={item.key}
                    className="rounded-xl border border-bengara/20 bg-sumi-950/35 px-3 py-2"
                  >
                    <p className="truncate text-xs text-torinoko">{item.id}</p>
                    <p className="mt-1 font-mono text-xs text-bengara">
                      raw tier: {item.rawTier}
                    </p>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          <section className="mt-6" aria-labelledby="receipt-records-heading">
            <div className="mb-2 flex items-center justify-between">
              <h2
                id="receipt-records-heading"
                className="text-xs font-semibold uppercase tracking-[0.14em] text-kitsurubami/75"
              >
                Observed records
              </h2>
              <span className="font-mono text-xs text-kitsurubami/75">
                {cards.length} total
              </span>
            </div>
            {cards.length ? (
              <div className="grid gap-2 md:grid-cols-2">
                {cards.map((card, index) => {
                  const evidence =
                    ladder.records[index] ??
                    readReceiptEvidence(card, index, nowMs);
                  const target =
                    readEvidenceField(card, "to") ||
                    readEvidenceField(card, "agent_uid") ||
                    "unknown peer";
                  const title =
                    readEvidenceField(card, "title") ||
                    "Unknown A2A evidence";
                  const createdAt = readEvidenceField(card, "created_at");
                  const unknown = evidence.state === "unknown";
                  return (
                    <article
                      key={evidence.key}
                      className={`rounded-2xl border p-4 ${
                        unknown
                          ? "border-bengara/40 bg-bengara/[0.07]"
                          : "border-sumi-700/35 bg-sumi-900/55"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p
                            className={`font-mono text-xs uppercase tracking-[0.12em] ${
                              unknown ? "text-bengara" : "text-kitsurubami/75"
                            }`}
                          >
                            {unknown ? "Unknown evidence" : target}
                          </p>
                          <h3 className="mt-1 line-clamp-2 text-sm font-medium text-torinoko">
                            {title}
                          </h3>
                        </div>
                        {unknown ? (
                          <AlertTriangle
                            size={15}
                            className="shrink-0 text-bengara"
                            aria-hidden="true"
                          />
                        ) : (
                          <ShieldCheck
                            size={15}
                            className="shrink-0 text-rokusho"
                            aria-hidden="true"
                          />
                        )}
                      </div>
                      <div className="mt-3 flex items-center justify-between gap-3">
                        <span
                          className={`truncate font-mono text-xs ${
                            unknown ? "text-bengara" : "text-kitsurubami/75"
                          }`}
                        >
                          {evidence.rawTier}
                        </span>
                        <time
                          dateTime={createdAt || undefined}
                          className="shrink-0 text-xs text-kitsurubami/75"
                        >
                          {ageFrom(createdAt, nowMs)}
                        </time>
                      </div>
                    </article>
                  );
                })}
              </div>
            ) : (
              <SurfaceMessage
                kind="empty"
                title="No contact receipts observed"
                detail="The receipt API answered cleanly. No contact evidence exists on this host."
              />
            )}
          </section>
        </>
      )}
    </div>
  );
}
