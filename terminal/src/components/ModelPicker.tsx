import React from "react";
import {Box, Text} from "ink";
import {routeStatePresentation} from "../routePresentation.ts";
import {THEME} from "../theme";
import type {RouteTarget} from "../types";

type Props = {
  choices: RouteTarget[];
  selectedIndex: number;
  title?: string;
  compact?: boolean;
};

export function modelPickerShortcut(index: number): string | undefined {
  if (index >= 0 && index < 9) return String(index + 1);
  if (index === 9) return "0";
  return index >= 10 && index < 36 ? String.fromCharCode(87 + index) : undefined;
}

export function modelPickerShortcutIndex(input: string): number | undefined {
  if (/^[1-9]$/.test(input)) return Number.parseInt(input, 10) - 1;
  if (input === "0") return 9;
  const codePoint = input.toLowerCase().codePointAt(0);
  return input.length === 1 && codePoint !== undefined && codePoint >= 97 && codePoint <= 122
    ? codePoint - 87
    : undefined;
}

function truthWord(value: boolean | undefined): string {
  return value === true ? "yes" : value === false ? "no" : "unknown";
}

export function ModelPicker({choices, selectedIndex, title = "Model Picker", compact = false}: Props): React.ReactElement {
  const windowSize = compact ? 6 : 10;
  const start = Math.max(0, Math.min(selectedIndex - (compact ? 2 : 4), Math.max(choices.length - windowSize, 0)));
  const visible = choices.slice(start, start + windowSize);
  return (
    <Box flexGrow={1} flexDirection="column" borderStyle="round" borderColor={THEME.ridge} paddingX={1}>
      <Text color={THEME.wave} bold>{title}</Text>
      <Text color={THEME.stone}>
        {compact ? "Enter apply | Esc close" : "Enter apply | Esc close | j/k or arrows move | 1-9 direct"} | shown key selects usable row | {choices.length} lanes
      </Text>
      <Text color={THEME.stone}>key  lane                    usable now  identity verified</Text>
      {visible.length === 0 ? (
        <Text color={THEME.stone}>No model targets loaded.</Text>
      ) : (
        visible.map((choice, index) => {
          const actualIndex = start + index;
          const active = actualIndex === selectedIndex;
          const route = routeStatePresentation(choice.routeState);
          const shortcut = modelPickerShortcut(actualIndex) ?? "–";
          return (
            <Box key={`${choice.provider}:${choice.model}`} flexDirection="column" marginBottom={compact ? 0 : 1}>
              <Text color={active ? THEME.wave : THEME.foam} bold={active}>
                {active ? "▶" : "•"} {shortcut}  {compact ? choice.alias : `${choice.alias} -> ${choice.label}`}
                {"  "}{truthWord(choice.usableNow)}{"         "}{truthWord(choice.identityVerified)}
              </Text>
              <Text color={THEME.stone}>
                {"  "}{compact ? choice.provider : `${choice.provider}:${choice.model}`} {"| "}
                <Text color={route.color}>{route.glyph} {route.word}</Text>
              </Text>
              {!compact && choice.availabilityReason ? <Text color={THEME.stone}>  {choice.availabilityReason}</Text> : null}
            </Box>
          );
        })
      )}
    </Box>
  );
}
