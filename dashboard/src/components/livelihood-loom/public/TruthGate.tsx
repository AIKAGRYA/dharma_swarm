import { cn } from "@/lib/utils";
import { StatusBadge } from "./StatusBadge";
import type { LivelihoodLoomStatusGate } from "@/lib/livelihoodLoom";

export interface TruthGateProps {
  gate: LivelihoodLoomStatusGate;
  className?: string;
}

export function TruthGate({ gate, className }: TruthGateProps) {
  return (
    <div
      className={cn(
        "rounded-lg border border-[#181a20]/10 bg-white p-5",
        gate.complete ? "border-l-4 border-l-rokusho" : "border-l-4 border-l-kinpaku",
        className,
      )}
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h3 className="font-heading text-lg font-semibold text-[#181a20]">{gate.name}</h3>
          <p className="mt-1 break-all text-sm leading-6 text-[#4e5060]">{gate.detail}</p>
        </div>
        <StatusBadge status={gate.status} />
      </div>

      {gate.provider_green && (
        <p className="mt-4 text-sm text-rokusho">Provider proof is green.</p>
      )}

      {gate.next_safe_step && (
        <div className="mt-4 rounded-lg bg-[#f4f1ea] p-3">
          <p className="text-xs font-semibold uppercase text-[#60736b]">Next safe step</p>
          <p className="mt-1 text-sm text-[#181a20]">{gate.next_safe_step}</p>
        </div>
      )}

      {gate.required_for_completion && gate.required_for_completion.length > 0 && (
        <div className="mt-4">
          <p className="text-xs font-semibold uppercase text-[#60736b]">Required for completion</p>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-[#5d5f68]">
            {gate.required_for_completion.map((item, index) => (
              <li key={index} className="break-all">{item}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
