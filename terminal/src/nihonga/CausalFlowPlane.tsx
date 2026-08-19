import React from "react";
import {Box, Text} from "ink";

import {THEME} from "../theme";
import type {CanonicalExecutionEvent} from "../types";

function eventGlyph(event: CanonicalExecutionEvent): {glyph: string; color: string} {
  if (event.kind === "error" || event.phase === "failed") return {glyph: "✖", color: THEME.vermilion};
  if (event.phase === "complete") return {glyph: "✓", color: THEME.moss};
  if (event.phase === "running") return {glyph: "▶", color: THEME.crest};
  return {glyph: "○", color: THEME.stone};
}

function eventRowCost(event: CanonicalExecutionEvent): number {
  return event.summary ? 2 : 1;
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
    const cost = eventRowCost(event);
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
      <Box flexShrink={0}><Text color={THEME.stone} wrap="truncate-end">correlated events · gaps stay visible</Text></Box>
      <Box flexShrink={0}><Text color={THEME.ink}> </Text></Box>
      {visible.length === 0 ? (
        <>
          <Text color={THEME.stone}>○ no correlated events yet</Text>
          <Text color={THEME.ink}>  configured is not contacted</Text>
          <Text color={THEME.ink}>  returned is not verified</Text>
        </>
      ) : visible.map((event) => {
        const presentation = eventGlyph(event);
        return (
          <Box key={event.id} flexDirection="column" flexShrink={0}>
            <Text wrap="truncate-end">
              <Text color={presentation.color}>{presentation.glyph} </Text>
              <Text color={THEME.mist}>{event.title}</Text>
            </Text>
            {event.summary ? <Text color={THEME.stone} wrap="truncate-end">  {event.summary}</Text> : null}
          </Box>
        );
      })}
      <Box flexGrow={1} />
      <Box flexShrink={0}><Text color={THEME.stone} wrap="truncate-end">{events.length} canonical events retained</Text></Box>
    </Box>
  );
}
