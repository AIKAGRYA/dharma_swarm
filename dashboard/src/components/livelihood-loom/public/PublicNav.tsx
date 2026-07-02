"use client";

import { useState } from "react";
import Link from "next/link";
import { ArrowRight, Handshake, Menu, X } from "lucide-react";

const links = [
  { label: "Thesis", href: "/livelihood-loom/thesis" },
  { label: "Market Map", href: "/livelihood-loom/market-map" },
  { label: "Proof Packet", href: "/livelihood-loom/proof-packet" },
  { label: "Investor Brief", href: "/livelihood-loom/investor-brief" },
  { label: "Safety/Governance", href: "/livelihood-loom/safety-governance" },
  { label: "Data Room", href: "/livelihood-loom/data-room" },
];

export function PublicNav() {
  const [open, setOpen] = useState(false);

  return (
    <header className="fixed inset-x-0 top-0 z-50 border-b border-[#181a20]/10 bg-[#f4f1ea]/95 backdrop-blur-md">
      <nav
        className="mx-auto flex max-w-7xl items-center justify-between px-5 py-4 sm:px-8"
        aria-label="Livelihood Loom public site"
      >
        <Link href="/livelihood-loom" className="flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-lg border border-[#0d615f]/30 bg-[#0d615f]/10 text-[#0d615f]">
            <Handshake size={20} aria-hidden="true" />
          </span>
          <span className="font-heading text-base font-semibold text-[#181a20]">Livelihood Loom</span>
        </Link>

        <div className="hidden items-center gap-6 text-sm text-[#4e5060] md:flex">
          {links.map((link) => (
            <Link key={link.href} href={link.href} className="transition hover:text-[#181a20]">
              {link.label}
            </Link>
          ))}
          <Link
            href="/dashboard/livelihood-loom"
            className="inline-flex items-center gap-1.5 rounded-lg bg-[#181a20] px-4 py-2 text-sm font-semibold text-white transition hover:bg-[#2c303a]"
          >
            Internal desk
            <ArrowRight size={14} />
          </Link>
        </div>

        <button
          type="button"
          className="rounded-md p-2 text-[#181a20] md:hidden"
          onClick={() => setOpen((prev) => !prev)}
          aria-expanded={open}
          aria-controls="mobile-menu"
          aria-label={open ? "Close menu" : "Open menu"}
        >
          {open ? <X size={24} /> : <Menu size={24} />}
        </button>
      </nav>

      {open && (
        <div id="mobile-menu" className="border-t border-[#181a20]/10 bg-[#f4f1ea] px-5 py-4 md:hidden">
          <div className="flex flex-col gap-1 text-sm">
            {links.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className="rounded-md py-2 text-[#4e5060] transition hover:bg-[#181a20]/5 hover:text-[#181a20]"
                onClick={() => setOpen(false)}
              >
                {link.label}
              </Link>
            ))}
            <Link
              href="/dashboard/livelihood-loom"
              className="mt-2 inline-flex items-center gap-2 rounded-lg bg-[#181a20] px-4 py-3 text-sm font-semibold text-white"
              onClick={() => setOpen(false)}
            >
              Internal desk
              <ArrowRight size={16} />
            </Link>
          </div>
        </div>
      )}
    </header>
  );
}
