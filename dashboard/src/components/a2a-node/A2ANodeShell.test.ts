import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
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
const messageSource = readFileSync(
  new URL("./A2ANodeMessages.tsx", import.meta.url),
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
const localHookUrl = new URL("./useA2ANodeData.ts", import.meta.url);

async function focusModule() {
  const loaded = await import("./a2aNodeFocus.ts").catch(() => null);
  assert.ok(loaded, "a2aNodeFocus support module must exist");
  return loaded;
}

test("fixed shell is an isolated dialog with tablist before tabpanels", () => {
  assert.match(shellSource, /role="dialog"/);
  assert.match(shellSource, /aria-modal="true"/);
  assert.match(shellSource, /aria-labelledby="a2a-node-title"/);
  assert.match(shellSource, /isolateSiblingBranches\(\s*shell/);

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

interface FakeIsolationNode {
  name: string;
  parentElement: FakeIsolationNode | null;
  children: FakeIsolationNode[];
  inert: boolean;
  attributes: Map<string, string>;
  hasAttribute: (name: string) => boolean;
  getAttribute: (name: string) => string | null;
  setAttribute: (name: string, value: string) => void;
  removeAttribute: (name: string) => void;
}

function isolationNode(name: string): FakeIsolationNode {
  const attributes = new Map<string, string>();
  return {
    name,
    parentElement: null,
    children: [],
    inert: false,
    attributes,
    hasAttribute: (attribute) => attributes.has(attribute),
    getAttribute: (attribute) => attributes.get(attribute) ?? null,
    setAttribute: (attribute, value) => {
      attributes.set(attribute, value);
    },
    removeAttribute: (attribute) => {
      attributes.delete(attribute);
    },
  };
}

function append(parent: FakeIsolationNode, ...children: FakeIsolationNode[]) {
  parent.children.push(...children);
  for (const child of children) {
    child.parentElement = parent;
  }
}

test("dialog isolation hides only sibling branches and restores exact state", async () => {
  const loaded = await focusModule();
  const isolateSiblingBranches = loaded.isolateSiblingBranches as
    | ((node: FakeIsolationNode) => () => void)
    | undefined;
  assert.equal(typeof isolateSiblingBranches, "function");

  const body = isolationNode("body");
  const appBranch = isolationNode("app-branch");
  const bodySibling = isolationNode("body-sibling");
  const pageBranch = isolationNode("page-branch");
  const appSibling = isolationNode("app-sibling");
  const shell = isolationNode("shell");
  const pageSibling = isolationNode("page-sibling");
  append(body, appBranch, bodySibling);
  append(appBranch, pageBranch, appSibling);
  append(pageBranch, shell, pageSibling);

  bodySibling.inert = true;
  bodySibling.setAttribute("inert", "");
  bodySibling.setAttribute("aria-hidden", "false");
  appSibling.setAttribute("aria-hidden", "false");

  const restore = isolateSiblingBranches!(shell);
  for (const sibling of [bodySibling, appSibling, pageSibling]) {
    assert.equal(sibling.inert, true, `${sibling.name} must be inert`);
    assert.equal(sibling.getAttribute("aria-hidden"), "true");
  }
  for (const containingBranch of [shell, pageBranch, appBranch, body]) {
    assert.equal(containingBranch.inert, false);
    assert.equal(containingBranch.hasAttribute("inert"), false);
    assert.equal(containingBranch.getAttribute("aria-hidden"), null);
  }

  restore();
  assert.equal(bodySibling.inert, true);
  assert.equal(bodySibling.hasAttribute("inert"), true);
  assert.equal(bodySibling.getAttribute("aria-hidden"), "false");
  assert.equal(appSibling.inert, false);
  assert.equal(appSibling.hasAttribute("inert"), false);
  assert.equal(appSibling.getAttribute("aria-hidden"), "false");
  assert.equal(pageSibling.inert, false);
  assert.equal(pageSibling.hasAttribute("inert"), false);
  assert.equal(pageSibling.getAttribute("aria-hidden"), null);

  restore();
  assert.equal(pageSibling.getAttribute("aria-hidden"), null);
});

test("dialog focuses the selected tab and Escape returns to dashboard", () => {
  assert.match(shellSource, /getAttribute\("aria-selected"\) === "true"/);
  assert.match(shellSource, /event\.key === "Escape"/);
  assert.match(shellSource, /router\.push\("\/dashboard"\)/);
  assert.match(shellSource, /previouslyFocused\?\.isConnected/);
});

test("clock starts hydration-safe and begins only after mount", () => {
  assert.match(shellSource, /useState<number \| null>\(null\)/);
  assert.doesNotMatch(shellSource, /useState\(\(\) => Date\.now\(\)\)/);
  assert.match(shellSource, /setNowMs\(Date\.now\(\)\)/);
});

test("query update timestamps advance one shared comparison clock", () => {
  assert.doesNotMatch(shellSource, /useEvidenceDataUpdatedAt\(\)/);
  assert.match(shellSource, /deriveEvidenceComparisonNow\(/);
  assert.match(shellSource, /agentsQuery\.dataUpdatedAt/);
  assert.match(shellSource, /tasksQuery\.dataUpdatedAt/);
  assert.match(shellSource, /tracesQuery\.dataUpdatedAt/);
  assert.match(shellSource, /a2aQuery\.dataUpdatedAt/);
  assert.match(shellSource, /fleetQuery\.dataUpdatedAt/);
  assert.equal(shellSource.match(/setInterval\(/g)?.length, 1);
});

test("all browser reads use the same-origin operator proxy without secrets", () => {
  assert.equal(existsSync(localHookUrl), true, "local read hooks must exist");
  const localHookSource = existsSync(localHookUrl)
    ? readFileSync(localHookUrl, "utf8")
    : "";

  assert.match(hookSource, /fetchRawFleetNodes/);
  assert.doesNotMatch(hookSource, /\bapiFetch\b/);
  assert.doesNotMatch(hookSource, /\bapiPath\b/);
  assert.match(hookSource, /\/dashboard\/a2a-node\/api\/fleet\/nodes/);
  assert.match(localHookSource, /\/dashboard\/a2a-node\/api\//);
  assert.doesNotMatch(localHookSource, /DASHBOARD_API_KEY|NEXT_PUBLIC|apiPath/);
  for (const reader of [
    "fetchNodeAgents",
    "fetchNodeTasks",
    "fetchNodeTraces",
    "fetchNodeCards",
  ]) {
    assert.match(localHookSource, new RegExp(`\\b${reader}\\b`));
  }
  assert.doesNotMatch(localHookSource, /\bfetchNodeArray\b/);
  assert.doesNotMatch(
    shellSource,
    /@\/hooks\/(?:useAgents|useTasks|useTraces|useControlSurface)/,
  );
  assert.match(shellSource, /useA2ANodeAgents/);
  assert.doesNotMatch(panelSource, /\bclassifyFleetError\b/);
});

test("every read surface renders classified truth without blanket unreachable copy", () => {
  assert.match(shellSource, /classifyNodeReadError\(error\)/);
  assert.ok(
    (panelSource.match(/nodeReadFailureView\(/g) ?? []).length >= 4,
    "fleet, agents, tasks, and both stream sources must classify errors",
  );
  assert.match(receiptSource, /nodeReadFailureView\(error/);
  assert.doesNotMatch(
    panelSource,
    /title="(?:Agent registry|TaskBoard|Trace activity|A2A receipt stream) unreachable"/,
  );
  assert.doesNotMatch(
    receiptSource,
    /title="Receipt projection unreachable"/,
  );
});

test("useful A2A cards keep an explicit partial-truth label on both views", () => {
  const localHookSource = readFileSync(localHookUrl, "utf8");
  assert.match(localHookSource, /partial: query\.data\?\.partial \?\? null/);
  assert.match(shellSource, /a2aPartial=\{a2aQuery\.partial\}/);
  assert.match(panelSource, /a2aPartial/);
  assert.match(receiptSource, /partial/);
  assert.match(panelSource, /title=\{a2aPartial\.title\}/);
  assert.match(receiptSource, /title=\{partial\.title\}/);
});

test("model-owned keys drive receipt and activity React identity", () => {
  assert.match(panelSource, /key=\{item\.key\}/);
  assert.match(receiptSource, /key=\{evidence\.key\}/);
  assert.doesNotMatch(receiptSource, /key=\{item\.id\}/);
});

test("mobile labels avoid tiny low-contrast text and CSS uses theme colors", () => {
  for (const source of [
    shellSource,
    panelSource,
    receiptSource,
    messageSource,
  ]) {
    assert.doesNotMatch(source, /text-\[(?:8|9|10)px\]/);
    assert.doesNotMatch(source, /\btext-sumi-600\b/);
  }
  assert.doesNotMatch(cssSource, /#[0-9a-f]{3,8}\b/i);
  assert.doesNotMatch(cssSource, /\brgba?\(/i);
  assert.match(cssSource, /var\(--color-aozora\)/);
  assert.match(cssSource, /var\(--color-sumi-950\)/);
});
