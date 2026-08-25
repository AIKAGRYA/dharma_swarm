"use client";

import { useEffect, useMemo, useState, type MouseEvent as ReactMouseEvent } from "react";

import {
  buildOperatorControlRequest,
  buildAccountUiConfirmationRequest,
  AccountUiConfirmationDeliveryUnknown,
  classifyControlProgress,
  describeDurableControlEvidence,
  evidenceFromSnapshot,
  isOperatorControlReason,
  OperatorControlDeliveryUnknown,
  parseOperatorControlEvidence,
  submitOperatorControl,
  submitAccountUiConfirmation,
  type OperatorControlAction,
  type OperatorControlEvidence,
  type PendingControl,
  type RequestAccepted,
} from "@/lib/sadhanaOperatorControl";

import styles from "./SadhanaOperatorControl.module.css";

interface ActionDefinition {
  action: OperatorControlAction;
  label: string;
  detail: string;
  tone: "normal" | "warning" | "danger";
}

const ACTIONS: ActionDefinition[] = [
  {
    action: "pause",
    label: "Pause campaign",
    detail: "Fence new dispatch while preserving queued work.",
    tone: "warning",
  },
  {
    action: "resume",
    label: "Resume campaign",
    detail: "Restore the exact paused campaign generation.",
    tone: "normal",
  },
  {
    action: "emergency_stop",
    label: "Emergency stop",
    detail: "Ask the root stop path to terminate all campaign units first.",
    tone: "danger",
  },
];

export interface SadhanaOperatorControlProps {
  snapshot?: unknown;
  operatorControlEvidence?: unknown;
  disabled?: boolean;
  normalControlsDisabled: boolean;
  className?: string;
  onRequestAccepted?: (accepted: RequestAccepted) => void;
}

function statusCopy(
  pending: PendingControl | null,
  evidence: OperatorControlEvidence | null,
) {
  if (!pending) {
    return {
      request: "Not requested",
      decision: "Unknown",
      effect: "Unknown",
      detail: "No control request has been accepted in this browser session.",
    };
  }
  const progress = classifyControlProgress(pending, evidence);
  if (progress === "effect_observed") {
    return {
      request: "Accepted",
      decision: "Authority applied",
      effect: "Independently observed",
      detail: "The effect receipt is bound to the exact authority receipt.",
    };
  }
  if (progress === "effect_violated") {
    return {
      request: "Accepted",
      decision: "Authority applied",
      effect: "Postcondition violated",
      detail: "Independent evidence contradicts the requested postcondition.",
    };
  }
  if (progress === "authority_applied_effect_unobserved") {
    return {
      request: "Accepted",
      decision: "Authority applied",
      effect: "Not proven",
      detail: "The authority receipt is present; effect observation is still separate.",
    };
  }
  if (progress === "evidence_unknown") {
    return {
      request: "Accepted",
      decision: "Unknown",
      effect: "Unknown",
      detail: "Evidence is malformed, stale, or behind the pending generation/sequence.",
    };
  }
  return {
    request: "Accepted",
    decision: "Awaiting authority",
    effect: "Not proven",
    detail: "HTTP 202 proves inbox publication only. It does not prove application.",
  };
}

export function SadhanaOperatorControl({
  snapshot,
  operatorControlEvidence,
  disabled = false,
  normalControlsDisabled,
  className = "",
  onRequestAccepted,
}: SadhanaOperatorControlProps) {
  const [selected, setSelected] = useState<OperatorControlAction | null>(null);
  const [step, setStep] = useState<"choose" | "confirm">("choose");
  const [reason, setReason] = useState("");
  const [emergencyPhrase, setEmergencyPhrase] = useState("");
  const [pending, setPending] = useState<PendingControl | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [accountUiReady, setAccountUiReady] = useState(false);
  const [accountUiSubmitting, setAccountUiSubmitting] = useState(false);
  const [accountUiAccepted, setAccountUiAccepted] = useState(false);
  const [accountUiDeliveryUnknown, setAccountUiDeliveryUnknown] = useState(false);
  const [accountUiError, setAccountUiError] = useState("");

  const evidence = useMemo(
    () =>
      operatorControlEvidence === undefined
        ? evidenceFromSnapshot(snapshot)
        : parseOperatorControlEvidence(operatorControlEvidence),
    [operatorControlEvidence, snapshot],
  );
  const status = statusCopy(pending, evidence);
  const durable = describeDurableControlEvidence(evidence);
  const action = ACTIONS.find((candidate) => candidate.action === selected) ?? null;
  const reasonReady = isOperatorControlReason(reason);
  const emergencyReady =
    selected !== "emergency_stop" || emergencyPhrase === "EMERGENCY STOP";
  const selectedNormalControlDisabled =
    normalControlsDisabled && selected !== null && selected !== "emergency_stop";
  const accountUiEligible =
    evidence?.claim_stage === "authority_applied" &&
    evidence.control_state === "PAUSED" &&
    evidence.action === "pause" &&
    evidence.campaign_generation === 1 &&
    evidence.transition_sequence === 1 &&
    evidence.effect_state === "unobserved";

  useEffect(() => {
    const update = () => {
      const documentWidth = Math.max(
        document.documentElement.clientWidth,
        document.documentElement.scrollWidth,
        document.body?.scrollWidth ?? 0,
      );
      setAccountUiReady(
        window.innerWidth === 390 &&
          documentWidth === 390 &&
          window.visualViewport?.width === 390 &&
          window.matchMedia("(pointer: coarse)").matches &&
          navigator.maxTouchPoints > 0,
      );
    };
    const coarse = window.matchMedia("(pointer: coarse)");
    update();
    window.addEventListener("resize", update);
    window.visualViewport?.addEventListener("resize", update);
    coarse.addEventListener("change", update);
    return () => {
      window.removeEventListener("resize", update);
      window.visualViewport?.removeEventListener("resize", update);
      coarse.removeEventListener("change", update);
    };
  }, []);

  function choose(next: OperatorControlAction) {
    if (disabled || (normalControlsDisabled && next !== "emergency_stop")) return;
    setSelected(next);
    setReason("");
    setEmergencyPhrase("");
    setError("");
    setStep("confirm");
  }

  async function submit() {
    if (
      !selected ||
      !reasonReady ||
      !emergencyReady ||
      submitting ||
      disabled ||
      selectedNormalControlDisabled
    ) {
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      const request = buildOperatorControlRequest(selected, reason);
      const accepted = await submitOperatorControl(request);
      const nextPending: PendingControl = {
        accepted,
        baseline_campaign_generation: evidence?.campaign_generation ?? null,
        baseline_transition_sequence: evidence?.transition_sequence ?? null,
      };
      setPending(nextPending);
      onRequestAccepted?.(accepted);
    } catch (caught) {
      setError(
        caught instanceof OperatorControlDeliveryUnknown
          ? caught.message
          : `Request rejected: ${caught instanceof Error ? caught.message : "operator_control_rejected"}`,
      );
    } finally {
      setSubmitting(false);
    }
  }

  async function submitAccountConfirmation(
    event: ReactMouseEvent<HTMLButtonElement>,
  ) {
    if (
      disabled ||
      !accountUiEligible ||
      !accountUiReady ||
      accountUiSubmitting ||
      accountUiAccepted ||
      accountUiDeliveryUnknown
    ) {
      return;
    }
    setAccountUiSubmitting(true);
    setAccountUiError("");
    try {
      const documentWidth = Math.max(
        document.documentElement.clientWidth,
        document.documentElement.scrollWidth,
        document.body?.scrollWidth ?? 0,
      );
      const request = buildAccountUiConfirmationRequest({
        viewportWidthCssPx: window.innerWidth,
        documentWidthCssPx: documentWidth,
        visualViewportWidthCssPx: window.visualViewport?.width ?? -1,
        coarsePointer: window.matchMedia("(pointer: coarse)").matches,
        touchCapability: navigator.maxTouchPoints > 0,
        trustedBrowserEvent: event.nativeEvent.isTrusted,
      });
      await submitAccountUiConfirmation(request);
      setAccountUiAccepted(true);
    } catch (caught) {
      if (caught instanceof AccountUiConfirmationDeliveryUnknown) {
        setAccountUiDeliveryUnknown(true);
        setAccountUiError(caught.message);
      } else {
        setAccountUiError(
          `Confirmation rejected: ${
            caught instanceof Error
              ? caught.message
              : "account_ui_confirmation_rejected"
          }`,
        );
      }
    } finally {
      setAccountUiSubmitting(false);
    }
  }

  return (
    <section
      className={`${styles.shell} ${className}`.trim()}
      aria-labelledby="sadhana-control-title"
      data-testid="sadhana-operator-control"
    >
      <header className={styles.header}>
        <div>
          <p className={styles.eyebrow}>SADHANA · PRIVATE CONTROL</p>
          <h1 id="sadhana-control-title">Operator control</h1>
        </div>
        <span className={styles.transport}>Tailnet only</span>
      </header>

      <div className={styles.truthGrid} aria-label="Control proof stages">
        <div>
          <span>Request accepted</span>
          <strong>{status.request}</strong>
        </div>
        <div>
          <span>Decision applied</span>
          <strong>{status.decision}</strong>
        </div>
        <div>
          <span>Effect executed</span>
          <strong>{status.effect}</strong>
        </div>
      </div>
      <p className={styles.statusDetail} role="status">
        {status.detail}
      </p>

      {normalControlsDisabled && (
        <p className={styles.statusDetail} data-testid="predispatch-view-only">
          Predispatch view-only: pause and resume remain locked until the
          receipt-bound dispatch activation transition is projected. Emergency
          stop remains a separate deliberate path.
        </p>
      )}

      <div className={styles.durable} aria-label="Current campaign control">
        <div className={styles.durableHeading}>
          <h2>Current campaign control</h2>
          <span>{durable.valid ? "validated projection" : "evidence unknown"}</span>
        </div>
        <dl>
          <div>
            <dt>State</dt>
            <dd>{durable.controlState}</dd>
          </div>
          <div>
            <dt>Claim stage</dt>
            <dd>{durable.claimStage}</dd>
          </div>
          <div>
            <dt>Generation / sequence</dt>
            <dd>{durable.generationSequence}</dd>
          </div>
          <div>
            <dt>Last action</dt>
            <dd>{durable.lastAction}</dd>
          </div>
          <div className={styles.durableWide}>
            <dt>Authority</dt>
            <dd title={evidence?.authority_receipt_ref || undefined}>
              {durable.authorityEvidence}
            </dd>
          </div>
          <div className={styles.durableWide}>
            <dt>Effect</dt>
            <dd title={evidence?.effect_receipt_ref || undefined}>
              {durable.effectEvidence}
            </dd>
          </div>
        </dl>
      </div>

      {normalControlsDisabled && (
        <div className={styles.step} data-testid="account-ui-confirmation-gate">
          <div className={styles.stepHeading}>
            <span>One-shot predispatch gate</span>
            <h2>Confirm this authenticated account view</h2>
          </div>
          <p className={styles.statusDetail}>
            This records an authenticated Tailscale account and client-reported
            same-origin gesture, 390px, and coarse-touch observations. It does
            not attest a physical phone, human identity, or human presence, and it
            does not unlock pause or resume.
          </p>
          <p className={styles.statusDetail} data-testid="account-ui-client-state">
            {!accountUiEligible
              ? "Waiting for the exact prepared pause at generation 1 / sequence 1."
              : accountUiReady
                ? "Exact 390px/coarse-touch client observation is ready."
                : "Use an exact 390 CSS px coarse-touch view to continue."}
          </p>
          {accountUiError && (
            <p className={styles.error} role="alert">
              {accountUiError}
            </p>
          )}
          {accountUiAccepted ? (
            <p className={styles.statusDetail} role="status">
              Account UI confirmation recorded once. Dispatch must complete
              within its freshness window; expiry fails closed.
            </p>
          ) : accountUiDeliveryUnknown ? (
            <p className={styles.statusDetail} role="status">
              Delivery is unknown. Do not generate another request. The root
              controller must inspect the fixed one-shot candidate.
            </p>
          ) : (
            <button
              type="button"
              className={styles.submit}
              onClick={submitAccountConfirmation}
              disabled={
                disabled ||
                !accountUiEligible ||
                !accountUiReady ||
                accountUiSubmitting
              }
            >
              {accountUiSubmitting
                ? "Recording confirmation…"
                : "Confirm authenticated account view"}
            </button>
          )}
        </div>
      )}

      {step === "choose" ? (
        <div className={styles.step} data-testid="control-step-choose">
          <div className={styles.stepHeading}>
            <span>Step 1 of 2</span>
            <h2>Choose one bounded request</h2>
          </div>
          <div className={styles.actions}>
            {ACTIONS.map((candidate) => (
              <button
                key={candidate.action}
                type="button"
                className={`${styles.action} ${styles[candidate.tone]}`}
                onClick={() => choose(candidate.action)}
                disabled={
                  disabled ||
                  (normalControlsDisabled && candidate.action !== "emergency_stop")
                }
              >
                <strong>{candidate.label}</strong>
                <span>{candidate.detail}</span>
              </button>
            ))}
          </div>
          <div className={styles.unsupported} aria-label="Unsupported decisions">
            <button type="button" disabled>
              Approve proposal · unavailable
            </button>
            <button type="button" disabled>
              Reject proposal · unavailable
            </button>
            <p>No proposal/effect/warrant decision contract is admitted in this slice.</p>
          </div>
        </div>
      ) : (
        <div className={styles.step} data-testid="control-step-confirm">
          <div className={styles.stepHeading}>
            <span>Step 2 of 2</span>
            <h2>Confirm {action?.label.toLowerCase()}</h2>
          </div>
          <div className={`${styles.confirmBanner} ${selected === "emergency_stop" ? styles.danger : ""}`}>
            <strong>{action?.label}</strong>
            <span>{action?.detail}</span>
          </div>
          <label className={styles.field}>
            <span>Operator reason</span>
            <textarea
              value={reason}
              maxLength={512}
              rows={3}
              placeholder="State why this control is required"
              onChange={(event) => setReason(event.target.value)}
              autoComplete="off"
            />
            <small>{reason.length}/512 · sent only inside the signed request</small>
          </label>
          {selected === "emergency_stop" && (
            <label className={styles.field}>
              <span>Type EMERGENCY STOP</span>
              <input
                value={emergencyPhrase}
                onChange={(event) => setEmergencyPhrase(event.target.value)}
                autoComplete="off"
                spellCheck={false}
              />
              <small>
                After HTTP 202 the dashboard may disconnect. Disconnect is expected, not
                effect proof.
              </small>
            </label>
          )}
          {error && (
            <p className={styles.error} role="alert">
              {error}
            </p>
          )}
          <div className={styles.confirmActions}>
            <button
              type="button"
              className={styles.back}
              onClick={() => setStep("choose")}
              disabled={submitting}
            >
              Back
            </button>
            <button
              type="button"
              className={selected === "emergency_stop" ? styles.stopSubmit : styles.submit}
              onClick={submit}
              disabled={
                !reasonReady ||
                !emergencyReady ||
                submitting ||
                disabled ||
                selectedNormalControlDisabled
              }
            >
              {submitting ? "Publishing request…" : `Confirm ${action?.label.toLowerCase()}`}
            </button>
          </div>
        </div>
      )}

      <footer className={styles.footer}>
        <p>Request acceptance never grants publication, spend, outreach, merge, or restart.</p>
        {pending && (
          <code title={pending.accepted.source_envelope_sha256}>
            {pending.accepted.request_id} · {pending.accepted.source_envelope_sha256.slice(0, 18)}…
          </code>
        )}
      </footer>
    </section>
  );
}
