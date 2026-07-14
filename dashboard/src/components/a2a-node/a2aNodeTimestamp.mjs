/**
 * @typedef {"missing" | "format" | "calendar" | "future" | "clock"} TimestampIssue
 * @typedef {{
 *   valid: true,
 *   raw: string,
 *   timestampMs: number,
 *   issue: null,
 *   detail: null,
 * } | {
 *   valid: false,
 *   raw: string | null,
 *   timestampMs: null,
 *   issue: TimestampIssue,
 *   detail: string,
 * }} TimestampEvidence
 * @typedef {{
 *   state: "runtime" | "stale" | "unreachable" | "unknown",
 *   ageMs: number | null,
 * }} Freshness
 */

const STALE_AFTER_MS = 5 * 60 * 1_000;
const UNREACHABLE_AFTER_MS = 15 * 60 * 1_000;
const RFC3339_PATTERN =
  /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(\.\d{1,9})?(Z|([+-])(\d{2}):(\d{2}))$/;

/**
 * @param {string | null} raw
 * @param {TimestampIssue} issue
 * @param {string} detail
 * @returns {TimestampEvidence}
 */
function invalidTimestamp(raw, issue, detail) {
  return { valid: false, raw, timestampMs: null, issue, detail };
}

/** @param {number} year @param {number} month */
function daysInMonth(year, month) {
  return new Date(Date.UTC(year, month, 0)).getUTCDate();
}

/**
 * Parse only RFC3339 timestamps carrying an explicit, known timezone.
 * Evidence later than the supplied comparison clock is always rejected.
 *
 * @param {unknown} value
 * @param {number} nowMs
 * @returns {TimestampEvidence}
 */
export function inspectRfc3339Timestamp(value, nowMs) {
  const raw = typeof value === "string" ? value.trim() : "";
  if (!raw) {
    return invalidTimestamp(null, "missing", "timestamp is missing");
  }
  if (!Number.isFinite(nowMs)) {
    return invalidTimestamp(raw, "clock", "comparison clock is invalid");
  }

  const match = RFC3339_PATTERN.exec(raw);
  if (!match) {
    return invalidTimestamp(
      raw,
      "format",
      "timestamp must be RFC3339 with a timezone offset",
    );
  }

  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const hour = Number(match[4]);
  const minute = Number(match[5]);
  const second = Number(match[6]);
  const fractional = match[7]?.slice(1) ?? "";
  const zone = match[8];
  const zoneSign = match[9];
  const zoneHour = Number(match[10] ?? 0);
  const zoneMinute = Number(match[11] ?? 0);

  if (
    year < 1 ||
    month < 1 ||
    month > 12 ||
    day < 1 ||
    day > daysInMonth(year, month) ||
    hour > 23 ||
    minute > 59 ||
    second > 59 ||
    zoneHour > 23 ||
    zoneMinute > 59 ||
    zone === "-00:00"
  ) {
    return invalidTimestamp(
      raw,
      "calendar",
      "timestamp is not a valid RFC3339 calendar value",
    );
  }

  const milliseconds = Number(`${fractional}000`.slice(0, 3));
  const local = new Date(0);
  local.setUTCFullYear(year, month - 1, day);
  local.setUTCHours(hour, minute, second, milliseconds);
  const offsetMinutes =
    zone === "Z"
      ? 0
      : (zoneSign === "+" ? 1 : -1) * (zoneHour * 60 + zoneMinute);
  const timestampMs = local.getTime() - offsetMinutes * 60_000;

  if (!Number.isFinite(timestampMs)) {
    return invalidTimestamp(
      raw,
      "calendar",
      "timestamp is not a valid RFC3339 calendar value",
    );
  }
  if (timestampMs > nowMs) {
    return invalidTimestamp(
      raw,
      "future",
      "future timestamp is not runtime evidence",
    );
  }
  return { valid: true, raw, timestampMs, issue: null, detail: null };
}

/**
 * @param {string | null | undefined} observedAt
 * @param {number} [nowMs]
 * @returns {Freshness}
 */
export function deriveFreshness(observedAt, nowMs = Date.now()) {
  const timestamp = inspectRfc3339Timestamp(observedAt, nowMs);
  if (!timestamp.valid) {
    return { state: "unknown", ageMs: null };
  }

  const ageMs = nowMs - timestamp.timestampMs;
  if (ageMs <= STALE_AFTER_MS) {
    return { state: "runtime", ageMs };
  }
  if (ageMs <= UNREACHABLE_AFTER_MS) {
    return { state: "stale", ageMs };
  }
  return { state: "unreachable", ageMs };
}

/**
 * @param {number | null} clockNowMs
 * @param {readonly (number | null | undefined)[]} queryDataUpdatedAt
 */
export function deriveEvidenceComparisonNow(
  clockNowMs,
  queryDataUpdatedAt,
) {
  let comparisonNow =
    typeof clockNowMs === "number" && Number.isFinite(clockNowMs)
      ? Math.max(0, clockNowMs)
      : 0;
  for (const updatedAt of queryDataUpdatedAt) {
    if (
      typeof updatedAt === "number" &&
      Number.isFinite(updatedAt) &&
      updatedAt > comparisonNow
    ) {
      comparisonNow = updatedAt;
    }
  }
  return comparisonNow;
}
