import React from "react";

import {ActivityPane} from "../components/ActivityPane";
import {AgentsPane} from "../components/AgentsPane";
import {ApprovalsPane} from "../components/ApprovalsPane";
import {ControlPane, buildControlPaneSections, buildRuntimePaneSections} from "../components/ControlPane";
import {ModelPicker} from "../components/ModelPicker";
import {PaneSwitcher} from "../components/PaneSwitcher";
import {RepoPane, buildRepoPaneSections} from "../components/RepoPane";
import {SessionsPane} from "../components/SessionsPane";
import {TranscriptPane} from "../components/TranscriptPane";
import type {AppState, RouteTarget, TabPreview, TabSpec, TranscriptLine} from "../types";

type TranscriptMeta = {
  subtitle?: string;
  emptyState?: string;
  accentColor?: string;
};

type Props = {
  state: AppState;
  activeTab: TabSpec | undefined;
  modelChoices: RouteTarget[];
  compact: boolean;
  contextualCompact: boolean;
  scrollOffset: number;
  windowSize: number;
  repoPreview?: TabPreview;
  controlPreview?: TabPreview;
  activeControlPreview?: TabPreview;
  displayedTranscriptLines: TranscriptLine[];
  transcriptMeta: TranscriptMeta;
};

export function ActiveFacet(props: Props): React.ReactElement {
  const {activeTab, state} = props;
  const controlLines = state.tabs.find((tab) => tab.id === "control")?.lines ?? [];

  if (state.uiMode.activeOverlay.kind === "paneSwitcher") {
    return (
      <PaneSwitcher
        tabs={state.tabs}
        selectedIndex={Math.min(state.uiMode.activeOverlay.selectedIndex, Math.max(state.tabs.length - 1, 0))}
        maximumRows={props.compact ? 6 : 10}
      />
    );
  }
  if (state.uiMode.activeOverlay.kind === "modelPicker") {
    return (
      <ModelPicker
        choices={props.modelChoices}
        selectedIndex={Math.min(state.uiMode.activeOverlay.selectedIndex, Math.max(props.modelChoices.length - 1, 0))}
        title="Model Picker"
        compact={props.compact}
      />
    );
  }
  if (
    (props.compact || props.contextualCompact)
    && activeTab
    && (activeTab.kind === "repo" || activeTab.kind === "control" || activeTab.kind === "runtime")
  ) {
    const sections = activeTab.kind === "repo"
      ? buildRepoPaneSections(props.repoPreview, activeTab.lines, props.controlPreview, controlLines)
      : activeTab.kind === "runtime"
        ? buildRuntimePaneSections(props.activeControlPreview, activeTab.lines.length === 0 ? controlLines : activeTab.lines)
        : buildControlPaneSections(props.activeControlPreview, activeTab.lines);
    const selectedIndex = Math.min(state.paneFocusIndices[activeTab.id] ?? 0, Math.max(sections.length - 1, 0));
    const selected = sections[selectedIndex];
    const lines: TranscriptLine[] = (selected?.rows ?? ["No detail available."]).map((text, index) => ({
      id: `${activeTab.id}-compact-${selectedIndex}-${index}`,
      kind: "system",
      text,
    }));
    return (
      <TranscriptPane
        title={`${activeTab.title} · ${selected?.title ?? "Detail"}`}
        lines={lines}
        scrollOffset={props.scrollOffset}
        windowSize={props.windowSize}
        subtitle={`${selectedIndex + 1}/${Math.max(sections.length, 1)} sections · j/k select`}
      />
    );
  }
  if (activeTab?.kind === "repo") {
    return (
      <RepoPane
        title={activeTab.title}
        preview={props.repoPreview}
        controlPreview={props.controlPreview}
        controlLines={controlLines}
        lines={activeTab.lines}
        scrollOffset={props.scrollOffset}
        windowSize={props.windowSize}
        selectedSectionIndex={state.paneFocusIndices[activeTab.id] ?? 0}
      />
    );
  }
  if (activeTab?.kind === "control" || activeTab?.kind === "runtime") {
    return (
      <ControlPane
        title={activeTab.title}
        mode={activeTab.kind}
        preview={props.activeControlPreview}
        lines={activeTab.kind === "runtime" && activeTab.lines.length === 0 ? controlLines : activeTab.lines}
        scrollOffset={props.scrollOffset}
        windowSize={props.windowSize}
        selectedSectionIndex={state.paneFocusIndices[activeTab.id] ?? 0}
      />
    );
  }
  if (activeTab?.kind === "approvals") {
    return (
      <ApprovalsPane
        title={activeTab.title}
        approvalPane={state.approvalPane}
        authorityObserved={state.authoritativeSurfaces.approvals}
        bridgeStatus={state.bridgeStatus}
        compact={props.contextualCompact}
      />
    );
  }
  if (activeTab?.kind === "sessions") {
    return (
      <SessionsPane
        title={activeTab.title}
        sessionPane={state.sessionPane}
        sessionContinuity={state.sessionContinuity}
        authorityObserved={state.authoritativeSurfaces.sessions}
        bridgeStatus={state.bridgeStatus}
        compact={props.contextualCompact}
      />
    );
  }
  if (activeTab?.kind === "agents") {
    return (
      <AgentsPane
        title={activeTab.title}
        lines={activeTab.lines}
        selectedRouteIndex={state.paneFocusIndices[activeTab.id] ?? 0}
        authorityObserved={state.authoritativeSurfaces.agents}
        bridgeStatus={state.bridgeStatus}
        compact={props.contextualCompact}
      />
    );
  }
  if (activeTab?.kind === "thinking" || activeTab?.kind === "tools" || activeTab?.kind === "timeline") {
    return (
      <ActivityPane
        title={activeTab.title}
        paneKind={activeTab.kind}
        feed={state.activityFeed}
        scrollOffset={props.scrollOffset}
        windowSize={props.windowSize}
      />
    );
  }
  return (
    <TranscriptPane
      title={activeTab?.title ?? "Workspace"}
      lines={props.displayedTranscriptLines}
      scrollOffset={props.scrollOffset}
      windowSize={props.windowSize}
      subtitle={props.transcriptMeta.subtitle}
      emptyState={props.transcriptMeta.emptyState}
      accentColor={props.transcriptMeta.accentColor}
    />
  );
}
