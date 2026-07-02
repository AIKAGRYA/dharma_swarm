import Link from "next/link";
import { ArrowRight, FileJson, LayoutDashboard } from "lucide-react";
import { cn } from "@/lib/utils";

export interface ProofLinkProps {
  href: string;
  label?: string;
  variant?: "api" | "desk" | "primary" | "secondary";
  external?: boolean;
  className?: string;
}

export function ProofLink({ href, label, variant = "api", external, className }: ProofLinkProps) {
  const isPrimary = variant === "api" || variant === "primary";

  const classes = cn(
    "inline-flex items-center gap-2 rounded-lg px-4 py-3 text-sm font-semibold transition",
    isPrimary
      ? "bg-[#181a20] text-white hover:bg-[#2c303a]"
      : "border border-[#181a20]/15 text-[#181a20] hover:bg-[#181a20]/5",
    className,
  );

  const icon = isPrimary ? <FileJson size={16} aria-hidden="true" /> : <LayoutDashboard size={16} aria-hidden="true" />;
  const text = label ?? (isPrimary ? "View JSON proof" : "Internal desk");
  const content = (
    <>
      {icon}
      {text}
      <ArrowRight size={16} />
    </>
  );

  if (external || href.startsWith("http")) {
    return (
      <a href={href} target="_blank" rel="noopener noreferrer" className={classes}>
        {content}
      </a>
    );
  }

  return <Link href={href} className={classes}>{content}</Link>;
}
