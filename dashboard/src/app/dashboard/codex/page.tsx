"use client";

import { motion } from "framer-motion";
import { Bot, Cable, Radio } from "lucide-react";
import { ChatInterface } from "@/components/chat/ChatInterface";
import { useRuntimeControlPlane } from "@/hooks/useRuntimeControlPlane";
import { findAdvertisedChatProfile } from "@/lib/chatProfiles";
import { colors } from "@/lib/theme";

const PROFILE_ID = "codex_operator";

export default function CodexLanePage() {
  const { chatStatus, snapshot } = useRuntimeControlPlane();
  const profile = findAdvertisedChatProfile(chatStatus, PROFILE_ID);
  const laneReady = profile?.available !== false;

  return (
    <div className="space-y-6">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
      >
        <div className="flex items-center gap-3">
          <Bot size={18} className="text-kinpaku" />
          <h1 className="font-heading text-3xl font-bold tracking-tight text-kinpaku">
            Codex Lane
          </h1>
        </div>
        <p className="mt-2 max-w-3xl text-sm text-sumi-600">
          Dedicated implementation lane for Codex-guided operator sessions on the same
          runtime contract as the live swarm.
        </p>
      </motion.div>

      <section className="grid gap-3 md:grid-cols-3">
        <LaneStat
          icon={<Radio size={14} />}
          label="Lane status"
          value={laneReady ? "live" : "blocked"}
          detail={profile?.status_note ?? "Waiting for the canonical chat contract."}
          accent={laneReady ? colors.rokusho : colors.bengara}
        />
        <LaneStat
          icon={<Cable size={14} />}
          label="Contract"
          value={snapshot.contractVersion}
          detail={snapshot.sessionFeedReady ? "session rail advertised" : "session rail missing"}
          accent={snapshot.sessionFeedReady ? colors.aozora : colors.kinpaku}
        />
        <LaneStat
          icon={<Bot size={14} />}
          label="Route"
          value={profile ? `${profile.provider} · ${profile.model}` : "not advertised"}
          detail="This page binds directly to codex_operator."
          accent={colors.kinpaku}
        />
      </section>

      <section className="overflow-hidden rounded-[28px] border border-sumi-700/40 bg-sumi-900/85">
        <div className="border-b border-sumi-700/30 px-5 py-4">
          <h2 className="font-heading text-lg text-torinoko">Live Session</h2>
          <p className="mt-1 text-sm text-sumi-500">
            Use this for a single focused Codex session. Use Command Post when you want
            explicit relay with Claude Code.
          </p>
        </div>
        <div style={{ height: "calc(100vh - 340px)", minHeight: 520 }}>
          <ChatInterface profileId={PROFILE_ID} allowProfileSwitch={false} />
        </div>
      </section>
    </div>
  );
}

function LaneStat({
  icon,
  label,
  value,
  detail,
  accent,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  detail: string;
  accent: string;
}) {
  return (
    <article className="rounded-2xl border border-sumi-700/40 bg-sumi-900/70 p-4">
      <div className="flex items-center gap-2 text-xs uppercase tracking-[0.14em] text-sumi-500">
        <span style={{ color: accent }}>{icon}</span>
        <span>{label}</span>
      </div>
      <div className="mt-3 text-sm font-medium" style={{ color: accent }}>
        {value}
      </div>
      <p className="mt-2 text-xs text-sumi-500">{detail}</p>
    </article>
  );
}
