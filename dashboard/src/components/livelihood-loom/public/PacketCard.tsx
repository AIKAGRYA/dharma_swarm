import Link from "next/link";
import { ArrowRight, FileText } from "lucide-react";
import { cn } from "@/lib/utils";
import type { LivelihoodLoomPacketDetail } from "@/lib/livelihoodLoom";

export interface PacketCardProps {
  packet: LivelihoodLoomPacketDetail;
  className?: string;
}

export function PacketCard({ packet, className }: PacketCardProps) {
  return (
    <article
      className={cn(
        "rounded-lg border border-[#181a20]/10 bg-white p-5 transition hover:border-[#181a20]/20 hover:shadow-lg",
        className,
      )}
    >
      <div className="flex items-start gap-4">
        <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-[#0d615f]/10 text-[#0d615f]">
          <FileText size={20} aria-hidden="true" />
        </span>
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase text-[#60736b]">Enablement packet</p>
          <h3 className="mt-1 font-heading text-xl font-semibold text-[#181a20]">{packet.packet_id}</h3>
          {packet.target_wedge && <p className="mt-1 text-sm text-[#5d5f68]">{packet.target_wedge}</p>}
          {packet.beneficiary && (
            <p className="mt-3 text-sm leading-6 text-[#4e5060]">{packet.beneficiary}</p>
          )}
        </div>
      </div>
      <Link
        href={`/livelihood-loom/packets/${packet.packet_id}`}
        className="mt-5 inline-flex items-center gap-2 text-sm font-semibold text-[#0d615f] transition hover:text-[#181a20]"
      >
        Open packet
        <ArrowRight size={16} />
      </Link>
    </article>
  );
}
