export type CommandOutcome = "completed" | "accepted" | "unsupported" | "failed";
export type CommandOutcomePhase = "complete" | "running" | "failed";
export type CommandOutcomeReason =
  | "explicit_completed"
  | "explicit_accepted"
  | "explicit_unsupported"
  | "explicit_failed"
  | "missing_outcome"
  | "unknown_outcome"
  | "missing_ok"
  | "contradictory_ok";

export type NormalizedCommandOutcome = Readonly<{
  outcome: CommandOutcome;
  phase: CommandOutcomePhase;
  terminal: boolean;
  rendersCompletion: boolean;
  reason: CommandOutcomeReason;
}>;

type UnknownObject = {[key: string]: unknown};

const COMMAND_OUTCOMES = new Set<CommandOutcome>(["completed", "accepted", "unsupported", "failed"]);

function failed(reason: CommandOutcomeReason): NormalizedCommandOutcome {
  return {
    outcome: "failed",
    phase: "failed",
    terminal: true,
    rendersCompletion: false,
    reason,
  };
}

export function normalizeCommandOutcome(value: unknown): NormalizedCommandOutcome {
  const event = typeof value === "object" && value !== null ? value as UnknownObject : undefined;
  if (!event || !Object.hasOwn(event, "outcome")) {
    return failed("missing_outcome");
  }
  const declared = event.outcome;
  if (typeof declared !== "string" || !COMMAND_OUTCOMES.has(declared as CommandOutcome)) {
    return failed("unknown_outcome");
  }
  if (typeof event.ok !== "boolean") {
    return failed("missing_ok");
  }
  if (declared === "completed") {
    return event.ok === true
      ? {outcome: "completed", phase: "complete", terminal: true, rendersCompletion: true, reason: "explicit_completed"}
      : failed("contradictory_ok");
  }
  if (declared === "accepted") {
    return event.ok === true
      ? {outcome: "accepted", phase: "running", terminal: false, rendersCompletion: false, reason: "explicit_accepted"}
      : failed("contradictory_ok");
  }
  if (event.ok === true) {
    return failed("contradictory_ok");
  }
  return declared === "unsupported"
    ? {outcome: "unsupported", phase: "failed", terminal: true, rendersCompletion: false, reason: "explicit_unsupported"}
    : {outcome: "failed", phase: "failed", terminal: true, rendersCompletion: false, reason: "explicit_failed"};
}
