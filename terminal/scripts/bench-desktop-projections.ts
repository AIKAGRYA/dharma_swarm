import {readFileSync, writeFileSync, mkdirSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {hostname, cpus, platform, arch, homedir} from 'node:os';
import {execFileSync} from 'node:child_process';
import {initialState, reduceApp as optimizedReduceApp} from '../src/state.ts';
import {canonicalEventsFromBridgeEvent, userPromptExecutionEvent, mergeExecutionEvents, projectChatTraceLines, projectPaneLines, projectActivityEntries} from '../src/executionLog.ts';
import {routeLabel} from '../src/routePolicy.ts';
import {buildBridgeTabs} from '../src/protocol.ts';
import type {AppState, AppAction, CanonicalExecutionEvent} from '../src/types.ts';

const root = new URL('../../', import.meta.url).pathname.replace(/\/$/, '');
const outputDirectory = `${homedir()}/.dharma/helm-desktop-build/perf`;
mkdirSync(outputDirectory, {recursive: true, mode: 0o700});
const output = `${outputDirectory}/reducer_projection_implemented.json`;
const sampleCount = 1200;
const warmupCount = 200;
const digest = (path: string) => createHash('sha256').update(readFileSync(path)).digest('hex');
const inputFiles = ['terminal/src/state.ts', 'terminal/src/executionLog.ts', 'terminal/src/executionProjectionMemo.ts'];
const sourceHashesBefore = Object.fromEntries(inputFiles.map(path => [path, digest(`${root}/${path}`)]));
// Reference is the pre-memo ingestion algorithm, using the same current pure
// projections. Compare the shipped reducer, not a second experimental candidate.
const candidateReduce = optimizedReduceApp;
function reduceApp(state: AppState, action: AppAction): AppState {
  if (action.type !== 'execution.events.ingest') return optimizedReduceApp(state, action);
  const executionEventLog = mergeExecutionEvents(state.executionEventLog, action.events);
  const chatTraceLines = projectChatTraceLines(executionEventLog, {
    expanded: state.chatTraceExpanded, showRaw: state.activityFeed.showRaw, routeLabel: routeLabel(state.routePolicy),
  });
  const thinking = projectPaneLines('thinking', executionEventLog);
  const tools = projectPaneLines('tools', executionEventLog);
  const timeline = projectPaneLines('timeline', executionEventLog);
  return {...state, executionEventLog, chatTraceLines,
    activityFeed: {...state.activityFeed, entries: projectActivityEntries(executionEventLog)},
    tabs: state.tabs.map(tab => tab.id === 'thinking' ? {...tab, lines: thinking}
      : tab.id === 'tools' ? {...tab, lines: tools} : tab.id === 'timeline' ? {...tab, lines: timeline} : tab),
  };
}

function makeEvents(turnCount: number): CanonicalExecutionEvent[] {
  const events: CanonicalExecutionEvent[] = [];
  const baseMs = Date.parse('2026-09-10T00:00:00Z');
  for (let t = 0; t < turnCount; t++) {
    const stamp = (step: number) => new Date(baseMs + t * 60000 + step * 100).toISOString();
    const request = `bench-request-${t}`;
    const session = `bench-session-${t}`;
    const wire = (event: Record<string, unknown>, step: number) => {
      events.push(...canonicalEventsFromBridgeEvent({request_id: request, session_id: session, created_at: stamp(step), ...event}, 'local:fixture-model'));
    };
    events.push(userPromptExecutionEvent(`Inspect the bounded project ${t} and summarize the relevant result`, stamp(0)));
    wire({type: 'session.ack', provider: 'local', model: 'fixture-model'}, 1);
    wire({type: 'session_start', provider: 'local', model: 'fixture-model'}, 2);
    wire({type: 'thinking_complete', content: `Inspecting changed files for project ${t}; use the existing owner interfaces.`}, 3);
    wire({type: 'tool_call_complete', tool_name: 'exec_command', tool_call_id: `bench-tool-${t}`, arguments: '{"cmd":"git status --short"}'}, 4);
    wire({type: 'tool_result', tool_name: 'exec_command', tool_call_id: `bench-tool-${t}`, success: true, content: 'M terminal/src/state.ts\nA terminal/tests/reducer.test.ts'}, 5);
    for (let d = 0; d < 12; d++) {
      wire({type: 'text_delta', content: `Project ${t}: ` + 'The bounded operation keeps the same owner and preserves session state. '.repeat(d + 1)}, 6 + d);
    }
    wire({type: 'text_complete', content: `Project ${t}: finished the local check.\nState remains owned by the bridge.\nNo remote operation ran.`}, 18);
    wire({type: 'session_end', success: true}, 19);
  }
  return events;
}

function percentile(values: number[], p: number): number {
  const sorted = values.toSorted((a, b) => a - b);
  return sorted[Math.max(0, Math.ceil(sorted.length * p) - 1)];
}
function summarize(values: number[]) {
  return {count: values.length, p50_ms: percentile(values, .5), p95_ms: percentile(values, .95), p99_ms: percentile(values, .99), max_ms: Math.max(...values), mean_ms: values.reduce((a, b) => a + b, 0) / values.length};
}

const events = makeEvents(400);
const readyState = {...initialState, tabs: [...initialState.tabs, ...buildBridgeTabs().filter(tab => !initialState.tabs.some(existing => existing.id === tab.id))]};
const normalize = (state: AppState) => JSON.stringify({
  ...state,
  chatTraceLines: state.chatTraceLines.map(({id: _id, ...line}) => line),
  tabs: state.tabs.map(tab => ({...tab, lines: tab.lines.map(({id: _id, ...line}) => line)})),
});

function seed(retained: number, expanded: boolean, raw = false): AppState {
  const state = {...readyState, chatTraceExpanded: expanded, activityFeed: {...readyState.activityFeed, showRaw: raw}};
  return reduceApp(state, {type: 'execution.events.ingest', events: events.slice(0, retained)});
}

function runWorkload(name: string, retained: number, expanded: boolean, raw = false) {
  const actions: AppAction[] = events.slice(retained, retained + warmupCount + sampleCount).map(event => ({type: 'execution.events.ingest', events: [event]}));
  const timings: Record<string, number[]> = {baseline: [], candidate: []};
  let baseline = seed(retained, expanded, raw);
  let candidate = baseline;
  let semanticChecks = 0;
  let preservedTabs = 0;
  let preservedActivity = 0;
  const begin = performance.now();
  for (let i = 0; i < actions.length; i++) {
    // Alternate order so the candidate does not always inherit the warmer CPU.
    for (const variant of i % 2 === 0 ? ['baseline', 'candidate'] : ['candidate', 'baseline']) {
      const before = candidate;
      const start = performance.now();
      if (variant === 'baseline') baseline = reduceApp(baseline, actions[i]);
      else candidate = candidateReduce(candidate, actions[i]);
      const elapsed = performance.now() - start;
      if (i >= warmupCount) timings[variant].push(elapsed);
      if (variant === 'candidate') {
        preservedTabs += Number(candidate.tabs === before.tabs);
        preservedActivity += Number(candidate.activityFeed === before.activityFeed);
      }
    }
    if (i % 20 === 0 || i === actions.length - 1) {
      if (normalize(baseline) !== normalize(candidate)) throw new Error(`semantic mismatch: ${name} action ${i}`);
      semanticChecks++;
    }
  }
  const row = {name, retained_seed: retained, retained_end: baseline.executionEventLog.length, expanded, raw, warmupCount, sampleCount, action_kind: 'one canonical event per ingest; mixed 20-event turns; 60% assistant text deltas', semanticChecks, preservedTabs, preservedActivity, baseline: summarize(timings.baseline), candidate: summarize(timings.candidate), raw_ms: timings, wall_ms: performance.now() - begin};
  return row;
}

function edgeCaseParity() {
  const results: string[] = [];
  const check = (name: string, seedEvents: CanonicalExecutionEvent[], actions: AppAction[]) => {
    let baseline = reduceApp(readyState, {type: 'execution.events.ingest', events: seedEvents});
    let candidate = candidateReduce(readyState, {type: 'execution.events.ingest', events: seedEvents});
    for (let i = 0; i < actions.length; i++) {
      baseline = reduceApp(baseline, actions[i]);
      candidate = candidateReduce(candidate, actions[i]);
      if (normalize(baseline) !== normalize(candidate)) throw new Error(`edge parity mismatch: ${name} action ${i}`);
    }
    results.push(`${name}: ${actions.length} transitions passed`);
  };
  const ingest = (event: CanonicalExecutionEvent): AppAction => ({type: 'execution.events.ingest', events: [event]});
  const thinking = {...events.find(event => event.kind === 'thinking')!, id: 'fixture-replaceable-thinking'};
  const narration = {...events.find(event => event.kind === 'assistant_text')!, id: 'fixture-narration-1'};
  check('first-ingest', [], [ingest(events[0]), ingest(narration)]);
  check('same-id-replacement-and-kind-transition', [events[0], thinking], [
    ingest({...thinking, content: 'revised reasoning', phase: 'running'}),
    ingest({...thinking, kind: 'error', title: 'revised failure', phase: 'failed'}),
    ingest({...thinking, kind: 'assistant_text', content: 'replacement narration', phase: 'complete'}),
  ]);
  check('relevant-event-retention-eviction', [thinking, ...events.slice(0, 3999)], [ingest(narration)]);
  check('external-view-writers-do-not-become-projection-cache', [events[0], thinking], [
    {type: 'tab.append', tabId: 'thinking', lines: [{id: 'fixture-stray', kind: 'system', text: 'noncanonical extra line'}]},
    ingest(narration),
    {type: 'activity.ingest', entries: [{id: 'fixture-stray', kind: 'status', phase: 'running', title: 'noncanonical activity'}]},
    ingest({...narration, id: 'fixture-narration-2'}),
    {type: 'trace.toggle'},
    {type: 'activity.raw.toggle'},
    ingest({...thinking, content: 'revised expanded output'}),
  ]);
  const accepted = canonicalEventsFromBridgeEvent({type: 'command.result', request_id: 'fixture-command', command: '/status', output: 'accepted', outcome: 'accepted', ok: true, created_at: '2026-09-10T10:00:01Z'})[0];
  const ended = canonicalEventsFromBridgeEvent({type: 'session_end', request_id: 'fixture-command', success: true, created_at: '2026-09-10T10:00:02Z'})[0];
  check('accepted-command-session-end-suppression', [userPromptExecutionEvent('/status', '2026-09-10T10:00:00Z'), accepted, ended], [
    ingest({...accepted, phase: 'complete', raw: {...accepted.raw, outcome: 'completed', completed: true}, content: 'completed'}),
    ingest({...accepted, phase: 'failed', raw: {...accepted.raw, outcome: 'failed', ok: false}, content: 'failed'}),
  ]);
  return results;
}

function breakdown() {
  const base = seed(4000, false);
  const source = base.executionEventLog;
  const incoming = [events[4000]];
  const merged = mergeExecutionEvents(source, incoming);
  const operations = {
    merge: () => mergeExecutionEvents(source, incoming),
    chat: () => projectChatTraceLines(merged, {expanded: false, showRaw: false, routeLabel: routeLabel(base.routePolicy)}),
    thinking: () => projectPaneLines('thinking', merged),
    tools: () => projectPaneLines('tools', merged),
    timeline: () => projectPaneLines('timeline', merged),
    activity: () => projectActivityEntries(merged),
  };
  const result: Record<string, unknown> = {};
  let sink = 0;
  for (const [name, operation] of Object.entries(operations)) {
    const times: number[] = [];
    for (let i = 0; i < sampleCount + warmupCount; i++) {
      const start = performance.now();
      const value = operation();
      const elapsed = performance.now() - start;
      sink += value.length;
      if (i >= warmupCount) times.push(elapsed);
    }
    result[name] = {summary: summarize(times), raw_ms: times};
  }
  return {result, sink, caveat: 'Fixed full-retention snapshot, separately timed functions; do not sum percentiles.'};
}

const startedAt = new Date().toISOString();
const edgeCaseResults = edgeCaseParity();
const workloads = [
  runWorkload('collapsed-growing-history', 1000, false),
  runWorkload('collapsed-full-retention', 4000, false),
  runWorkload('expanded-full-retention', 4000, true),
  runWorkload('expanded-raw-full-retention', 4000, true, true),
];
const components = breakdown();
const sourceHashesAfter = Object.fromEntries(inputFiles.map(path => [path, digest(`${root}/${path}`)]));
const report = {
  schema: 'helm.reducer.projection.benchmark.v1', started_at: startedAt, completed_at: new Date().toISOString(),
  locus: {root, host: hostname(), branch: execFileSync('git', ['branch', '--show-current'], {cwd: root, encoding: 'utf8'}).trim(), head: execFileSync('git', ['rev-parse', 'HEAD'], {cwd: root, encoding: 'utf8'}).trim()},
  environment: {bun: Bun.version, platform: platform(), arch: arch(), cpu: cpus()[0]?.model, logical_cpus: cpus().length},
  clock: 'performance.now; monotonic milliseconds', authority: 'MEASURED_LOCAL_REDUCER_ONLY_SYNTHETIC_FIXTURE',
  caveats: ['No terminal, Ink render, transport, provider, network, or visible UI latency measured.', 'Canonical events constructed by repository adapters from deterministic fixture data before timing.', 'No forced garbage collection; allocation and observed GC pauses are included.', 'Shared host; concurrent development processes were not stopped.', 'Candidate is the shipped reducer; baseline reference rebuilds every projection as before memoization.', 'Comparison excludes randomly regenerated transcript line IDs; all other state values compared every twentieth ingest and at the last ingest.'],
  source_hashes_before: sourceHashesBefore, source_hashes_after: sourceHashesAfter,
  source_stable: JSON.stringify(sourceHashesBefore) === JSON.stringify(sourceHashesAfter),
  candidate: 'Shipped reduceApp with pure projection memo; baseline reference uses full projections',
  actual_bridge_tabs_in_seed: readyState.tabs.map(tab => tab.id), edge_case_parity: edgeCaseResults,
  workloads, components,
};
writeFileSync(output, JSON.stringify(report, null, 2) + '\n', {mode: 0o600});
process.stdout.write(JSON.stringify({report: output, source_stable: report.source_stable}) + '\n');
