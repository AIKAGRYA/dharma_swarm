import React from "react";
import {Box, Text} from "ink";

import {ownerProjectionModality} from "../nihonga/projectionModality.ts";
import type {BridgeStatus, TranscriptLine} from "../types";
import {THEME} from "../theme";

type AgentRouteCard = {
  intent: string;
  provider: string;
  modelAlias: string;
  effort: string;
  role: string;
};

type OpenClawSummary = {
  present: string;
  readable: string;
  agents: string;
  providers: string;
};

type Props = {
  title: string;
  lines: TranscriptLine[];
  selectedRouteIndex?: number;
  authorityObserved: boolean;
  bridgeStatus: BridgeStatus;
  compact?: boolean;
};

function parseAgentRouteCards(lines: TranscriptLine[]): AgentRouteCard[] {
  return lines
    .map((line) => line.text.trim())
    .filter((line) => line.startsWith("- "))
    .map((line) => line.replace(/^- /, ""))
    .map((line) => {
      const match = line.match(/^(.*?) -> (.*?):(.*?) \| effort (.*?) \| role (.*?)$/);
      if (!match) {
        return null;
      }
      return {
        intent: match[1].trim(),
        provider: match[2].trim(),
        modelAlias: match[3].trim(),
        effort: match[4].trim(),
        role: match[5].trim(),
      };
    })
    .filter((card): card is AgentRouteCard => Boolean(card));
}

function parseOpenClawSummary(lines: TranscriptLine[]): OpenClawSummary {
  const lineValue = (label: string): string => {
    const match = lines.find((line) => line.text.startsWith(`${label}: `));
    return match ? match.text.slice(label.length + 2).trim() : "n/a";
  };
  return {
    present: lineValue("Present"),
    readable: lineValue("Readable"),
    agents: lineValue("Agents"),
    providers: lineValue("Providers"),
  };
}

function clampIndex(index: number, count: number): number {
  if (count <= 0) {
    return 0;
  }
  return Math.min(Math.max(index, 0), count - 1);
}

export function AgentsPane({title, lines, selectedRouteIndex = 0, authorityObserved, bridgeStatus, compact = false}: Props): React.ReactElement {
  const routes = parseAgentRouteCards(lines);
  const openclaw = parseOpenClawSummary(lines);
  const activeIndex = clampIndex(selectedRouteIndex, routes.length);
  const selected = routes[activeIndex];
  const retained = routes.length > 0 || Object.values(openclaw).some((value) => value !== "n/a");
  const modality = ownerProjectionModality({
    bridgeStatus,
    authorityObserved,
    hasRetainedProjection: retained,
  });
  const modalityLabel = modality === "observed"
    ? "◉ OBSERVED · route intents · configured ≠ contacted"
    : modality === "stale"
      ? "~ STALE · retained route projection · no liveness implied"
      : "?[?] UNKNOWN · agent-route owner projection absent";

  return (
    <Box flexGrow={1} borderStyle="round" borderColor={THEME.ridge} paddingX={1} flexDirection="column">
      <Text color={THEME.wave} bold>{title}</Text>
      <Text color={THEME.stone}>
        {modalityLabel}{compact ? "" : " · j/k select"}
      </Text>
      <Box marginTop={1} flexDirection={compact ? "column" : "row"}>
        <Box width={compact ? undefined : "35%"} flexDirection="column" paddingX={1}>
          <Text color={THEME.mist} bold>Routes</Text>
          <Text color={THEME.stone}>typed routing intents</Text>
          {routes.length === 0 ? (
            <Text color={THEME.stone}>
              {modality === "observed" ? "No routes in the observed projection." : "No current owner projection."}
            </Text>
          ) : (
            routes.slice(0, 12).map((route, index) => {
              const active = index === activeIndex;
              return (
                <Box key={`${route.intent}-${route.provider}-${route.modelAlias}`} flexDirection="column" marginTop={1}>
                  <Text color={active ? THEME.wave : THEME.foam} bold={active} backgroundColor={active ? THEME.harbor : undefined}>
                    {active ? "◆ " : "• "}
                    {route.intent}
                  </Text>
                  <Text color={active ? THEME.foam : THEME.stone}>
                    {"  "}{route.provider}:{route.modelAlias} | {route.effort}
                  </Text>
                </Box>
              );
            })
          )}
        </Box>
        <Box
          width={compact ? undefined : "65%"}
          marginLeft={compact ? 0 : 1}
          marginTop={compact ? 1 : 0}
          flexDirection="column"
          paddingX={1}
        >
          <Text color={THEME.mist} bold>Route brief</Text>
          <Text color={THEME.stone}>selected route plus OpenClaw envelope</Text>
          {!selected ? (
            <Text color={THEME.stone}>No selected route.</Text>
          ) : (
            <>
              <Text color={THEME.foam} bold>{selected.intent}</Text>
              <Text color={THEME.stone}>{selected.provider}:{selected.modelAlias} | effort {selected.effort}</Text>
              <Text color={THEME.stone}>role {selected.role}</Text>
            </>
          )}
          <Text color={THEME.mist} bold>OpenClaw</Text>
          {modality === "observed" ? (
            <>
              <Text color={THEME.stone}>present {openclaw.present} | readable {openclaw.readable}</Text>
              <Text color={THEME.stone}>agents {openclaw.agents} | providers {openclaw.providers}</Text>
            </>
          ) : modality === "stale" && retained ? (
            <Text color={THEME.stone}>retained projection · do not infer current state</Text>
          ) : (
            <Text color={THEME.stone}>owner projection absent</Text>
          )}
        </Box>
      </Box>
    </Box>
  );
}
