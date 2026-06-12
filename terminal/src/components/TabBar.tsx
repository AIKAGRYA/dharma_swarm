import React from "react";
import {Box, Text} from "ink";

import type {TabSpec} from "../types";
import {THEME} from "../theme";

type Props = {
  tabs: TabSpec[];
  activeTabId: string;
  compact?: boolean;
};

// F-021: one-line tab bar at ALL widths — the bordered-pill rows cost 6+ rows
// of chrome and scrolled the header off every graded size. The windowed
// single-row widget is the only renderer; `compact` now only tightens titles.
export function TabBar({tabs, activeTabId, compact = false}: Props): React.ReactElement {
  const limit = 6;
  const activeIndex = Math.max(0, tabs.findIndex((tab) => tab.id === activeTabId));
  const startIndex = Math.max(0, Math.min(activeIndex - 2, Math.max(tabs.length - limit, 0)));
  const visibleTabs = tabs.slice(startIndex, startIndex + limit);
  const hasOverflowLeft = startIndex > 0;
  const hasOverflowRight = startIndex + limit < tabs.length;

  return (
    <Box flexWrap="nowrap">
      {hasOverflowLeft ? <Text color={THEME.stone}>◂ </Text> : null}
      {visibleTabs.map((tab) => {
        const active = tab.id === activeTabId;
        const title = compact && tab.title.length > 8 ? `${tab.title.slice(0, 7)}…` : tab.title;
        return (
          <Box key={tab.id} marginRight={1}>
            <Text color={active ? THEME.wave : THEME.stone} bold={active}>
              {active ? `[${title}]` : title}
            </Text>
          </Box>
        );
      })}
      {hasOverflowRight ? <Text color={THEME.stone}>▸</Text> : null}
    </Box>
  );
}
