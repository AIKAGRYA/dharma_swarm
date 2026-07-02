import { cn } from "@/lib/utils";
import { PublicNav } from "./PublicNav";
import { PublicFooter } from "./PublicFooter";

export interface PublicShellProps {
  children: React.ReactNode;
  hero?: boolean;
  className?: string;
}

export function PublicShell({ children, hero = false, className }: PublicShellProps) {
  return (
    <div className="flex min-h-screen flex-col bg-[#f4f1ea] text-[#181a20]">
      <PublicNav />
      <main className={cn("flex-1", !hero && "pt-20", className)}>{children}</main>
      <PublicFooter />
    </div>
  );
}
