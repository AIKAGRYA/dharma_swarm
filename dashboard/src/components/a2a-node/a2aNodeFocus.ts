export interface FocusTargetLike {
  focus: () => void;
  closest: (selectors: string) => unknown;
  hasAttribute: (name: string) => boolean;
  getAttribute: (name: string) => string | null;
}

export interface FocusContainerLike {
  ownerDocument: { activeElement: unknown };
  querySelectorAll: (selectors: string) => ArrayLike<FocusTargetLike>;
  focus: () => void;
}

export interface TabKeyEventLike {
  key: string;
  shiftKey: boolean;
  preventDefault: () => void;
}

export interface IsolationElementLike {
  parentElement: IsolationElementLike | null;
  children: ArrayLike<IsolationElementLike>;
  tagName?: string;
  inert: boolean;
  hasAttribute: (name: string) => boolean;
  getAttribute: (name: string) => string | null;
  setAttribute: (name: string, value: string) => void;
  removeAttribute: (name: string) => void;
}

interface IsolationSnapshot {
  element: IsolationElementLike;
  inert: boolean;
  hadInertAttribute: boolean;
  ariaHidden: string | null;
}

export const DIALOG_FOCUSABLE_SELECTOR = [
  "a[href]",
  "button:not([disabled])",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  '[tabindex]:not([tabindex="-1"])',
].join(",");

function availableTargets(container: FocusContainerLike): FocusTargetLike[] {
  return Array.from(
    container.querySelectorAll(DIALOG_FOCUSABLE_SELECTOR),
  ).filter(
    (target) =>
      !target.hasAttribute("disabled") &&
      target.getAttribute("aria-disabled") !== "true" &&
      !target.closest('[hidden], [inert], [aria-hidden="true"]'),
  );
}

export function trapDialogTabKey(
  container: FocusContainerLike,
  event: TabKeyEventLike,
): void {
  if (event.key !== "Tab") {
    return;
  }

  const targets = availableTargets(container);
  if (targets.length === 0) {
    event.preventDefault();
    container.focus();
    return;
  }

  const activeIndex = targets.indexOf(
    container.ownerDocument.activeElement as FocusTargetLike,
  );
  const lastIndex = targets.length - 1;
  const targetIndex = event.shiftKey
    ? activeIndex <= 0
      ? lastIndex
      : null
    : activeIndex < 0 || activeIndex === lastIndex
      ? 0
      : null;

  if (targetIndex !== null) {
    event.preventDefault();
    targets[targetIndex]?.focus();
  }
}

export function isolateSiblingBranches(
  dialog: IsolationElementLike,
): () => void {
  const snapshots: IsolationSnapshot[] = [];
  let branch: IsolationElementLike | null = dialog;

  while (branch?.parentElement) {
    const parent: IsolationElementLike = branch.parentElement;
    if (parent.tagName?.toLowerCase() === "html") {
      break;
    }
    for (const sibling of Array.from(parent.children)) {
      if (sibling === branch) {
        continue;
      }
      snapshots.push({
        element: sibling,
        inert: sibling.inert,
        hadInertAttribute: sibling.hasAttribute("inert"),
        ariaHidden: sibling.getAttribute("aria-hidden"),
      });
      sibling.inert = true;
      sibling.setAttribute("inert", "");
      sibling.setAttribute("aria-hidden", "true");
    }
    branch = parent;
  }

  let restored = false;
  return () => {
    if (restored) {
      return;
    }
    restored = true;
    for (const snapshot of snapshots.reverse()) {
      snapshot.element.inert = snapshot.inert;
      if (snapshot.hadInertAttribute) {
        snapshot.element.setAttribute("inert", "");
      } else {
        snapshot.element.removeAttribute("inert");
      }
      if (snapshot.ariaHidden === null) {
        snapshot.element.removeAttribute("aria-hidden");
      } else {
        snapshot.element.setAttribute("aria-hidden", snapshot.ariaHidden);
      }
    }
  };
}
