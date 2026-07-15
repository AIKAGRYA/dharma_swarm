"use client";

import { Send } from "lucide-react";
import {
  type FormEvent,
  type KeyboardEvent,
  useEffect,
  useRef,
  useState,
} from "react";
import {
  type A2ASendFailureView,
  type A2ASendResult,
  type A2ASendUnresolvedDescriptor,
  A2A_SEND_SESSION_KEY,
  checkA2ASendStatus,
  parseA2ASendUnresolved,
  sendA2AMessageAttempt,
  sendFailureView,
  sendOutcomeText,
  serializeA2ASendUnresolved,
} from "./a2aNodeSend";

function persistUnresolved(value: A2ASendUnresolvedDescriptor) {
  try {
    sessionStorage.setItem(
      A2A_SEND_SESSION_KEY,
      serializeA2ASendUnresolved(value),
    );
  } catch {
    // In-memory retention still prevents an automatic republish.
  }
}

function clearPersistedUnresolved() {
  try {
    sessionStorage.removeItem(A2A_SEND_SESSION_KEY);
  } catch {
    // A blocked storage API must not affect the send boundary.
  }
}

export function A2ANodeCompose() {
  const formRef = useRef<HTMLFormElement | null>(null);
  const pendingRef = useRef(false);
  const [to, setTo] = useState("");
  const [message, setMessage] = useState("");
  const [pending, setPending] = useState(false);
  const [sessionReady, setSessionReady] = useState(false);
  const [outcome, setOutcome] = useState<A2ASendResult | null>(null);
  const [failure, setFailure] = useState<A2ASendFailureView | null>(null);
  const [unresolved, setUnresolved] =
    useState<A2ASendUnresolvedDescriptor | null>(
      null,
    );
  const fieldsDisabled =
    !sessionReady || pending || unresolved !== null;

  useEffect(() => {
    let restored: A2ASendUnresolvedDescriptor | null = null;
    try {
      restored = parseA2ASendUnresolved(
        sessionStorage.getItem(A2A_SEND_SESSION_KEY),
      );
    } catch {
      // A blocked storage API means there is nothing safe to restore.
    }
    if (!restored) {
      setSessionReady(true);
      return;
    }
    setUnresolved(restored);
    setTo(restored.target);
    setPending(true);
    setSessionReady(true);
    void checkA2ASendStatus(restored.packet_id)
      .then((status) => {
        if (status.status === "STORED") {
          setOutcome(status.receipt);
          setUnresolved(null);
          clearPersistedUnresolved();
          return;
        }
        setUnresolved(status);
        persistUnresolved(status);
      })
      .catch((error) => setFailure(sendFailureView(error)))
      .finally(() => setPending(false));
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!sessionReady) return;
    if (pending) return;
    if (unresolved) return;
    if (pendingRef.current) return;
    pendingRef.current = true;
    setPending(true);
    setOutcome(null);
    setFailure(null);
    try {
      const result = await sendA2AMessageAttempt({
        to: to.trim(),
        body: message,
      });
      setOutcome(result);
      setUnresolved(null);
      clearPersistedUnresolved();
      setMessage("");
    } catch (error) {
      const failureView = sendFailureView(error);
      setFailure(failureView);
      if (
        (failureView.outcome === "PENDING" ||
          failureView.outcome === "UNKNOWN") &&
        failureView.packetId
      ) {
        const descriptor: A2ASendUnresolvedDescriptor = {
          packet_id: failureView.packetId,
          target: to.trim(),
          status: failureView.outcome,
        };
        setUnresolved(descriptor);
        persistUnresolved(descriptor);
      }
    } finally {
      pendingRef.current = false;
      setPending(false);
    }
  }

  async function handleStatusCheck() {
    if (!unresolved || pending) return;
    setPending(true);
    setFailure(null);
    try {
      const status = await checkA2ASendStatus(unresolved.packet_id);
      if (status.status === "STORED") {
        setOutcome(status.receipt);
        setUnresolved(null);
        clearPersistedUnresolved();
      } else {
        setUnresolved(status);
        persistUnresolved(status);
      }
    } catch (error) {
      setFailure(sendFailureView(error));
    } finally {
      setPending(false);
    }
  }

  function handleDismissLocal() {
    if (pending) return;
    setUnresolved(null);
    clearPersistedUnresolved();
    setFailure(null);
    setOutcome(null);
    setTo("");
    setMessage("");
  }

  function handleMessageKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
      event.preventDefault();
      formRef.current?.requestSubmit();
    }
  }

  return (
    <section
      className="mb-4 rounded-2xl border border-aozora/25 bg-aozora/[0.045] p-4"
      aria-labelledby="a2a-compose-heading"
    >
      <div className="flex items-start gap-3">
        <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl border border-aozora/25 bg-sumi-950/55 text-aozora">
          <Send size={15} aria-hidden="true" />
        </span>
        <div>
          <h2
            id="a2a-compose-heading"
            className="text-sm font-semibold text-torinoko"
          >
            Send to mailbox
          </h2>
          <p className="mt-1 text-xs leading-relaxed text-kitsurubami/75">
            One bounded mailbox publish. STORED is the ceiling: no delivery,
            task, or effect authority.
          </p>
        </div>
      </div>

      <form
        ref={formRef}
        className="mt-4 grid gap-3"
        onSubmit={handleSubmit}
      >
        <div>
          <label
            htmlFor="a2a-compose-recipient"
            className="text-xs font-semibold text-kitsurubami"
          >
            Recipient
          </label>
          <input
            id="a2a-compose-recipient"
            type="text"
            value={to}
            onChange={(event) => setTo(event.target.value)}
            disabled={fieldsDisabled}
            required
            maxLength={80}
            pattern="[A-Za-z0-9][A-Za-z0-9_-]{0,79}"
            autoComplete="off"
            spellCheck={false}
            placeholder="agent_callsign"
            className="mt-1 min-h-11 w-full rounded-xl border border-sumi-700/45 bg-sumi-950/65 px-3 text-sm text-torinoko outline-none transition-colors placeholder:text-kitsurubami/50 focus:border-aozora/55 disabled:cursor-wait disabled:opacity-60"
          />
        </div>

        <div>
          <label
            htmlFor="a2a-compose-message"
            className="text-xs font-semibold text-kitsurubami"
          >
            Message
          </label>
          <textarea
            id="a2a-compose-message"
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            onKeyDown={handleMessageKeyDown}
            disabled={fieldsDisabled}
            required
            rows={3}
            maxLength={4_096}
            aria-describedby="a2a-compose-shortcut"
            className="mt-1 w-full resize-y rounded-xl border border-sumi-700/45 bg-sumi-950/65 px-3 py-2.5 text-sm leading-relaxed text-torinoko outline-none transition-colors placeholder:text-kitsurubami/50 focus:border-aozora/55 disabled:cursor-wait disabled:opacity-60"
            placeholder="Write a concise message"
          />
          <p
            id="a2a-compose-shortcut"
            className="mt-1 text-xs text-kitsurubami/75"
          >
            Ctrl/⌘ + Enter to send
          </p>
        </div>

        {!unresolved ? (
          <button
            type="submit"
            disabled={pending || !sessionReady}
            className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-aozora px-4 text-sm font-semibold text-sumi-950 transition-opacity hover:opacity-90 disabled:cursor-wait disabled:opacity-55"
          >
            <Send size={15} aria-hidden="true" />
            {pending ? "Sending…" : "Send"}
          </button>
        ) : null}
      </form>

      {unresolved ? (
        <div
          className="mt-3 rounded-xl border border-kohaku/35 bg-kohaku/[0.07] px-3 py-2.5"
          role="status"
          aria-live="polite"
        >
          <p className="text-sm font-semibold text-kohaku">
            {unresolved.status} · status only
          </p>
          <p className="mt-1 break-all font-mono text-xs text-kitsurubami/75">
            packet {unresolved.packet_id} · target {unresolved.target}
          </p>
          <p className="mt-2 text-xs leading-relaxed text-kitsurubami/75">
            Dismissal only hides this local status. The server receipt remains;
            do not resend based on dismissal.
          </p>
          <div className="mt-3 grid grid-cols-2 gap-2">
            <button
              type="button"
              disabled={pending}
              onClick={handleStatusCheck}
              className="min-h-11 rounded-xl border border-aozora/35 px-3 text-xs font-semibold text-aozora disabled:cursor-wait disabled:opacity-55"
            >
              {pending ? "Checking…" : "Check status"}
            </button>
            <button
              type="button"
              disabled={pending}
              onClick={handleDismissLocal}
              className="min-h-11 rounded-xl border border-bengara/35 px-3 text-xs font-semibold text-bengara disabled:cursor-wait disabled:opacity-55"
            >
              Dismiss local status
            </button>
          </div>
        </div>
      ) : null}

      {outcome ? (
        <div
          className="mt-3 rounded-xl border border-rokusho/30 bg-rokusho/[0.07] px-3 py-2.5"
          role="status"
          aria-live="polite"
        >
          <p className="text-sm font-semibold text-rokusho">
            {sendOutcomeText(outcome)}
          </p>
          <p className="mt-1 break-all font-mono text-xs text-kitsurubami/75">
            packet {outcome.packet_id}
          </p>
        </div>
      ) : null}

      {failure ? (
        <div
          className="mt-3 rounded-xl border border-bengara/35 bg-bengara/[0.07] px-3 py-2.5"
          role="alert"
        >
          <p className="text-sm font-semibold text-bengara">{failure.title}</p>
          <p className="mt-1 text-xs leading-relaxed text-kitsurubami/75">
            {failure.detail}
          </p>
          {failure.packetId ? (
            <p className="mt-1 break-all font-mono text-xs text-kitsurubami/75">
              packet {failure.packetId}
            </p>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
