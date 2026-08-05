"use client";

import {
  AlertTriangle,
  CheckCircle2,
  CircleDashed,
  FlaskConical,
  FileCheck2,
  LockKeyhole,
  Radio,
  ShieldCheck,
} from "lucide-react";

import {
  authorityPresentation,
  cycleWitnessPresentation,
  type AutocatalyticCycleWitness,
  type PresentedAuthorityState,
} from "@/lib/autocatalyticPortfolio";

const stateIcons = {
  live: Radio,
  local_evidence: FileCheck2,
  local_rehearsal: FlaskConical,
  projection_only: CircleDashed,
  external_gated: LockKeyhole,
  unknown: AlertTriangle,
} satisfies Record<PresentedAuthorityState, typeof Radio>;

export function AuthorityBadge({
  authority,
  compact = false,
}: {
  authority: unknown;
  compact?: boolean;
}) {
  const presentation = authorityPresentation(authority);
  const Icon = stateIcons[presentation.state];
  return (
    <span
      className="inline-flex max-w-full items-center gap-1.5 rounded-full border px-2 py-1 font-mono text-[9px] font-semibold uppercase tracking-[0.08em]"
      style={{
        color: presentation.color,
        borderColor: `color-mix(in srgb, ${presentation.color} 35%, transparent)`,
        backgroundColor: `color-mix(in srgb, ${presentation.color} 10%, transparent)`,
      }}
      title={presentation.description}
    >
      <Icon size={compact ? 9 : 10} aria-hidden="true" />
      <span className="truncate">{presentation.label}</span>
    </span>
  );
}

export function CycleWitnessBadge({
  witness,
}: {
  witness: AutocatalyticCycleWitness | null | undefined;
}) {
  const presentation = cycleWitnessPresentation(witness);
  const Icon = presentation.state === "receipt_consistent" ? CheckCircle2 : AlertTriangle;
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 font-mono text-[9px] font-semibold uppercase tracking-[0.08em]"
      style={{
        color: presentation.color,
        borderColor: `color-mix(in srgb, ${presentation.color} 35%, transparent)`,
        backgroundColor: `color-mix(in srgb, ${presentation.color} 10%, transparent)`,
      }}
      title={presentation.description}
    >
      <Icon size={10} aria-hidden="true" />
      {presentation.label}
    </span>
  );
}

export function PanelHeading({
  icon: Icon = ShieldCheck,
  children,
}: {
  icon?: typeof ShieldCheck;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-center gap-2">
      <Icon size={14} className="text-aozora" aria-hidden="true" />
      <h2 className="text-[10px] font-semibold uppercase tracking-[0.14em] text-kitsurubami">
        {children}
      </h2>
    </div>
  );
}

export function LoadingSurface({ label = "Loading organism contract…" }: { label?: string }) {
  return (
    <div className="glass-panel flex min-h-[320px] items-center justify-center p-8">
      <div className="text-center">
        <CircleDashed size={24} className="mx-auto animate-spin text-aozora" />
        <p className="mt-3 text-sm text-sumi-600">{label}</p>
      </div>
    </div>
  );
}

export function ErrorSurface({ message }: { message: string }) {
  return (
    <div className="glass-panel border-bengara/30 p-6">
      <div className="flex items-start gap-3">
        <AlertTriangle size={18} className="mt-0.5 shrink-0 text-bengara" />
        <div>
          <p className="text-sm font-semibold text-bengara">Organism contract unavailable</p>
          <p className="mt-1 text-xs leading-relaxed text-sumi-600">{message}</p>
        </div>
      </div>
    </div>
  );
}

export function TruthBoundaryNotice() {
  return (
    <div className="rounded-lg border border-fuji/25 bg-fuji/5 px-4 py-3">
      <div className="flex items-start gap-2.5">
        <ShieldCheck size={15} className="mt-0.5 shrink-0 text-fuji" />
        <p className="text-[11px] leading-relaxed text-sumi-600">
          Graph edges are declared metabolic contracts, not observed production traffic. A ten-hop
          structural witness plus 41 matching mutable rows proves local receipt consistency only;
          it is not authenticated execution provenance, and transport acknowledgement is never
          enough.
        </p>
      </div>
    </div>
  );
}
