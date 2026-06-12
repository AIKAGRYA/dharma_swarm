import {describe, expect, test} from "bun:test";

import {OFFLINE_NO_SIGNAL_TEXT, extractSlashCommands, formatTranscriptLine, projectLinesForBridgeStatus} from "../src/transcriptFormatting";
import {buildInitialTabs} from "../src/mockContent";
import type {BridgeStatus} from "../src/types";
import path from "node:path";

const REPO_ROOT = path.resolve(import.meta.dir, "..", "..");

describe("extractSlashCommands", () => {
  test("finds slash commands without treating filesystem paths as commands", () => {
    expect(extractSlashCommands("run /git then /runtime")).toEqual(["/git", "/runtime"]);
    expect(extractSlashCommands(`saved to ${REPO_ROOT}/terminal/src/app.tsx`)).toEqual([]);
  });
});

describe("formatTranscriptLine", () => {
  test("formats headings and subheadings distinctly", () => {
    expect(formatTranscriptLine({id: "1", kind: "system", text: "# Mission"}).segments[0]).toEqual({
      text: "Mission",
      color: "magenta",
      bold: true,
    });
    expect(formatTranscriptLine({id: "2", kind: "system", text: "## Active Lane"}).segments[0]).toEqual({
      text: "Active Lane",
      color: "cyan",
      bold: true,
    });
  });

  test("highlights inline slash commands in blue", () => {
    const formatted = formatTranscriptLine({
      id: "3",
      kind: "assistant",
      text: "Run /git and then /runtime for current truth.",
    });

    expect(formatted.segments.map((segment) => segment.text)).toEqual([
      "Run ",
      "/git",
      " and then ",
      "/runtime",
      " for current truth.",
    ]);
    expect(formatted.segments[1]?.color).toBe("blue");
    expect(formatted.segments[3]?.color).toBe("blue");
  });
});

describe("projectLinesForBridgeStatus (F-161)", () => {
  test("bridge-down maps every pending/loading placeholder in the pane registry to the no-signal message", () => {
    const tabsWithPlaceholders: string[] = [];
    for (const tab of buildInitialTabs()) {
      const projected = projectLinesForBridgeStatus(tab.lines, "offline");
      expect(projected).toHaveLength(tab.lines.length);
      for (const [index, line] of projected.entries()) {
        expect(line.text).not.toMatch(/loading/i);
        expect(line.id).toBe(tab.lines[index]!.id);
        expect(line.kind).toBe(tab.lines[index]!.kind);
      }
      const hadPlaceholder = tab.lines.some((line) => /loading/i.test(line.text));
      if (hadPlaceholder) {
        tabsWithPlaceholders.push(tab.id);
        expect(projected.some((line) => line.text.includes(OFFLINE_NO_SIGNAL_TEXT))).toBe(true);
      } else {
        expect(projected).toBe(tab.lines);
      }
    }
    expect(tabsWithPlaceholders.sort()).toEqual(["agents", "commands", "control", "evolution", "models", "ontology", "repo"]);
  });

  test("placeholder subject is preserved in the no-signal line, never a pending state", () => {
    const projected = projectLinesForBridgeStatus(
      [{id: "models-1", kind: "system", text: "Model policy loading..."}],
      "offline",
    );
    expect(projected[0]?.text).toBe(`Model policy: ${OFFLINE_NO_SIGNAL_TEXT}`);
    const bare = projectLinesForBridgeStatus([{id: "x", kind: "system", text: "Loading"}], "offline");
    expect(bare[0]?.text).toBe(OFFLINE_NO_SIGNAL_TEXT);
  });

  test("non-offline bridge states leave lines untouched (loading stays honest while connecting)", () => {
    const lines = [{id: "models-1", kind: "system" as const, text: "Model policy loading..."}];
    for (const status of ["booting", "connected", "degraded"] as BridgeStatus[]) {
      expect(projectLinesForBridgeStatus(lines, status)).toBe(lines);
    }
  });
});
