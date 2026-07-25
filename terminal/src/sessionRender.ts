import {projectSessionDetailHistory} from "./sessionContinuity.ts";
import type {SessionCatalogEntry, SessionCatalogPayload, SessionDetailPayload} from "./types.ts";

export const SESSION_CATALOG_VIEWPORT_SIZE = 8;

export type SessionCatalogViewport = {
  entries: SessionCatalogEntry[];
  startIndex: number;
  endIndex: number;
  loadedCount: number;
  totalCount: number;
};

export type SessionConversationLine = {
  role: "you" | "agent";
  content: string;
};

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.min(Math.max(value, minimum), maximum);
}

export function compactText(value: string, maximumLength: number): string {
  const normalized = value.replace(/\s+/g, " ").trim();
  if (maximumLength <= 0 || normalized.length <= maximumLength) {
    return maximumLength <= 0 ? "" : normalized;
  }
  if (maximumLength === 1) {
    return "…";
  }
  return `${normalized.slice(0, maximumLength - 1)}…`;
}

export function compactSessionId(sessionId: string, maximumLength = 10): string {
  const normalized = sessionId.trim();
  if (normalized.length <= maximumLength) {
    return normalized;
  }
  if (maximumLength < 5) {
    return compactText(normalized, maximumLength);
  }
  const headLength = Math.ceil((maximumLength - 1) / 2);
  const tailLength = maximumLength - headLength - 1;
  return `${normalized.slice(0, headLength)}…${normalized.slice(-tailLength)}`;
}

export function compactSessionRoute(
  providerId: string,
  modelId: string,
  maximumLength = 12,
): string {
  const provider = providerId.trim().toLowerCase();
  const model = modelId
    .trim()
    .replace(new RegExp(`^${provider.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}[-/:]?`, "i"), "");
  return compactText(`${provider.slice(0, 3)}/${model || modelId.trim()}`, maximumLength);
}

export function centeredSessionViewport(
  catalog: SessionCatalogPayload | undefined,
  selectedSessionId: string | undefined,
  maximumRows = SESSION_CATALOG_VIEWPORT_SIZE,
): SessionCatalogViewport {
  const allEntries = catalog?.sessions ?? [];
  const loadedCount = catalog?.returned_count ?? allEntries.length;
  const totalCount = catalog?.count ?? loadedCount;
  const viewportSize = Math.max(1, maximumRows);
  const selectedIndex = Math.max(
    0,
    allEntries.findIndex((entry) => entry.session.session_id === selectedSessionId),
  );
  const maximumStart = Math.max(0, allEntries.length - viewportSize);
  const startIndex = clamp(selectedIndex - Math.floor(viewportSize / 2), 0, maximumStart);
  const entries = allEntries.slice(startIndex, startIndex + viewportSize);
  return {
    entries,
    startIndex,
    endIndex: startIndex + entries.length,
    loadedCount,
    totalCount,
  };
}

export function sessionConversationLines(
  detail: SessionDetailPayload | undefined,
  maximumLines = 4,
): SessionConversationLine[] {
  if (!detail) {
    return [];
  }
  return projectSessionDetailHistory(detail)
    .slice(-Math.max(0, maximumLines))
    .map((message) => ({
      role: message.role === "user" ? "you" : "agent",
      content: message.content.replace(/\s+/g, " ").trim(),
    }));
}

export function sessionStatusGlyph(status: string): string {
  switch (status.trim().toLowerCase()) {
    case "completed":
      return "✓";
    case "running":
      return "…";
    case "cancelled":
      return "⊘";
    case "interrupted":
      return "!";
    case "failed":
      return "×";
    default:
      return "?";
  }
}

export function sessionContinuityLabel(
  continuityMode: "fresh" | "resume",
  activeSessionId: string | undefined,
  selectedSessionId: string | undefined,
): string {
  if (
    continuityMode === "resume" &&
    activeSessionId &&
    selectedSessionId === activeSessionId
  ) {
    return "resume armed";
  }
  return "next fresh";
}
