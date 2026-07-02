import { cn } from "@/lib/utils";

export interface SectionHeaderProps {
  eyebrow?: string;
  title: string;
  subtitle?: string;
  align?: "left" | "center";
  dark?: boolean;
  className?: string;
}

export function SectionHeader({
  eyebrow,
  title,
  subtitle,
  align = "left",
  dark = false,
  className,
}: SectionHeaderProps) {
  const textColor = dark ? "text-white" : "text-[#181a20]";
  const mutedColor = dark ? "text-white/68" : "text-[#4e5060]";
  const eyebrowColor = dark ? "text-[#4fd1d9]" : "text-[#b15f94]";

  return (
    <div className={cn(align === "center" && "text-center", className)}>
      {eyebrow && (
        <p className={cn("text-sm font-semibold uppercase", eyebrowColor)}>{eyebrow}</p>
      )}
      <h2
        className={cn(
          "mt-3 font-heading text-3xl font-semibold leading-tight sm:text-4xl lg:text-5xl",
          textColor,
        )}
      >
        {title}
      </h2>
      {subtitle && (
        <p className={cn("mt-5 max-w-3xl text-lg leading-8", mutedColor, align === "center" && "mx-auto")}>
          {subtitle}
        </p>
      )}
    </div>
  );
}
