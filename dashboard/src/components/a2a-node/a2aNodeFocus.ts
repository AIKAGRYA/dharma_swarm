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
