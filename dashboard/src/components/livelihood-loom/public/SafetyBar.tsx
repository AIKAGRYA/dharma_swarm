import { cn } from "@/lib/utils";

export interface SafetyBarProps {
  allowed: number;
  needs_review: number;
  blocked: number;
  total?: number;
  className?: string;
}

export function SafetyBar({ allowed, needs_review, blocked, total, className }: SafetyBarProps) {
  const computedTotal = total ?? allowed + needs_review + blocked;
  const pct = (value: number) => (computedTotal > 0 ? `${(value / computedTotal) * 100}%` : "0%");

  return (
    <div className={cn("space-y-3", className)}>
      <div className="flex h-3 overflow-hidden rounded-full bg-[#e8e4da]">
        <div className="bg-rokusho transition-all" style={{ width: pct(allowed) }} />
        <div className="bg-kinpaku transition-all" style={{ width: pct(needs_review) }} />
        <div className="bg-bengara transition-all" style={{ width: pct(blocked) }} />
      </div>
      <div className="flex flex-wrap gap-4 text-xs font-semibold">
        <span className="text-rokusho">{allowed} allowed</span>
        <span className="text-kinpaku">{needs_review} needs review</span>
        <span className="text-bengara">{blocked} blocked</span>
        {computedTotal > 0 && <span className="text-[#60736b]">{computedTotal} total</span>}
      </div>
    </div>
  );
}
