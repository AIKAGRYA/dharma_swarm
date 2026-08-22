"use client";

import { AnimatePresence } from "framer-motion";
import { Header } from "@/components/layout/Header";
import { OperatorMicrographics } from "@/components/layout/OperatorMicrographics";
import { ChatPanel } from "@/components/chat/ChatPanel";
import { BackendStatus } from "@/components/ui/ErrorBanner";
import { KeyboardNav } from "@/components/ui/KeyboardNav";
import { useChatWorkspace } from "@/hooks/useChatWorkspace";

/**
 * Dashboard layout wrapper.
 * Renders breadcrumb header, page content, and optional split chat panel.
 */
export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { panelOpen, togglePanel, closePanel } = useChatWorkspace();

  return (
    <div className="flex min-h-screen min-w-0 flex-col">
      <KeyboardNav />
      <Header onToggleChat={() => togglePanel()} chatOpen={panelOpen} />
      <div className="flex min-w-0 flex-1">
        <div
          className={`min-w-0 flex-1 p-3 transition-all sm:p-6 ${panelOpen ? "pr-3" : ""}`}
        >
          <div className="flex min-w-0 flex-col gap-6">
            <BackendStatus />
            <OperatorMicrographics />
            {children}
          </div>
        </div>
      </div>

      {/* Half-screen split chat panel */}
      <AnimatePresence>
        {panelOpen && <ChatPanel onClose={closePanel} />}
      </AnimatePresence>
    </div>
  );
}
