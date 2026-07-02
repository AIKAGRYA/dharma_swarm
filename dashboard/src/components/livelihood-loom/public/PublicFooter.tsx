import Link from "next/link";
import { Handshake } from "lucide-react";

const footerLinks = [
  { label: "Thesis", href: "/livelihood-loom/thesis" },
  { label: "Market Map", href: "/livelihood-loom/market-map" },
  { label: "Proof Packet", href: "/livelihood-loom/proof-packet" },
  { label: "Investor Brief", href: "/livelihood-loom/investor-brief" },
  { label: "Safety", href: "/livelihood-loom/safety-governance" },
  { label: "Data Room", href: "/livelihood-loom/data-room" },
  { label: "Internal desk", href: "/dashboard/livelihood-loom" },
];

export function PublicFooter() {
  return (
    <footer className="border-t border-[#181a20]/10 bg-[#f4f1ea] px-5 py-12 sm:px-8">
      <div className="mx-auto flex max-w-7xl flex-col gap-8">
        <div className="flex flex-col gap-6 sm:flex-row sm:items-start sm:justify-between">
          <Link href="/livelihood-loom" className="flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-lg border border-[#0d615f]/30 bg-[#0d615f]/10 text-[#0d615f]">
              <Handshake size={20} aria-hidden="true" />
            </span>
            <span className="font-heading text-lg font-semibold text-[#181a20]">Livelihood Loom</span>
          </Link>
          <div className="grid grid-cols-2 gap-x-8 gap-y-3 text-sm text-[#5d5f68] sm:grid-cols-3">
            {footerLinks.map((link) => (
              <Link key={link.href} href={link.href} className="transition hover:text-[#181a20]">
                {link.label}
              </Link>
            ))}
          </div>
        </div>
        <p className="max-w-3xl text-xs leading-5 text-[#5d5f68]">
          Local draft site. Not a securities offering. Public deployment, external outreach, and fundraising claims
          require explicit human approval and acted receipts. All source data is local to this repository.
        </p>
      </div>
    </footer>
  );
}
