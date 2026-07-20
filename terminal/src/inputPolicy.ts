const BRACKETED_PASTE_START = /\u001b\[200~/g;
const BRACKETED_PASTE_END = /\u001b\[201~/g;

/**
 * Preserve printable prompt text and explicit newlines while dropping terminal
 * control bytes one character at a time. A single pasted control character
 * must never cause the surrounding operator text to disappear.
 */
export function normalizeComposerInput(input: string): string {
  const unwrapped = input
    .replace(BRACKETED_PASTE_START, "")
    .replace(BRACKETED_PASTE_END, "")
    .replace(/\r\n?/g, "\n");

  let normalized = "";
  for (const character of unwrapped) {
    const codePoint = character.codePointAt(0) ?? 0;
    if (character === "\n" || (codePoint >= 0x20 && codePoint !== 0x7f)) {
      normalized += character;
    }
  }
  return normalized;
}

export function isPlainReturn(input: string, returnKey: boolean): boolean {
  if (!returnKey) {
    return false;
  }
  return input === "" || input === "\r";
}
