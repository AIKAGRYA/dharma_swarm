import { cn } from "@/lib/utils";

export interface StatCardProps {
  label: string;
  value: string;
  detail?: string;
  variant?: "light" | "dark";
  className?: string;
}

export function StatCard({ label, value, detail, variant = "light", className }: StatCardProps) {
  const isDark = variant === "dark";

  return (
    <article
      className={cn(
        "rounded-lg border p-5",
        isDark
          ? "border-white/10 bg-white/[0.05] text-white"
          : "border-[#181a20]/10 bg-white text-[#181a20]",
        className,
      )}
    >
      <p className={cn("text-xs font-semibold uppercase", isDark ? "text-[#d4a855]" : "text-[#60736b]")}>
        {label}
      </p>
      <p className="mt-2 font-heading text-4xl font-semibold">{value}</p>
      {detail && (
        <p className={cn("mt-2 text-sm leading-6", isDark ? "text-white/58" : "text-[#5d5f68]")}>{detail}</p>
      )}
    </article>
  );
}
