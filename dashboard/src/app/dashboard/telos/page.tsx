import {
  FileText,
  LockKeyhole,
  Network,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { colors } from "@/lib/theme";

const pipeline = [
  {
    name: "Raw Pointer",
    state: "private",
    detail: "Encrypted local reference plus content hash. Raw text does not enter repo artifacts.",
  },
  {
    name: "Essence Pass",
    state: "source-faithful",
    detail: "Invariants, tensions, themes, questions, and idea seeds are extracted from approved input.",
  },
  {
    name: "Hardened Node",
    state: "correctable",
    detail: "The user can correct the semantic packet before anything moves outward.",
  },
  {
    name: "Empire Screen",
    state: "sanitized",
    detail: "Portfolio and venture agents see hardened nodes only, never raw morning pages.",
  },
  {
    name: "Receipt Gate",
    state: "external proof required",
    detail: "Public, SAB, venture, or revenue claims wait for an acted external receipt.",
  },
];

const guardrails = [
  "raw_shared: false",
  "private by default",
  "no raw upward flow",
  "receipt before promotion",
  "no external account action",
];

const packetFields = [
  "invariants",
  "categories",
  "themes",
  "idea seeds",
  "tensions",
  "next questions",
  "promotion state",
  "consent flags",
];

const links = [
  {
    label: "Morning Refinery Spec",
    path: "docs/vision_maps/TELOS_MORNING_REFINERY_V0.md",
  },
  {
    label: "Seed Spec",
    path: "docs/vision_maps/TELOS_AI_SEED_SPEC_V0.md",
  },
  {
    label: "Sanitized Example",
    path: "docs/research/telos_ai/refinery_examples/2026-06-13_ARTICULATE_ESSENCE_EXTRATOR_NODE_trial_001.md",
  },
  {
    label: "Receipt Schema",
    path: "reports/telos_ai/EXTERNAL_ACTED_RECEIPT_SCHEMA.md",
  },
];

function StatusPill({ label, color }: { label: string; color: string }) {
  return (
    <span
      className="inline-flex items-center rounded-lg border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em]"
      style={{
        borderColor: `color-mix(in srgb, ${color} 32%, transparent)`,
        backgroundColor: `color-mix(in srgb, ${color} 9%, transparent)`,
        color,
      }}
    >
      {label}
    </span>
  );
}

export default function TelosMorningRefineryPage() {
  return (
    <main className="space-y-6">
      <section className="glass-panel p-5">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div className="space-y-3">
            <div className="flex items-center gap-3">
              <div className="flex h-11 w-11 items-center justify-center rounded-lg border border-kinpaku/30 bg-kinpaku/10 text-kinpaku">
                <Sparkles size={22} />
              </div>
              <div>
                <h1 className="font-heading text-2xl font-bold tracking-tight text-kinpaku">
                  TELOS Morning Refinery
                </h1>
                <p className="mt-1 max-w-3xl text-sm leading-6 text-sumi-600">
                  Private morning-page packets become corrected semantic nodes, then consent-gated outward candidates.
                </p>
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <StatusPill label="prototype" color={colors.aozora} />
              <StatusPill label="private by default" color={colors.rokusho} />
              <StatusPill label="external receipt absent" color={colors.kinpaku} />
            </div>
          </div>

          <div className="grid grid-cols-3 gap-3 text-center">
            <div className="rounded-lg border border-sumi-700/40 bg-sumi-900/50 px-4 py-3">
              <div className="font-mono text-xl font-semibold text-torinoko">2</div>
              <div className="mt-1 text-[10px] uppercase tracking-[0.12em] text-sumi-600">Engines</div>
            </div>
            <div className="rounded-lg border border-sumi-700/40 bg-sumi-900/50 px-4 py-3">
              <div className="font-mono text-xl font-semibold text-torinoko">0</div>
              <div className="mt-1 text-[10px] uppercase tracking-[0.12em] text-sumi-600">Raw exports</div>
            </div>
            <div className="rounded-lg border border-sumi-700/40 bg-sumi-900/50 px-4 py-3">
              <div className="font-mono text-xl font-semibold text-torinoko">0</div>
              <div className="mt-1 text-[10px] uppercase tracking-[0.12em] text-sumi-600">Claims</div>
            </div>
          </div>
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-[1.35fr_0.65fr]">
        <div className="glass-panel p-5">
          <div className="mb-4 flex items-center gap-2">
            <Network size={18} className="text-aozora" />
            <h2 className="font-heading text-lg font-semibold text-torinoko">Pipeline</h2>
          </div>
          <div className="grid gap-3 lg:grid-cols-5">
            {pipeline.map((stage, index) => (
              <article key={stage.name} className="rounded-lg border border-sumi-700/35 bg-sumi-900/45 p-4">
                <div className="mb-3 flex items-center justify-between gap-2">
                  <span className="font-mono text-xs text-sumi-600">0{index}</span>
                  <StatusPill label={stage.state} color={index < 3 ? colors.rokusho : colors.kinpaku} />
                </div>
                <h3 className="font-heading text-sm font-semibold text-torinoko">{stage.name}</h3>
                <p className="mt-2 text-xs leading-5 text-sumi-600">{stage.detail}</p>
              </article>
            ))}
          </div>
        </div>

        <div className="glass-panel p-5">
          <div className="mb-4 flex items-center gap-2">
            <LockKeyhole size={18} className="text-rokusho" />
            <h2 className="font-heading text-lg font-semibold text-torinoko">Boundary</h2>
          </div>
          <div className="flex flex-wrap gap-2">
            {guardrails.map((item) => (
              <span
                key={item}
                className="rounded-lg border border-rokusho/25 bg-rokusho/10 px-2.5 py-1.5 text-xs text-rokusho"
              >
                {item}
              </span>
            ))}
          </div>
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <div className="glass-panel p-5">
          <div className="mb-4 flex items-center gap-2">
            <FileText size={18} className="text-botan" />
            <h2 className="font-heading text-lg font-semibold text-torinoko">Packet Shape</h2>
          </div>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {packetFields.map((field) => (
              <div key={field} className="rounded-lg border border-sumi-700/35 bg-sumi-900/45 px-3 py-2">
                <span className="text-xs text-torinoko">{field}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="glass-panel p-5">
          <div className="mb-4 flex items-center gap-2">
            <ShieldCheck size={18} className="text-kinpaku" />
            <h2 className="font-heading text-lg font-semibold text-torinoko">Proof State</h2>
          </div>
          <div className="space-y-3 text-sm leading-6 text-sumi-600">
            <p>
              The local prototype can show sanitized packet structure and consent gates. It does not create the first
              external acted receipt.
            </p>
            <p>
              Promotion remains blocked until an external human acts on a consented TELOS output and the receipt is
              written under the tracked schema.
            </p>
          </div>
        </div>
      </section>

      <section className="glass-panel p-5">
        <div className="mb-4 flex items-center justify-between gap-4">
          <h2 className="font-heading text-lg font-semibold text-torinoko">Anchors</h2>
          <StatusPill label="read only" color={colors.fuji} />
        </div>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {links.map((item) => (
            <div key={item.path} className="min-h-16 rounded-lg border border-sumi-700/35 bg-sumi-900/45 px-4 py-3">
              <div className="text-sm text-torinoko">{item.label}</div>
              <div className="mt-2 break-words font-mono text-[11px] leading-4 text-sumi-600">{item.path}</div>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}
