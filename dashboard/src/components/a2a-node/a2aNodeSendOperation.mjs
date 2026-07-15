import {
  gatewayHeaders,
  gatewayPayload,
  projectStoredSend,
  readUpstreamJson,
  SendRequestError,
} from "./a2aNodeSendServer.mjs";
import {
  claimPacket,
  persistStored,
  persistUnknown,
  releasePacket,
  requestFingerprint,
  SendReceiptStoreError,
} from "./a2aNodeSendReceiptStore.mjs";

const DEFAULT_TIMEOUT_MS = 10_000;

/** @param {string} packetId @param {string} kind @param {number} status */
function unknownExecution(packetId, kind = "upstream", status = 502) {
  return {
    state: "unknown",
    error: {
      kind,
      status,
      message: "Mailbox send outcome is unknown",
      outcome: "UNKNOWN",
      packet_id: packetId,
    },
  };
}

/** @param {string} packetId */
function pendingExecution(packetId) {
  return {
    state: "pending",
    error: {
      kind: "upstream",
      status: 409,
      message: "Mailbox send is still pending",
      outcome: "PENDING",
      packet_id: packetId,
    },
  };
}

/**
 * @param {string} kind
 * @param {number} status
 * @param {string} message
 * @param {string | undefined} packetId
 */
function rejectedExecution(kind, status, message, packetId) {
  return {
    state: "rejected",
    error: {
      kind,
      status,
      message,
      ...(packetId ? { packet_id: packetId } : {}),
    },
  };
}

/** @param {Response} response */
async function discardResponse(response) {
  await response.body?.cancel().catch(() => undefined);
}

/**
 * @param {string} receiptDir
 * @param {{to: string, body: string, packet_id: string}} input
 * @param {ReturnType<typeof unknownExecution>} outcome
 * @param {string} ownerToken
 */
async function preserveUnknown(
  receiptDir,
  input,
  outcome,
  ownerToken,
  storeOptions,
) {
  try {
    const transition = await persistUnknown(
      receiptDir,
      input,
      outcome.error,
      ownerToken,
      storeOptions,
    );
    if (transition.state === "stored") {
      return {
        state: "stored",
        result: transition.result,
        replayed: true,
      };
    }
    if (transition.state === "unknown") {
      return { state: "unknown", error: transition.error };
    }
    if (transition.state === "pending") {
      return pendingExecution(input.packet_id);
    }
  } catch {
    // The durable PENDING claim still prevents a duplicate publish.
  }
  return outcome;
}

/** @param {number} value */
function timeoutValue(value) {
  return Number.isSafeInteger(value) && value > 0 && value <= 60_000
    ? value
    : DEFAULT_TIMEOUT_MS;
}

/**
 * @param {{
 *   fetcher?: typeof fetch,
 *   timeoutMs?: number,
 * }} options
 */
export function createSendCoordinator(options = {}) {
  const inFlight = new Map();
  const timeoutMs = timeoutValue(options.timeoutMs);
  const fetcher =
    options.fetcher ??
    ((input, init) => globalThis.fetch(input, init));

  /**
   * @param {{
   *   input: {to: string, body: string, packet_id: string},
   *   target: URL,
   *   token: string,
   *   receiptDir: string,
   *   staleAfterMs?: number,
   * }} send
   */
  async function executeOnce(send) {
    const { input, target, token, receiptDir } = send;
    const storeOptions = {
      staleAfterMs: send.staleAfterMs,
    };
    let headers;
    try {
      headers = gatewayHeaders(token);
    } catch (error) {
      if (error instanceof SendRequestError) {
        return rejectedExecution(
          "configuration",
          503,
          "Mailbox send configuration is invalid",
        );
      }
      return rejectedExecution(
        "configuration",
        503,
        "Mailbox send configuration is invalid",
      );
    }
    let claim;
    try {
      claim = await claimPacket(receiptDir, input, storeOptions);
    } catch (error) {
      if (error instanceof SendReceiptStoreError) {
        return rejectedExecution(
          "configuration",
          503,
          "Send receipt cache is unavailable",
        );
      }
      return rejectedExecution(
        "configuration",
        503,
        "Send receipt cache is unavailable",
      );
    }

    if (claim.state === "stored") {
      return {
        state: "stored",
        result: claim.result,
        replayed: true,
      };
    }
    if (claim.state === "unknown") {
      return { state: "unknown", error: claim.error };
    }
    if (claim.state === "pending") {
      return pendingExecution(input.packet_id);
    }
    if (claim.state === "conflict") {
      return rejectedExecution(
        "contract",
        409,
        "packet_id is already bound to different content",
        input.packet_id,
      );
    }
    const ownerToken = claim.ownerToken;

    const controller = new AbortController();
    let deadlineReached = false;
    const deadline = setTimeout(() => {
      deadlineReached = true;
      controller.abort();
    }, timeoutMs);
    const finish = async (outcome) => {
      try {
        return await outcome;
      } finally {
        clearTimeout(deadline);
      }
    };
    let upstream;
    try {
      upstream = await fetcher(target, {
        method: "POST",
        headers,
        body: JSON.stringify(gatewayPayload(input)),
        cache: "no-store",
        redirect: "manual",
        signal: controller.signal,
      });
    } catch (error) {
      const aborted =
        deadlineReached ||
        (error instanceof Error && error.name === "AbortError");
      return finish(
        preserveUnknown(
          receiptDir,
          input,
          unknownExecution(
            input.packet_id,
            "upstream",
            aborted ? 504 : 502,
          ),
          ownerToken,
          storeOptions,
        ),
      );
    }

    if (controller.signal.aborted) {
      await discardResponse(upstream);
      return finish(
        preserveUnknown(
          receiptDir,
          input,
          unknownExecution(input.packet_id, "upstream", 504),
          ownerToken,
          storeOptions,
        ),
      );
    }
    if (
      (upstream.status >= 300 && upstream.status <= 399) ||
      upstream.status === 408 ||
      upstream.status >= 500
    ) {
      await discardResponse(upstream);
      const status =
        upstream.status >= 300 && upstream.status <= 399
          ? 502
          : upstream.status;
      return finish(
        preserveUnknown(
          receiptDir,
          input,
          unknownExecution(input.packet_id, "upstream", status),
          ownerToken,
          storeOptions,
        ),
      );
    }
    if (!upstream.ok) {
      await discardResponse(upstream);
      const kind =
        upstream.status === 401 || upstream.status === 403
          ? "auth"
          : upstream.status === 429
            ? "throttle"
            : "contract";
      await releasePacket(
        receiptDir,
        input.packet_id,
        ownerToken,
        storeOptions,
      ).catch(
        () => undefined,
      );
      return finish(
        rejectedExecution(
          kind,
          upstream.status,
          kind === "auth"
            ? "Mailbox authentication rejected this send"
            : kind === "throttle"
              ? "Mailbox throttled this send"
              : "Mailbox send contract was rejected",
          input.packet_id,
        ),
      );
    }

    let result;
    try {
      const payload = await readUpstreamJson(
        upstream,
        controller.signal,
      );
      result = projectStoredSend(payload, input);
      if (JSON.stringify(result).includes(token)) {
        throw new SendRequestError(
          "Mailbox returned malformed storage evidence",
          "projection",
          502,
        );
      }
    } catch (error) {
      const timedOut =
        controller.signal.aborted ||
        (error instanceof Error && error.name === "AbortError");
      return finish(
        preserveUnknown(
          receiptDir,
          input,
          unknownExecution(
            input.packet_id,
            timedOut ? "upstream" : "projection",
            timedOut ? 504 : 502,
          ),
          ownerToken,
          storeOptions,
        ),
      );
    }

    try {
      if (controller.signal.aborted) {
        return finish(
          preserveUnknown(
            receiptDir,
            input,
            unknownExecution(input.packet_id, "upstream", 504),
            ownerToken,
            storeOptions,
          ),
        );
      }
      const transition = await persistStored(
        receiptDir,
        input,
        result,
        ownerToken,
        storeOptions,
      );
      if (transition.state === "stored") {
        return finish({
          state: "stored",
          result: transition.result,
          replayed: !transition.transitioned,
        });
      }
      if (transition.state === "unknown") {
        return finish({
          state: "unknown",
          error: transition.error,
        });
      }
      return finish(pendingExecution(input.packet_id));
    } catch {
      return finish(
        preserveUnknown(
          receiptDir,
          input,
          unknownExecution(
            input.packet_id,
            controller.signal.aborted ? "upstream" : "projection",
            controller.signal.aborted ? 504 : 502,
          ),
          ownerToken,
          storeOptions,
        ),
      );
    }
  }

  return {
    /**
     * @param {{
     *   input: {to: string, body: string, packet_id: string},
     *   target: URL,
     *   token: string,
     *   receiptDir: string,
     *   staleAfterMs?: number,
     * }} send
     */
    async execute(send) {
      const key = `${send.receiptDir}\u0000${send.input.packet_id}`;
      const fingerprint = requestFingerprint(send.input);
      const current = inFlight.get(key);
      if (current) {
        if (current.fingerprint !== fingerprint) {
          return rejectedExecution(
            "contract",
            409,
            "packet_id is already bound to different content",
            send.input.packet_id,
          );
        }
        return current.promise;
      }

      const promise = executeOnce(send);
      const entry = { fingerprint, promise };
      inFlight.set(key, entry);
      try {
        return await promise;
      } finally {
        if (inFlight.get(key) === entry) {
          inFlight.delete(key);
        }
      }
    },
  };
}

export const sendCoordinator = createSendCoordinator();
