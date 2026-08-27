import {describe, expect, test} from "bun:test";

import {manuscriptLines, scrollStatusLine} from "../src/scrollFace";
import {initialState, reduceApp} from "../src/state";
import {matchUiIntent} from "../src/uiIntents";
import type {TranscriptLine} from "../src/types";

const line = (id: string, kind: TranscriptLine["kind"], text: string): TranscriptLine => ({id, kind, text});

describe("FACE-3 the scroll — manuscript projection", () => {
  test("inserts one centered wave rule between turns, never before the first", () => {
    const lines = [
      line("u1", "user", "> hello"),
      line("a1", "assistant", "namaste"),
      line("t1", "thinking", "■ 2s · codex:gpt-5.4 · ^T details"),
      line("u2", "user", "> and again"),
      line("a2", "assistant", "still here"),
    ];
    const out = manuscriptLines(lines, 84);
    expect(out).toHaveLength(6);
    const rule = out[3];
    expect(rule?.kind).toBe("thinking");
    expect(rule?.text.trim()).toBe("~ ~ ~");
    // Centered within the inner measure (84 - 2 padding - 5 rule = 77 -> 38).
    expect(rule?.text).toBe(`${" ".repeat(38)}~ ~ ~`);
    expect(rule?.id).toBe("scroll-rule-3-u2");
    // Everything else passes through untouched, in order.
    expect(out.filter((entry) => !entry.id.startsWith("scroll-rule-")).map((entry) => entry.id)).toEqual([
      "u1",
      "a1",
      "t1",
      "u2",
      "a2",
    ]);
  });

  test("boot prelude with no user lines passes through unchanged", () => {
    const lines = [line("boot-1", "thinking", "namaste"), line("boot-2", "thinking", "type below")];
    expect(manuscriptLines(lines, 80)).toEqual(lines);
  });

  test("consecutive user lines share one turn boundary (no double rule)", () => {
    const lines = [line("u1", "user", "> one"), line("u2", "user", "> two")];
    const out = manuscriptLines(lines, 80);
    expect(out).toHaveLength(2);
  });

  test("narrow measures never produce a negative indent", () => {
    const lines = [line("u1", "user", "> a"), line("a1", "assistant", "b"), line("u2", "user", "> c")];
    const out = manuscriptLines(lines, 4);
    expect(out[2]?.text).toBe("~ ~ ~");
  });
});

describe("FACE-3 the scroll — one-row status drawer", () => {
  test("closed + live carries zero telemetry (silence is health)", () => {
    const status = scrollStatusLine({
      drawerOpen: false,
      routeLabel: "codex:gpt-5.4",
      bridgeStatus: "connected",
      routeState: "ready",
      strategy: "balanced-throughput",
    });
    expect(status).toBe("the scroll  ·  ^D telemetry  ·  F2 zen");
    expect(status).not.toContain("route");
    expect(status).not.toContain("live");
  });

  test("closed + offline breathes exactly one honest token", () => {
    const status = scrollStatusLine({
      drawerOpen: false,
      routeLabel: "codex:gpt-5.4",
      bridgeStatus: "offline",
      routeState: "ready",
    });
    expect(status).toContain("○ offline");
    expect(status).not.toContain("codex");
  });

  test("closed + connected keeps an unverified route visible", () => {
    const status = scrollStatusLine({
      drawerOpen: false,
      routeLabel: "codex:gpt-5.5",
      bridgeStatus: "connected",
      routeState: "unverified",
    });
    expect(status).toContain("unverified");
    expect(status).not.toContain("live");
  });

  test("open drawer is the full telemetry row — route, gate, state, strategy", () => {
    const status = scrollStatusLine({
      drawerOpen: true,
      routeLabel: "codex:gpt-5.4",
      bridgeStatus: "connected",
      routeState: "ready",
      strategy: "balanced-throughput",
    });
    expect(status).toContain("route codex:gpt-5.4");
    expect(status).toContain("● bridge");
    expect(status).toContain("ready");
    expect(status).toContain("balanced-throughput");
    expect(status).toContain("^D close");
  });

  test("open drawer suppresses route state while the bridge is down", () => {
    const status = scrollStatusLine({
      drawerOpen: true,
      routeLabel: "codex:gpt-5.4",
      bridgeStatus: "offline",
      routeState: "ready",
    });
    expect(status).toContain("○ offline");
    expect(status).not.toContain("ready");
  });
});

describe("FACE-3 the scroll — mode wiring", () => {
  test("layout.mode.set enters and leaves the scroll face", () => {
    const toScroll = reduceApp(initialState, {type: "layout.mode.set", mode: "scroll"});
    expect(toScroll.uiMode.layoutMode).toBe("scroll");
    const backToZen = reduceApp(toScroll, {type: "layout.mode.set", mode: "zen"});
    expect(backToZen.uiMode.layoutMode).toBe("zen");
  });

  test("plain-language asks reach the manuscript only via precise phrases", () => {
    expect(matchUiIntent("switch to the scroll view", [], [])).toEqual({kind: "layout", mode: "scroll"});
    expect(matchUiIntent("open reading mode", [], [])).toEqual({kind: "layout", mode: "scroll"});
    expect(matchUiIntent("switch to the manuscript layout", [], [])).toEqual({kind: "layout", mode: "scroll"});
    // Bare "scroll" is a TUI verb — never a layout yank.
    expect(matchUiIntent("show me how to scroll the view", [], [])).toBeNull();
  });
});
