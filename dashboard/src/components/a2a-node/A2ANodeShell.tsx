"use client";

import Link from "next/link";
import {
  Activity,
  ArrowUpRight,
  ListTodo,
  RadioTower,
  ShieldCheck,
  Users,
  type LucideIcon,
} from "lucide-react";
import {
  type KeyboardEvent as ReactKeyboardEvent,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useAgents } from "@/hooks/useAgents";
import { useA2ASendCards } from "@/hooks/useControlSurface";
import { useFleetNodes } from "@/hooks/useFleetNodes";
import { useTasks } from "@/hooks/useTasks";
import { useTraces } from "@/hooks/useTraces";
import {
  buildReceiptLadder,
  deriveEvidenceComparisonNow,
  formatEvidenceAge,
  mergeActivity,
  type RuntimeTruthState,
} from "@/lib/a2aNodeModel";
import {
  RosterPanel,
  StreamPanel,
  TasksPanel,
} from "./A2ANodePanels";
import { ReceiptsPanel } from "./A2AReceiptsPanel";
import {
  classifyFleetError,
  deriveFleetNodeTruth as deriveNodeTruth,
  type FleetNode,
} from "./a2aNodeFleet";
import {
  trapDialogTabKey,
  type FocusContainerLike,
} from "./a2aNodeFocus";
import { useEvidenceDataUpdatedAt } from "./a2aNodeQueryClock";
import styles from "./A2ANodeShell.module.css";

type TabId = "roster" | "tasks" | "stream" | "receipts";

interface TabDefinition {
  id: TabId;
  label: string;
  icon: LucideIcon;
}

const tabs: readonly TabDefinition[] = [
  { id: "roster", label: "Roster", icon: Users },
  { id: "tasks", label: "Tasks", icon: ListTodo },
  { id: "stream", label: "Stream", icon: Activity },
  { id: "receipts", label: "Receipts", icon: ShieldCheck },
];

const transportPresentation: Record<
  RuntimeTruthState,
  { label: string; dot: string; text: string }
> = {
  runtime: {
    label: "runtime truth",
    dot: "bg-rokusho",
    text: "text-rokusho",
  },
  stale: {
    label: "stale",
    dot: "bg-kinpaku",
    text: "text-kinpaku",
  },
  unreachable: {
    label: "unreachable",
    dot: "bg-bengara",
    text: "text-bengara",
  },
  unknown: {
    label: "awaiting evidence",
    dot: "bg-fuji",
    text: "text-fuji",
  },
};

function fleetPosture(
  nodes: FleetNode[],
  nowMs: number,
  isLoading: boolean,
  error: unknown,
): RuntimeTruthState {
  if (error) {
    return classifyFleetError(error).truth;
  }
  if (isLoading || nodes.length === 0) {
    return "unknown";
  }

  const states = nodes.map((node) => deriveNodeTruth(node, nowMs).state);
  if (states.every((state) => state === "runtime")) {
    return "runtime";
  }
  if (states.every((state) => state === "unreachable")) {
    return "unreachable";
  }
  if (states.some((state) => state === "stale" || state === "unreachable")) {
    return "stale";
  }
  return "unknown";
}

function freshestHeartbeatAge(nodes: FleetNode[], nowMs: number): number | null {
  const ages = nodes
    .map((node) => deriveNodeTruth(node, nowMs).ageMs)
    .filter((age): age is number => age !== null);
  return ages.length ? Math.min(...ages) : null;
}

export function A2ANodeShell() {
  const fleet = useFleetNodes();
  const agents = useAgents();
  const tasks = useTasks();
  const traces = useTraces(48);
  const a2a = useA2ASendCards("", 48);
  const queryDataUpdatedAt = useEvidenceDataUpdatedAt();
  const [activeTab, setActiveTab] = useState<TabId>("roster");
  const [nowMs, setNowMs] = useState<number | null>(null);
  const shellRef = useRef<HTMLDivElement | null>(null);
  const tabRefs = useRef<Array<HTMLButtonElement | null>>([]);

  useEffect(() => {
    const initialFrame = window.requestAnimationFrame(() =>
      setNowMs(Date.now()),
    );
    const timer = window.setInterval(() => setNowMs(Date.now()), 30_000);
    return () => {
      window.cancelAnimationFrame(initialFrame);
      window.clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    const shell = shellRef.current;
    if (!shell) {
      return;
    }
    const previouslyFocused =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
    const handleKeyDown = (event: globalThis.KeyboardEvent) => {
      trapDialogTabKey(
        shell as unknown as FocusContainerLike,
        event,
      );
    };
    document.addEventListener("keydown", handleKeyDown);
    const focusFrame = window.requestAnimationFrame(() => {
      tabRefs.current[0]?.focus();
    });

    return () => {
      window.cancelAnimationFrame(focusFrame);
      document.removeEventListener("keydown", handleKeyDown);
      if (previouslyFocused?.isConnected) {
        previouslyFocused.focus();
      }
    };
  }, []);

  const modelNowMs = deriveEvidenceComparisonNow(nowMs, [
    queryDataUpdatedAt,
  ]);
  const activity = useMemo(
    () =>
      modelNowMs === 0
        ? []
        : mergeActivity(traces.traces, a2a.cards, modelNowMs),
    [traces.traces, a2a.cards, modelNowMs],
  );
  const ladder = useMemo(
    () => buildReceiptLadder(a2a.cards, modelNowMs),
    [a2a.cards, modelNowMs],
  );
  const posture = fleetPosture(
    fleet.nodes,
    modelNowMs,
    fleet.isLoading,
    fleet.error,
  );
  const postureView = transportPresentation[posture];
  const freshestAge = freshestHeartbeatAge(fleet.nodes, modelNowMs);
  const activeIndex = tabs.findIndex((tab) => tab.id === activeTab);

  function selectTab(index: number) {
    const normalized = (index + tabs.length) % tabs.length;
    const next = tabs[normalized];
    if (!next) {
      return;
    }
    setActiveTab(next.id);
    tabRefs.current[normalized]?.focus();
  }

  function handleTabKeyDown(
    event: ReactKeyboardEvent<HTMLButtonElement>,
    index: number,
  ) {
    if (event.key === "ArrowRight") {
      event.preventDefault();
      selectTab(index + 1);
    } else if (event.key === "ArrowLeft") {
      event.preventDefault();
      selectTab(index - 1);
    } else if (event.key === "Home") {
      event.preventDefault();
      selectTab(0);
    } else if (event.key === "End") {
      event.preventDefault();
      selectTab(tabs.length - 1);
    }
  }

  function renderPanel(tabId: TabId) {
    switch (tabId) {
      case "roster":
        return (
          <RosterPanel
            nodes={fleet.nodes}
            agents={agents.agents}
            nowMs={modelNowMs}
            fleetLoading={fleet.isLoading}
            agentsLoading={agents.isLoading}
            fleetError={fleet.error}
            agentsError={agents.error}
          />
        );
      case "tasks":
        return (
          <TasksPanel
            tasks={tasks.tasks}
            nowMs={modelNowMs}
            isLoading={tasks.isLoading}
            error={tasks.error}
          />
        );
      case "stream":
        return (
          <StreamPanel
            activity={activity}
            nowMs={modelNowMs}
            isLoading={
              traces.isLoading || a2a.isLoading || modelNowMs === 0
            }
            traceError={traces.error}
            a2aError={a2a.error}
          />
        );
      case "receipts":
        return (
          <ReceiptsPanel
            cards={a2a.cards}
            ladder={ladder}
            nowMs={modelNowMs}
            isLoading={a2a.isLoading || modelNowMs === 0}
            error={a2a.error}
          />
        );
    }
  }

  return (
    <div
      ref={shellRef}
      className={styles.viewport}
      role="dialog"
      aria-modal="true"
      aria-labelledby="a2a-node-title"
      aria-describedby="a2a-node-summary"
      tabIndex={-1}
    >
      <header className={styles.transport}>
        <div className={`${styles.transportInner} px-4 pb-2.5`}>
          <div className="flex items-center justify-between gap-3">
            <div className="flex min-w-0 items-center gap-2.5">
              <div className="grid h-8 w-8 shrink-0 place-items-center rounded-xl border border-aozora/20 bg-aozora/[0.06] text-aozora">
                <RadioTower size={15} aria-hidden="true" />
              </div>
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <p id="a2a-node-title" className="truncate font-heading text-sm font-semibold tracking-[-0.02em] text-torinoko">
                    A2A Operator Node
                  </p>
                  <span className="rounded-full border border-sumi-700/35 px-1.5 py-0.5 font-mono text-xs uppercase tracking-wider text-kitsurubami/80">
                    read only
                  </span>
                </div>
                <p id="a2a-node-summary" className="mt-0.5 truncate font-mono text-xs uppercase tracking-[0.16em] text-kitsurubami/75">
                  fleet / taskboard / receipt rail
                </p>
              </div>
            </div>
            <Link
              href="/dashboard/command-post"
              prefetch={false}
              className="grid h-9 w-9 shrink-0 place-items-center rounded-full border border-sumi-700/40 bg-sumi-900/75 text-kitsurubami transition-colors hover:border-sumi-600 hover:text-torinoko"
              aria-label="Open Command Post"
            >
              <ArrowUpRight size={15} aria-hidden="true" />
            </Link>
          </div>

          <div className="mt-2 flex items-center justify-between gap-3 rounded-xl border border-sumi-700/25 bg-sumi-950/55 px-3 py-2">
            <div className="flex min-w-0 items-center gap-2">
              <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${postureView.dot}`} />
              <span
                className={`truncate text-xs font-semibold uppercase tracking-[0.12em] ${postureView.text}`}
                aria-live="polite"
              >
                {postureView.label}
              </span>
              <span className="truncate font-mono text-xs text-kitsurubami/75">
                /api/fleet/nodes
              </span>
            </div>
            <div className="flex shrink-0 items-center gap-2 font-mono text-xs text-kitsurubami/75">
              <span>{fleet.count} nodes</span>
              <span aria-hidden="true">·</span>
              <span>
                {fleet.isFetching && !fleet.isLoading
                  ? "syncing"
                  : formatEvidenceAge(freshestAge)}
              </span>
            </div>
          </div>
        </div>
      </header>

      <nav className={styles.bottomDock} aria-label="A2A node sections">
        <div
          className={`${styles.bottomDockInner} grid grid-cols-4 gap-1 py-1.5`}
          role="tablist"
          aria-orientation="horizontal"
        >
          {tabs.map((tab, index) => {
            const Icon = tab.icon;
            const selected = activeIndex === index;
            return (
              <button
                key={tab.id}
                ref={(element) => {
                  tabRefs.current[index] = element;
                }}
                id={`a2a-tab-${tab.id}`}
                type="button"
                role="tab"
                aria-selected={selected}
                aria-controls={`a2a-panel-${tab.id}`}
                tabIndex={selected ? 0 : -1}
                onClick={() => setActiveTab(tab.id)}
                onKeyDown={(event) => handleTabKeyDown(event, index)}
                className={`flex min-h-12 flex-col items-center justify-center gap-1 rounded-xl px-1 text-xs font-medium transition-colors ${
                  selected
                    ? "bg-sumi-800/85 text-aozora"
                    : "text-kitsurubami/75 hover:bg-sumi-900 hover:text-torinoko"
                }`}
              >
                <Icon size={17} strokeWidth={selected ? 2 : 1.7} aria-hidden="true" />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>
      </nav>

      <main className={styles.scrollRegion}>
        <div className={styles.contentInner}>
          {tabs.map((tab) => {
            const selected = activeTab === tab.id;
            return (
              <section
                key={tab.id}
                id={`a2a-panel-${tab.id}`}
                role="tabpanel"
                tabIndex={selected ? 0 : -1}
                aria-labelledby={`a2a-tab-${tab.id}`}
                className={styles.tabPanel}
                hidden={!selected}
              >
                {selected ? renderPanel(tab.id) : null}
              </section>
            );
          })}
        </div>
      </main>
    </div>
  );
}
