import React from "react";
import {Box, Text} from "ink";
import {THEME} from "../theme";

type Props = {
  prompt: string;
  focused?: boolean;
  compact?: boolean;
  // Total composer width (terminal cols it spans); used to wrap + cap the text.
  width?: number;
};

// Greedy word-wrap to a column budget, honoring explicit newlines and splitting
// any word longer than the budget. Returns the visual lines the prompt occupies.
export function wrapComposerText(text: string, width: number): string[] {
  if (width <= 0) return [text];
  const out: string[] = [];
  for (const paragraph of text.split("\n")) {
    if (paragraph === "") {
      out.push("");
      continue;
    }
    let line = "";
    for (const word of paragraph.split(" ")) {
      let w = word;
      if (line === "") {
        while (w.length > width) {
          out.push(w.slice(0, width));
          w = w.slice(width);
        }
        line = w;
      } else if ((line + " " + w).length <= width) {
        line += " " + w;
      } else {
        out.push(line);
        while (w.length > width) {
          out.push(w.slice(0, width));
          w = w.slice(width);
        }
        line = w;
      }
    }
    out.push(line);
  }
  return out;
}

// FACE-1 zen-pure composer, now EXPANDABLE (operator word 2026-06-16: "the typing
// window must be expandable to match the text length… expands if i type beyond
// the third line"). It grows with the wrapped text up to a cap, then bottom-
// anchors so the newest text + cursor are always visible — the cap keeps the
// chrome bounded so a long message can never push the conversation off-screen
// (F-163). One sanctioned wave-accent border per the de-border law.
export function Composer({prompt, focused = true, compact = false, width = 80}: Props): React.ReactElement {
  const maxLines = compact ? 4 : 6;
  // Box border (2) + paddingX (2) = 4 cols of chrome; "> " / "  " prefix = 2.
  const textWidth = Math.max(8, width - 4 - 2);
  return (
    <Box borderStyle="round" borderColor={focused ? THEME.wave : THEME.ridge} paddingX={1} flexDirection="column">
      {prompt ? (
        (() => {
          const lines = wrapComposerText(prompt, textWidth);
          const overflow = lines.length > maxLines;
          const shown = overflow ? lines.slice(lines.length - maxLines) : lines;
          return shown.map((line, index) => {
            const isFirstReal = index === 0 && !overflow;
            const isLast = index === shown.length - 1;
            return (
              <Text key={index} color={THEME.foam} wrap="truncate-end">
                <Text color={THEME.stone}>{isFirstReal ? "> " : overflow && index === 0 ? "⋮ " : "  "}</Text>
                {line}
                {isLast && focused ? <Text color={THEME.foam} inverse> </Text> : null}
              </Text>
            );
          });
        })()
      ) : (
        <Box>
          <Text color={THEME.stone}>&gt; </Text>
          {focused ? <Text color={THEME.foam} inverse> </Text> : null}
          <Text color={THEME.stone} dimColor>
            {focused ? " Type a message · / commands · ? keys" : " Navigation active · Esc returns to composer"}
          </Text>
        </Box>
      )}
    </Box>
  );
}
