"use client";

import Link from "next/link";
import { OperatorCoherenceCockpit } from "@/components/operator-coherence/OperatorCoherenceCockpit";
import { MissionControlDeck } from "@/components/cockpit/MissionControlDeck";

export default function CockpitPage() {
  return (
    <div className="fixed inset-0 z-[60] space-y-4 overflow-y-auto bg-[#0A0E1A] p-3 md:bottom-0 md:left-[260px] md:right-0 md:top-12 md:z-[30] md:p-6">
      <div className="sticky top-0 z-10 -mx-1 hidden items-center justify-between bg-[#0A0E1A]/95 px-2 py-2 text-xs backdrop-blur max-md:flex">
        <Link href="/dashboard" className="font-semibold uppercase tracking-[0.16em] text-[#6E96D6]">
          Dharma Command
        </Link>
        <span className="text-[#6B7694]">Cockpit / Linear v1</span>
      </div>
      <MissionControlDeck />
      <OperatorCoherenceCockpit />
    </div>
  );
}
