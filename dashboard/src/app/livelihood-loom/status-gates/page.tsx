import type { Metadata } from "next";
import { PublicShell } from "@/components/livelihood-loom/public/PublicShell";
import { SectionHeader } from "@/components/livelihood-loom/public/SectionHeader";
import { TruthGate } from "@/components/livelihood-loom/public/TruthGate";
import { loadLivelihoodLoomStatusGates } from "@/lib/livelihoodLoom";

export const metadata: Metadata = {
  title: "Status Gates | Livelihood Loom",
  description:
    "Truthful readiness gates for provider proof, external action, safety review, and human-governed publication.",
  openGraph: {
    title: "Status Gates | Livelihood Loom",
    description:
      "Truthful readiness gates for provider proof, external action, safety review, and human-governed publication.",
    images: ["/livelihood-loom/hero-market-network.png"],
  },
};

export default function StatusGatesPage() {
  const gates = loadLivelihoodLoomStatusGates();

  return (
    <PublicShell>
      <section className="mx-auto max-w-4xl px-5 py-24 sm:px-8">
        <SectionHeader
          eyebrow="Safety and governance"
          title="Status gates"
          subtitle="Every gate is reported truthfully. Green means the evidence supports the claim; red or yellow means the next safe step is shown, not hidden."
          align="center"
        />
        <div className="mt-12 space-y-4">
          {gates.map((gate) => (
            <TruthGate key={gate.name} gate={gate} />
          ))}
        </div>
      </section>
    </PublicShell>
  );
}
