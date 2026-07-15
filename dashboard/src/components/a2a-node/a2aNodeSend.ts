import {
  A2A_SEND_SESSION_KEY,
  A2AStatusRequestError,
  parseA2ASendUnresolved,
  requestA2ASendStatus,
  serializeA2ASendUnresolved,
  type A2ASendStatusResult,
  type A2ASendUnresolvedDescriptor,
} from "./a2aNodeSendStatus.mjs";

export {
  A2A_SEND_SESSION_KEY,
  parseA2ASendUnresolved,
  serializeA2ASendUnresolved,
};
export type {
  A2ASendStatusResult,
  A2ASendUnresolvedDescriptor,
};

const SEND_URL = "/dashboard/a2a-node/api/a2a/send";
const SUBJECT_TOKEN = /^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$/;

export type A2ASendErrorKind =
  | "transport"
  | "policy"
  | "configuration"
  | "auth"
  | "contract"
  | "throttle"
  | "upstream"
  | "projection";
export type A2ASendOutcome = "PENDING" | "UNKNOWN" | "REJECTED";

export interface A2ASendInput {
  to: string;
  body: string;
  packet_id: string;
}

export interface A2ASendResult {
  ok: true;
  subject: string;
  seq: number;
  from: string;
  packet_id: string;
  evidence_tier: "STORED";
}

export interface A2ASendFailureView {
  kind: A2ASendErrorKind;
  title: string;
  detail: string;
  outcome: A2ASendOutcome;
  packetId: string | null;
}

export class A2ASendError extends Error {
  readonly kind: A2ASendErrorKind;
  readonly status: number | null;
  readonly outcome: A2ASendOutcome;
  readonly packet_id: string | null;

  constructor(
    message: string,
    kind: A2ASendErrorKind,
    status: number | null = null,
    options: {
      outcome?: A2ASendOutcome;
      packetId?: string | null;
    } = {},
  ) {
    super(message);
    this.name = "A2ASendError";
    this.kind = kind;
    this.status = status;
    this.outcome = options.outcome ?? "REJECTED";
    this.packet_id = options.packetId ?? null;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function statusKind(status: number): A2ASendErrorKind {
  if (status === 401 || status === 403) return "auth";
  if (status === 429) return "throttle";
  if (status >= 500) return "upstream";
  return "contract";
}

function statusIsAmbiguous(status: number): boolean {
  return (
    (status >= 300 && status <= 399) ||
    status === 408 ||
    status >= 500
  );
}

function isSendErrorKind(value: unknown): value is A2ASendErrorKind {
  return [
    "transport",
    "policy",
    "configuration",
    "auth",
    "contract",
    "throttle",
    "upstream",
    "projection",
  ].includes(String(value));
}

function safeErrorMessage(
  kind: A2ASendErrorKind,
  status: number | null,
): string {
  switch (kind) {
    case "auth":
      return `Mailbox authentication blocked this send (${status ?? "unknown"})`;
    case "throttle":
      return `Mailbox throttled this send (${status ?? "unknown"})`;
    case "upstream":
      return `Mailbox send was unavailable (${status ?? "unknown"})`;
    case "transport":
      return "Operator send proxy could not be reached";
    case "configuration":
      return "Operator send configuration is unavailable";
    case "policy":
      return `Operator send policy rejected this request (${status ?? "unknown"})`;
    case "contract":
      return `Operator send contract rejected this request (${status ?? "unknown"})`;
    case "projection":
      return "Mailbox returned malformed storage evidence";
  }
}

async function responseError(
  response: Response,
  input: A2ASendInput,
): Promise<A2ASendError> {
  const forceUnknownUpstream =
    (response.status >= 300 && response.status <= 399) ||
    response.status === 408;
  let kind: A2ASendErrorKind = forceUnknownUpstream
    ? "upstream"
    : statusKind(response.status);
  let outcome: A2ASendOutcome = statusIsAmbiguous(response.status)
    ? "UNKNOWN"
    : "REJECTED";
  try {
    const payload: unknown = await response.json();
    const detail =
      isRecord(payload) && isRecord(payload.error) ? payload.error : null;
    if (
      !forceUnknownUpstream &&
      detail &&
      isSendErrorKind(detail.kind)
    ) {
      kind = detail.kind;
    }
    if (
      detail?.outcome === "PENDING" &&
      detail.packet_id === input.packet_id
    ) {
      outcome = "PENDING";
    } else if (
      detail?.outcome === "UNKNOWN" &&
      detail.packet_id === input.packet_id
    ) {
      outcome = "UNKNOWN";
    } else if (
      detail &&
      isSendErrorKind(detail.kind) &&
      detail.kind !== "upstream" &&
      detail.kind !== "transport" &&
      detail.kind !== "projection"
    ) {
      outcome = "REJECTED";
    }
  } catch {
    // Status classification is the safe fallback; upstream bodies stay opaque.
  }
  return new A2ASendError(
    safeErrorMessage(kind, response.status),
    kind,
    response.status,
    { outcome, packetId: input.packet_id },
  );
}

function parseStoredResult(
  payload: unknown,
  input: A2ASendInput,
): A2ASendResult {
  const expectedKeys = new Set([
    "ok",
    "subject",
    "seq",
    "from",
    "packet_id",
    "evidence_tier",
  ]);
  if (
    !isRecord(payload) ||
    Object.keys(payload).length !== expectedKeys.size ||
    Object.keys(payload).some((key) => !expectedKeys.has(key)) ||
    payload.ok !== true ||
    payload.subject !== `dharma.a2a.${input.to}` ||
    !Number.isSafeInteger(payload.seq) ||
    Number(payload.seq) <= 0 ||
    typeof payload.from !== "string" ||
    !SUBJECT_TOKEN.test(payload.from) ||
    payload.packet_id !== input.packet_id ||
    payload.evidence_tier !== "STORED"
  ) {
    throw new A2ASendError(
      safeErrorMessage("projection", 502),
      "projection",
      502,
      { outcome: "UNKNOWN", packetId: input.packet_id },
    );
  }
  return {
    ok: true,
    subject: payload.subject,
    seq: payload.seq as number,
    from: payload.from,
    packet_id: payload.packet_id,
    evidence_tier: "STORED",
  };
}

export async function sendA2AMessage(
  input: A2ASendInput,
  options: { fetcher?: typeof fetch } = {},
): Promise<A2ASendResult> {
  const fetcher = options.fetcher ?? globalThis.fetch;
  let response: Response;
  try {
    response = await fetcher(SEND_URL, {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify(input),
      cache: "no-store",
      credentials: "same-origin",
    });
  } catch {
    throw new A2ASendError(
      safeErrorMessage("transport", null),
      "transport",
      null,
      { outcome: "UNKNOWN", packetId: input.packet_id },
    );
  }
  if (!response.ok) {
    throw await responseError(response, input);
  }
  const contentType = response.headers.get("Content-Type") ?? "";
  if (!contentType.toLowerCase().includes("application/json")) {
    throw new A2ASendError(
      safeErrorMessage("projection", response.status),
      "projection",
      response.status,
      { outcome: "UNKNOWN", packetId: input.packet_id },
    );
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new A2ASendError(
      safeErrorMessage("projection", response.status),
      "projection",
      response.status,
      { outcome: "UNKNOWN", packetId: input.packet_id },
    );
  }
  return parseStoredResult(payload, input);
}

function createPacketId(): string {
  if (!globalThis.crypto?.randomUUID) {
    throw new A2ASendError(
      "This browser cannot create a secure packet identifier",
      "configuration",
    );
  }
  return globalThis.crypto.randomUUID();
}

export async function sendA2AMessageAttempt(
  input: Omit<A2ASendInput, "packet_id">,
  options: {
    fetcher?: typeof fetch;
    randomUUID?: () => string;
    packetId?: string;
  } = {},
): Promise<A2ASendResult> {
  const packetId =
    options.packetId ?? (options.randomUUID ?? createPacketId)();
  return sendA2AMessage(
    { ...input, packet_id: packetId },
    { fetcher: options.fetcher },
  );
}

export async function checkA2ASendStatus(
  packetId: string,
  options: { fetcher?: typeof fetch } = {},
): Promise<A2ASendStatusResult> {
  try {
    return await requestA2ASendStatus(packetId, options);
  } catch (error) {
    if (error instanceof A2AStatusRequestError) {
      const kind = isSendErrorKind(error.kind)
        ? error.kind
        : "projection";
      throw new A2ASendError(
        safeErrorMessage(kind, error.status),
        kind,
        error.status,
        { outcome: "REJECTED", packetId },
      );
    }
    throw new A2ASendError(
      safeErrorMessage("projection", 502),
      "projection",
      502,
      { outcome: "REJECTED", packetId },
    );
  }
}

export function sendOutcomeText(
  result: Pick<A2ASendResult, "evidence_tier" | "seq">,
): string {
  return `${result.evidence_tier} · seq ${result.seq}`;
}

function errorKind(error: unknown): A2ASendErrorKind {
  if (error instanceof A2ASendError) return error.kind;
  if (
    isRecord(error) &&
    error.name === "A2ASendError" &&
    isSendErrorKind(error.kind)
  ) {
    return error.kind;
  }
  return "projection";
}

function errorOutcome(error: unknown): A2ASendOutcome {
  if (error instanceof A2ASendError) return error.outcome;
  if (
    isRecord(error) &&
    error.name === "A2ASendError" &&
    (error.outcome === "PENDING" ||
      error.outcome === "UNKNOWN" ||
      error.outcome === "REJECTED")
  ) {
    return error.outcome;
  }
  return "UNKNOWN";
}

function errorPacketId(error: unknown): string | null {
  if (error instanceof A2ASendError) return error.packet_id;
  if (
    isRecord(error) &&
    error.name === "A2ASendError" &&
    typeof error.packet_id === "string"
  ) {
    return error.packet_id;
  }
  return null;
}

export function sendFailureView(error: unknown): A2ASendFailureView {
  const kind = errorKind(error);
  const outcome = errorOutcome(error);
  const packetId = errorPacketId(error);
  if (outcome === "PENDING") {
    return {
      kind,
      title: "Send still pending",
      detail:
        "This packet is retained for status checks and will not be republished.",
      outcome,
      packetId,
    };
  }
  if (outcome === "UNKNOWN") {
    return {
      kind,
      title: "Send outcome unknown",
      detail:
        "This packet is retained for a safe status check and will not be republished.",
      outcome,
      packetId,
    };
  }
  switch (kind) {
    case "auth":
      return {
        kind,
        title: "Send authentication blocked",
        detail: "The mailbox rejected the server credential. Nothing was stored.",
        outcome,
        packetId,
      };
    case "throttle":
      return {
        kind,
        title: "Send throttled",
        detail: "The mailbox declined this attempt. It was not retried.",
        outcome,
        packetId,
      };
    case "transport":
    case "upstream":
      return {
        kind,
        title: "Mailbox unreachable",
        detail: "This attempt has no storage evidence and was not retried.",
        outcome,
        packetId,
      };
    case "configuration":
      return {
        kind,
        title: "Send unavailable",
        detail: "Server-side mailbox configuration is unavailable.",
        outcome,
        packetId,
      };
    case "policy":
    case "contract":
      return {
        kind,
        title: "Send rejected",
        detail: "The bounded send contract rejected this attempt.",
        outcome,
        packetId,
      };
    case "projection":
      return {
        kind,
        title: "Storage evidence unknown",
        detail: "The response could not prove that the mailbox stored this message.",
        outcome,
        packetId,
      };
  }
}
