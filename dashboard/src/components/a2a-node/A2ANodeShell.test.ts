import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const shellSource = readFileSync(
  new URL("./A2ANodeShell.tsx", import.meta.url),
  "utf8",
);
const panelSource = readFileSync(
  new URL("./A2ANodePanels.tsx", import.meta.url),
  "utf8",
);
const receiptSource = readFileSync(
  new URL("./A2AReceiptsPanel.tsx", import.meta.url),
  "utf8",
);
const cssSource = readFileSync(
  new URL("./A2ANodeShell.module.css", import.meta.url),
  "utf8",
);
const hookSource = readFileSync(
  new URL("../../hooks/useFleetNodes.ts", import.meta.url),
  "utf8",
);

async function focusModule() {
  const loaded = await import("./a2aNodeFocus.ts").catch(() => null);
  assert.ok(loaded, "a2aNodeFocus support module must exist");
  return loaded;
}

test("fixed shell is an isolated dialog with tablist before tabpanels", () => {
  assert.match(shellSource, /role="dialog"/);
  assert.match(shellSource, /aria-modal="true"/);
  assert.match(shellSource, /aria-labelledby="a2a-node-title"/);
  assert.doesNotMatch(shellSource, /\binert\b/);

  const navPosition = shellSource.indexOf(
    "<nav className={styles.bottomDock}",
  );
  const mainPosition = shellSource.indexOf(
    "<main className={styles.scrollRegion}>",
  );
  assert.ok(navPosition >= 0, "tablist navigation must be rendered");
  assert.ok(mainPosition >= 0, "tabpanel region must be rendered");
  assert.ok(navPosition < mainPosition, "tablist must precede panels in DOM");
});

test("stable tabpanel shells only construct the active panel content", () => {
  assert.match(shellSource, /tabs\.map\(\(tab\) =>/);
  assert.match(shellSource, /id=\{`a2a-panel-\$\{tab\.id\}`\}/);
  assert.match(shellSource, /hidden=\{!selected\}/);
  assert.match(
    shellSource,
    /\{selected \? renderPanel\(tab\.id\) : null\}/,
  );
});

test("dialog tab trap wraps focus and handles focus outside the shell", async () => {
  const { trapDialogTabKey } = await focusModule();
  const documentState: { activeElement: unknown } = { activeElement: null };
  const focused: string[] = [];
  const target = (name: string) => ({
    focus: () => {
      focused.push(name);
      documentState.activeElement = targets[name as keyof typeof targets];
    },
    closest: () => null,
    hasAttribute: () => false,
    getAttribute: () => null,
  });
  const targets = {
    first: target("first"),
    middle: target("middle"),
    last: target("last"),
  };
  const container = {
    ownerDocument: documentState,
    querySelectorAll: () => Object.values(targets),
    focus: () => focused.push("container"),
  };
  const event = (shiftKey: boolean) => {
    let prevented = false;
    return {
      key: "Tab",
      shiftKey,
      preventDefault: () => {
        prevented = true;
      },
      get prevented() {
        return prevented;
      },
    };
  };

  documentState.activeElement = targets.last;
  const forward = event(false);
  trapDialogTabKey(container, forward);
  assert.equal(forward.prevented, true);
  assert.equal(focused.at(-1), "first");

  documentState.activeElement = targets.first;
  const backward = event(true);
  trapDialogTabKey(container, backward);
  assert.equal(backward.prevented, true);
  assert.equal(focused.at(-1), "last");

  documentState.activeElement = {};
  const outside = event(false);
  trapDialogTabKey(container, outside);
  assert.equal(outside.prevented, true);
  assert.equal(focused.at(-1), "first");
});

test("clock starts hydration-safe and begins only after mount", () => {
  assert.match(shellSource, /useState<number \| null>\(null\)/);
  assert.doesNotMatch(shellSource, /useState\(\(\) => Date\.now\(\)\)/);
  assert.match(shellSource, /setNowMs\(Date\.now\(\)\)/);
});

test("query update timestamps advance one shared comparison clock", () => {
  assert.match(shellSource, /useEvidenceDataUpdatedAt\(\)/);
  assert.match(shellSource, /deriveEvidenceComparisonNow\(/);
  assert.equal(shellSource.match(/setInterval\(/g)?.length, 1);
});

test("fleet hook uses raw transport and UI distinguishes invalid projection", () => {
  assert.match(hookSource, /fetchRawFleetNodes/);
  assert.doesNotMatch(hookSource, /\bapiFetch\b/);
  assert.match(panelSource, /classifyFleetError/);
  assert.match(panelSource, /kind=\{fleetFailure\.truth === "unknown"/);
});

test("model-owned keys drive receipt and activity React identity", () => {
  assert.match(panelSource, /key=\{item\.key\}/);
  assert.match(receiptSource, /key=\{evidence\.key\}/);
  assert.doesNotMatch(receiptSource, /key=\{item\.id\}/);
});

test("mobile labels avoid tiny low-contrast text and CSS uses theme colors", () => {
  for (const source of [shellSource, panelSource, receiptSource]) {
    assert.doesNotMatch(source, /text-\[(?:8|9|10)px\]/);
    assert.doesNotMatch(source, /\btext-sumi-600\b/);
  }
  assert.doesNotMatch(cssSource, /#[0-9a-f]{3,8}\b/i);
  assert.doesNotMatch(cssSource, /\brgba?\(/i);
  assert.match(cssSource, /var\(--color-aozora\)/);
  assert.match(cssSource, /var\(--color-sumi-950\)/);
});
