import {projectActivityEntries, projectPaneLines} from "./executionLog";
import type {ActivityEntry, CanonicalExecutionEvent, CanonicalExecutionEventKind, TranscriptLine} from "./types";

type ExecutionViews = {
  thinking: TranscriptLine[];
  tools: TranscriptLine[];
  timeline: TranscriptLine[];
  activity: ActivityEntry[];
};

// These are the kinds consumed by executionLog's pane/activity projections.
// In particular, command replacements can change session_end suppression in
// activity; assistant narration and user prompts cannot affect these views.
const thinkingKinds = new Set<CanonicalExecutionEventKind>(["thinking", "command", "error"]);
const toolsKinds = new Set<CanonicalExecutionEventKind>(["tool_call", "tool_result", "approval", "error"]);
const timelineKinds = new Set<CanonicalExecutionEventKind>(["task", "status", "command", "error"]);
const activityKinds = new Set<CanonicalExecutionEventKind>([
  "thinking", "tool_call", "tool_result", "approval", "task", "command", "status", "error",
]);
const viewsByEvents = new WeakMap<CanonicalExecutionEvent[], ExecutionViews>();

function sameInputs(
  previous: CanonicalExecutionEvent[],
  next: CanonicalExecutionEvent[],
  kinds: ReadonlySet<CanonicalExecutionEventKind>,
): boolean {
  let p = 0;
  let n = 0;
  while (true) {
    while (p < previous.length && !kinds.has(previous[p].kind)) p++;
    while (n < next.length && !kinds.has(next[n].kind)) n++;
    if (p === previous.length || n === next.length) {
      return p === previous.length && n === next.length;
    }
    if (previous[p] !== next[n]) return false;
    p++;
    n++;
  }
}

/** Reuse only outputs derived here from immutable canonical event arrays.
 * Tab and activity reducers can write independent content, so their current
 * display arrays must never seed this cache. Weak keys retain no old logs.
 */
export function projectExecutionViews(
  previousEvents: CanonicalExecutionEvent[],
  events: CanonicalExecutionEvent[],
): ExecutionViews {
  const cached = viewsByEvents.get(events);
  if (cached) return cached;
  const previous = viewsByEvents.get(previousEvents);
  const views = {
    thinking: previous && sameInputs(previousEvents, events, thinkingKinds)
      ? previous.thinking : projectPaneLines("thinking", events),
    tools: previous && sameInputs(previousEvents, events, toolsKinds)
      ? previous.tools : projectPaneLines("tools", events),
    timeline: previous && sameInputs(previousEvents, events, timelineKinds)
      ? previous.timeline : projectPaneLines("timeline", events),
    activity: previous && sameInputs(previousEvents, events, activityKinds)
      ? previous.activity : projectActivityEntries(events),
  };
  viewsByEvents.set(events, views);
  return views;
}
