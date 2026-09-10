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
  const isMultiline = /[\r\n\u2028\u2029]/u.test(prompt);
  const cueText = [
    ...(isMultiline
      ? ["multi-line draft · Enter sends all lines · multi-line → chat (intents are single-line)"]
      : []),
    ...(!focused && prompt ? ["Esc → compose"] : []),
  ].join(" · ");
  const wrappedCueLines = cueText ? wrapComposerText(cueText, textWidth) : [];
  const cueBudget = Math.max(0, maxLines - 1);
  const cueLines = wrappedCueLines.length <= cueBudget
    ? wrappedCueLines
    : focused
      ? wrappedCueLines.slice(0, cueBudget)
      : [...wrappedCueLines.slice(0, Math.max(0, cueBudget - 1)), "Esc → compose"];
  return (
    <Box borderStyle="round" borderColor={focused ? THEME.wave : THEME.ridge} paddingX={1} flexDirection="column">
      {prompt ? (
        (() => {
          const lines = wrapComposerText(prompt, textWidth);
          const promptLineBudget = Math.max(1, maxLines - cueLines.length);
          const overflow = lines.length > promptLineBudget;
          const shown = overflow
            ? focused
              ? lines.slice(lines.length - promptLineBudget)
              : lines.slice(0, promptLineBudget)
            : lines;
          return (
            <>
              {shown.map((line, index) => {
                const isLast = index === shown.length - 1;
                // Focused overflow hides the head (marker on line 0); unfocused
                // overflow hides the tail (marker on the last shown line).
                const elided = overflow && (focused ? index === 0 : isLast);
                const prefix = elided ? "⋮ " : index === 0 ? "> " : "  ";
                return (
                  <Text key={index} color={THEME.foam} wrap="truncate-end">
                    <Text color={THEME.stone}>{prefix}</Text>
                    {line}
                    {isLast && focused ? <Text color={THEME.foam} inverse> </Text> : null}
                  </Text>
                );
              })}
              {cueLines.map((line, index) => (
                <Text key={`cue-${index}`} color={THEME.stone} dimColor wrap="truncate-end">{line}</Text>
              ))}
            </>
          );
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
