import type {SessionCatalogPayload, SessionDetailPayload, SessionPaneState} from "./types";

function catalogEntryBySessionId(catalog: SessionCatalogPayload | undefined, sessionId: string) {
  return catalog?.sessions.find((entry) => entry.session.session_id === sessionId);
}

function currentSelectionProvenance(current: SessionPaneState): SessionPaneState["selectionProvenance"] {
  return current.selectionProvenance ?? "follow_latest";
}

function currentPendingRequests(
  current: SessionPaneState,
): SessionPaneState["pendingDetailRequestsBySessionId"] {
  return current.pendingDetailRequestsBySessionId ?? {};
}

export function nextSessionPaneAfterCatalog(
  current: SessionPaneState,
  catalog: SessionCatalogPayload,
): SessionPaneState {
  const entriesBySessionId = new Map(
    catalog.sessions.map((entry) => [entry.session.session_id, entry] as const),
  );
  const pinnedSessionId =
    currentSelectionProvenance(current) === "operator_pinned" &&
    current.selectedSessionId &&
    entriesBySessionId.has(current.selectedSessionId)
      ? current.selectedSessionId
      : undefined;
  const selectedSessionId = pinnedSessionId ?? catalog.sessions[0]?.session.session_id;

  const detailsBySessionId: SessionPaneState["detailsBySessionId"] = {};
  for (const [sessionId, detail] of Object.entries(current.detailsBySessionId)) {
    const catalogEntry = entriesBySessionId.get(sessionId);
    if (catalogEntry && catalogEntry.session.updated_at === detail.session.updated_at) {
      detailsBySessionId[sessionId] = detail;
    }
  }

  const pendingDetailRequestsBySessionId: SessionPaneState["pendingDetailRequestsBySessionId"] = {};
  for (const [sessionId, pending] of Object.entries(currentPendingRequests(current))) {
    const catalogEntry = entriesBySessionId.get(sessionId);
    if (
      catalogEntry &&
      (pending.catalogUpdatedAt === undefined || pending.catalogUpdatedAt === catalogEntry.session.updated_at)
    ) {
      pendingDetailRequestsBySessionId[sessionId] = pending;
    }
  }

  return {
    catalog,
    selectedSessionId,
    selectionProvenance: pinnedSessionId ? "operator_pinned" : "follow_latest",
    detailsBySessionId,
    pendingDetailRequestsBySessionId,
  };
}

export function nextSessionPaneAfterSelection(
  current: SessionPaneState,
  sessionId: string,
): SessionPaneState {
  return {
    ...current,
    selectedSessionId: sessionId,
    selectionProvenance: "operator_pinned",
  };
}

export function nextSessionPaneAfterDetailRequest(
  current: SessionPaneState,
  requestId: string,
  sessionId: string,
): SessionPaneState {
  if (!requestId || !sessionId) {
    return current;
  }
  return {
    ...current,
    pendingDetailRequestsBySessionId: {
      ...currentPendingRequests(current),
      [sessionId]: {
        requestId,
        sessionId,
        catalogUpdatedAt: catalogEntryBySessionId(current.catalog, sessionId)?.session.updated_at,
      },
    },
  };
}

export function nextSessionPaneAfterDetailResult(
  current: SessionPaneState,
  requestId: string,
  sessionId: string,
  detail: SessionDetailPayload,
): SessionPaneState | undefined {
  if (!requestId || !sessionId || detail.session.session_id !== sessionId) {
    return undefined;
  }
  const pending = currentPendingRequests(current)[sessionId];
  if (!pending || pending.requestId !== requestId || pending.sessionId !== sessionId) {
    return undefined;
  }

  const pendingDetailRequestsBySessionId = {...currentPendingRequests(current)};
  delete pendingDetailRequestsBySessionId[sessionId];
  return {
    ...current,
    detailsBySessionId: {
      ...current.detailsBySessionId,
      [sessionId]: detail,
    },
    pendingDetailRequestsBySessionId,
  };
}

export function nextSessionPaneAfterDetailFailure(
  current: SessionPaneState,
  requestId: string,
): SessionPaneState {
  if (!requestId) {
    return current;
  }
  const pendingDetailRequestsBySessionId = {...currentPendingRequests(current)};
  const failed = Object.entries(pendingDetailRequestsBySessionId).find(
    ([, pending]) => pending.requestId === requestId,
  );
  if (!failed) {
    return current;
  }
  delete pendingDetailRequestsBySessionId[failed[0]];
  return {
    ...current,
    pendingDetailRequestsBySessionId,
  };
}
