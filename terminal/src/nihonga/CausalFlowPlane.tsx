import React from "react";
import {Box, Text} from "ink";

import {THEME} from "../theme";
import type {CanonicalExecutionEvent} from "../types";

export function executionPhasePresentation(event: CanonicalExecutionEvent): {glyph: string; word: string; color: string} {
  if (event.kind === "error" || event.phase === "failed") return {glyph: "✖", word: "FAILED", color: THEME.vermilion};
  // A terminal completion is executor-owned success, not independent
  // verification. Reserve ✓ for a future verifier-owned projection.
  if (event.phase === "complete") return {glyph: "■", word: "SUCCEEDED", color: THEME.pine};
  if (event.phase === "running") return {glyph: "▶", word: "RUNNING", color: THEME.crest};
  return {glyph: "○", word: "QUEUED", color: THEME.stone};
}

function eventRowCost(): number {
  // Phase and content deliberately occupy separate rows. The semantic word
  // must survive narrow-panel truncation alongside its glyph and colour.
  return 2;
}

// Panorama owns six rows above the workspace and five below it. The Causal
// panel then owns two border rows, one panel-title row, and three fixed feed
// rows (header, ma, retained-count). What remains is the actual event budget.
export function causalEventRowBudget(terminalHeight: number): number {
  return Math.max(terminalHeight - 17, 1);
}

export function visibleCausalEvents(
  events: CanonicalExecutionEvent[],
  rowBudget: number,
): CanonicalExecutionEvent[] {
  const selected: CanonicalExecutionEvent[] = [];
  let remaining = Math.max(rowBudget, 1);
  for (let index = events.length - 1; index >= 0; index -= 1) {
    const event = events[index];
    if (!event) continue;
    const cost = eventRowCost();
    if (selected.length > 0 && cost > remaining) break;
    selected.push(event);
    remaining -= cost;
    if (remaining <= 0) break;
  }
  return selected.reverse();
}

export function CausalFlowPlane({events, rowBudget}: {events: CanonicalExecutionEvent[]; rowBudget: number}): React.ReactElement {
  const visible = visibleCausalEvents(events, rowBudget);
  return (
    <Box flexDirection="column" flexGrow={1} overflow="hidden">
      <Box flexShrink={0}><Text color={THEME.stone} wrap="truncate-end">owner-correlated feed</Text></Box>
      <Box flexShrink={0}><Text color={THEME.ink}> </Text></Box>
      {visible.length === 0 ? (
        <>
          <Text color={THEME.stone}>? no owner-correlated events yet</Text>
          <Text color={THEME.stone}>  ◇ configured ≠ contacted</Text>
          <Text color={THEME.stone}>  ■ succeeded ≠ ✓ verified</Text>
        </>
      ) : visible.map((event) => {
        const presentation = executionPhasePresentation(event);
        return (
          <Box key={event.id} flexDirection="column" flexShrink={0}>
            <Text wrap="truncate-end">
              <Text color={presentation.color}>{presentation.glyph} {presentation.word}</Text>
            </Text>
            <Text color={THEME.stone} wrap="truncate-end">
              {event.title}{event.summary ? `—${event.summary}` : ""}
            </Text>
          </Box>
        );
      })}
      <Box flexGrow={1} />
      <Box flexShrink={0}><Text color={THEME.stone} wrap="truncate-end">NO VERDICT · {events.length} evt</Text></Box>
    </Box>
  );
}
