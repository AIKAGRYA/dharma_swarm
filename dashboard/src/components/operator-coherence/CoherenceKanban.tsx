"use client";

import type { KanbanLane } from "@/lib/operatorCoherence";
import { CoherenceCardView } from "./CoherenceCardView";

export function CoherenceKanban({ lanes }: { lanes: KanbanLane[] }) {
  return (
    <section className="rounded-xl border border-sumi-800/60 bg-sumi-950/50 p-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-sumi-500">
            Kanban
          </div>
          <h2 className="mt-1 text-lg font-semibold text-torinoko">
            Portfolio + Reality flow
          </h2>
        </div>
        <div className="text-xs text-sumi-500">
          {lanes.reduce((sum, lane) => sum + lane.count, 0)} cards
        </div>
      </div>
      <div className="mt-4 grid gap-3 overflow-x-auto lg:grid-cols-3 2xl:grid-cols-5">
        {lanes.map((lane) => (
          <div key={lane.lane} className="min-h-[220px] rounded-lg border border-sumi-800/50 bg-sumi-900/25 p-3">
            <div className="flex items-center justify-between gap-2">
              <h3 className="text-xs font-semibold uppercase tracking-[0.12em] text-sumi-400">
                {lane.lane}
              </h3>
              <span className="rounded-full bg-sumi-800/60 px-2 py-0.5 text-[10px] text-sumi-400">
                {lane.count}
              </span>
            </div>
            <div className="mt-3 space-y-2">
              {lane.cards.slice(0, 5).map((card) => (
                <CoherenceCardView key={card.id} card={card} compact />
              ))}
              {lane.count > 5 ? (
                <div className="text-[10px] text-sumi-600">+{lane.count - 5} more in JSON/API</div>
              ) : null}
              {lane.count === 0 ? (
                <div className="rounded border border-dashed border-sumi-800/70 p-3 text-xs text-sumi-600">
                  No cards
                </div>
              ) : null}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

