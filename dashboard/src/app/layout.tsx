import type { Metadata } from "next";
import { Inter, Geist_Mono } from "next/font/google";
import { Providers } from "./providers";
import { Sidebar } from "@/components/layout/Sidebar";
import { ChatOverlayWrapper } from "@/components/chat/ChatOverlayWrapper";
import "./globals.css";

// ---------------------------------------------------------------------------
// Fonts — Phase 2 font swap per command-plane-design-lock
// Inter for prose; Geist Mono for protagonist numerals + ALLCAPS chrome.
// Commit Mono is honored first in the CSS stack so an operator who
// installs it locally gets the locked aesthetic; Geist Mono is the
// always-loaded fallback (Google Fonts, ships via next/font).
// ---------------------------------------------------------------------------

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

const geistMono = Geist_Mono({
  subsets: ["latin"],
  variable: "--font-geist-mono",
  display: "swap",
});

// ---------------------------------------------------------------------------
// Metadata
// ---------------------------------------------------------------------------

export const metadata: Metadata = {
  title: "DHARMA COMMAND",
  description: "Operator command plane for dharma_swarm — verifiable agent operations, MRV evidence, and welfare-tracked coordination.",
};

// ---------------------------------------------------------------------------
// Root layout
// ---------------------------------------------------------------------------

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${inter.variable} ${geistMono.variable}`}>
      <body className="min-h-screen bg-sumi-950 font-body text-torinoko antialiased">
        <Providers>
          <div className="flex min-h-screen">
            <Sidebar />
            <main className="ml-[260px] flex-1">
              {children}
            </main>
          </div>

          {/* Floating chat overlay */}
          <ChatOverlayWrapper />
        </Providers>
      </body>
    </html>
  );
}
