import React, {type ReactNode} from "react";
import {Box, Text} from "ink";

import {Composer} from "../components/Composer";
import {OnCallTruthBand} from "../components/OnCallTruthBand";
import {StatusFooter} from "../components/StatusFooter";
import {TranscriptPane} from "../components/TranscriptPane";
import {THEME} from "../theme";
import type {
  ActiveTurnState,
  AppState,
  BridgeStatus,
  CanonicalExecutionEvent,
  RoutePolicyState,
  TabSpec,
  TranscriptLine,
} from "../types";
import {BoundaryLine, NihongaRoomBand, PlaceCompass} from "./NihongaChrome";
import {CausalFlowPlane, causalEventRowBudget} from "./CausalFlowPlane";
import {WholeOrganismPlane} from "./WholeOrganismPlane";
import {placeForPane, planeForPane, viewportProfile, workspaceLabel} from "./shellModel";

type Props = {
  width: number;
  height: number;
  activeTab: TabSpec | undefined;
  overlayActive: boolean;
  activeFacet: ReactNode;
  transcriptLines: TranscriptLine[];
  transcriptScrollOffset: number;
  transcriptWindowSize: number;
  transcriptSubtitle?: string;
  transcriptEmptyState?: string;
  transcriptAccentColor?: string;
  ownerProjectionLines: string[];
  events: CanonicalExecutionEvent[];
  prompt: string;
  composerFocused: boolean;
  activeTurn: ActiveTurnState;
  routePolicy: RoutePolicyState;
  liveRouteLabel: string;
  bridgeStatus: BridgeStatus;
  onCallTruth: AppState["onCallTruth"];
  statusMode: string;
};

function Panel({title, active, width, children}: {title: string; active: boolean; width?: `${number}%`; children: ReactNode}): React.ReactElement {
  return (
    <Box
      width={width}
      flexGrow={width ? undefined : 1}
      flexDirection="column"
      overflow="hidden"
      borderStyle="single"
      borderColor={active ? THEME.ridge : THEME.river}
      paddingX={1}
    >
      <Text color={active ? THEME.wave : THEME.stone} bold={active}>{title}</Text>
      {children}
    </Box>
  );
}

function FacetPlane({title, active, width, children}: {title: string; active: boolean; width?: `${number}%`; children: ReactNode}): React.ReactElement {
  return (
    <Box width={width} flexGrow={width ? undefined : 1} flexDirection="column" overflow="hidden">
      <Text color={active ? THEME.wave : THEME.stone} bold={active}>{title}</Text>
      <Box flexGrow={1} overflow="hidden">{children}</Box>
    </Box>
  );
}

function ResizeSafe({width, height, route}: {width: number; height: number; route: string}): React.ReactElement {
  return (
    <Box flexGrow={1} flexDirection="column" justifyContent="center" alignItems="center">
      <Text color={THEME.wave} bold>◆ DHARMA HELM</Text>
      <Text color={THEME.persimmon}>RESIZE-SAFE · {width}×{height}</Text>
      <Text color={THEME.stone}>Structure requires at least 44×18.</Text>
      <Text color={THEME.parchment}>{route}</Text>
      <Text color={THEME.stone}>Ctrl-C quit · resize to continue</Text>
    </Box>
  );
}

export function NihongaCockpit(props: Props): React.ReactElement {
  const profile = viewportProfile(props.width, props.height);
  const activePlace = placeForPane(props.activeTab?.kind);
  const activePlane = planeForPane(props.activeTab?.kind);
  const compact = profile === "compact" || profile === "survival";
  const conversation = (
    <TranscriptPane
      frameless
      bottomAnchor
      title="Conversation"
      lines={props.transcriptLines}
      scrollOffset={props.transcriptScrollOffset}
      windowSize={props.transcriptWindowSize}
      subtitle={props.transcriptSubtitle}
      emptyState={props.transcriptEmptyState}
      accentColor={props.transcriptAccentColor}
    />
  );
  const contextual = props.activeTab?.kind === "chat"
    ? <WholeOrganismPlane projectionLines={props.ownerProjectionLines} activeFacet={props.activeTab.title} compact={profile !== "panorama"} />
    : props.activeFacet;
  const facetOwnsFrame = props.activeTab?.kind !== "chat";

  let workspace: ReactNode;
  if (profile === "resize-safe") {
    workspace = <ResizeSafe width={props.width} height={props.height} route={props.liveRouteLabel} />;
  } else if (props.overlayActive) {
    workspace = <FacetPlane title="OVERLAY / TEMPORARY" active>{props.activeFacet}</FacetPlane>;
  } else if (profile === "panorama") {
    workspace = (
      <Box flexGrow={1} overflow="hidden">
        <Panel title="CONVERSATION / INTENT" active={activePlane === "conversation"} width="45%">{conversation}</Panel>
        {facetOwnsFrame ? (
          <FacetPlane title="ECOSYSTEM / ORGANISM" active={activePlane === "ecosystem"} width="35%">{contextual}</FacetPlane>
        ) : (
          <Panel title="ECOSYSTEM / ORGANISM" active={activePlane === "ecosystem"} width="35%">{contextual}</Panel>
        )}
        <Panel title="CAUSAL / PROOF" active={activePlane === "causal"} width="20%">
          <CausalFlowPlane events={props.events} rowBudget={causalEventRowBudget(props.height)} />
        </Panel>
      </Box>
    );
  } else if (profile === "standard") {
    const contextualFocus = activePlane !== "conversation";
    workspace = (
      <Box flexGrow={1} overflow="hidden">
        <Panel title="CONVERSATION / INTENT" active={!contextualFocus} width={contextualFocus ? "42%" : "58%"}>{conversation}</Panel>
        {facetOwnsFrame ? (
          <FacetPlane title="CONTEXT / ORGANISM" active={contextualFocus} width={contextualFocus ? "58%" : "42%"}>{contextual}</FacetPlane>
        ) : (
          <Panel title="CONTEXT / ORGANISM" active={contextualFocus} width={contextualFocus ? "58%" : "42%"}>{contextual}</Panel>
        )}
      </Box>
    );
  } else {
    workspace = props.activeTab?.kind === "chat"
      ? <Panel title={`${activePlace.toUpperCase()} / FOCUSED`} active>{conversation}</Panel>
      : props.activeFacet;
  }

  return (
    <Box flexDirection="column" height={props.height}>
      {profile === "resize-safe" ? null : (
        <>
          <NihongaRoomBand
            workspace={workspaceLabel(process.cwd())}
            place={activePlace}
            profile={profile}
            routeLabel={props.liveRouteLabel}
            routeState={props.routePolicy.routeState}
            bridgeStatus={props.bridgeStatus}
            width={props.width}
            height={props.height}
          />
          <PlaceCompass active={activePlace} compact={compact} />
          <OnCallTruthBand
            truth={props.onCallTruth}
            compact={props.width < 120}
            width={props.width}
            usableNowCount={props.routePolicy.targets.filter((target) => target.usableNow === true).length}
            usableLaneTotal={props.routePolicy.targets.length}
          />
        </>
      )}
      <Box flexGrow={1} flexShrink={1} overflow="hidden">{workspace}</Box>
      {profile === "resize-safe" ? null : (
        <Box flexDirection="column" flexShrink={0}>
          <BoundaryLine turnPhase={props.activeTurn.phase} />
          <Composer prompt={props.prompt} focused={props.composerFocused} compact={compact} width={props.width} />
          <StatusFooter
            mode={props.statusMode}
            routeLabel={props.liveRouteLabel}
            bridgeStatus={props.bridgeStatus}
            routeState={props.routePolicy.routeState}
            strategy={props.routePolicy.strategy}
            reason={props.routePolicy.availabilityReason}
            compact={compact}
          />
        </Box>
      )}
    </Box>
  );
}
