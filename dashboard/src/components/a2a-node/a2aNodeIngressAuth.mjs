import { createHash, timingSafeEqual } from "node:crypto";
import { TextDecoder } from "node:util";

const MAX_AUTHORIZATION_LENGTH = 4_096;
const MAX_CREDENTIAL_BYTES = 1_024;
const BASIC_HEADER_PATTERN = /^Basic ([A-Za-z0-9+/]+={0,2})$/i;
const CANONICAL_BASE64_PATTERN =
  /^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/;
const CONTROL_CHARACTER_PATTERN = /[\u0000-\u001f\u007f]/u;
const utf8Decoder = new TextDecoder("utf-8", { fatal: true });

/** @param {string} value */
function digestCredential(value) {
  return createHash("sha256").update(value, "utf8").digest();
}

/**
 * Compare fixed-length digests so a mismatch never falls back to ordinary
 * secret string comparison or skips the second credential comparison.
 *
 * @param {string} actual
 * @param {string} expected
 */
function constantTimeEqual(actual, expected) {
  return timingSafeEqual(
    digestCredential(actual),
    digestCredential(expected),
  );
}

/** @param {unknown} value */
function isConfigured(value) {
  return typeof value === "string" && value.length > 0;
}

/**
 * @param {string} user
 * @param {string} password
 */
function validConfiguredCredentials(user, password) {
  return (
    !user.includes(":") &&
    !CONTROL_CHARACTER_PATTERN.test(user) &&
    !CONTROL_CHARACTER_PATTERN.test(password) &&
    Buffer.byteLength(user, "utf8") <= MAX_CREDENTIAL_BYTES &&
    Buffer.byteLength(password, "utf8") <= MAX_CREDENTIAL_BYTES
  );
}

/** @param {string | null} authorization */
function parseBasicCredentials(authorization) {
  if (
    typeof authorization !== "string" ||
    authorization.length > MAX_AUTHORIZATION_LENGTH
  ) {
    return null;
  }
  const headerMatch = BASIC_HEADER_PATTERN.exec(authorization);
  const token = headerMatch?.[1];
  if (
    !token ||
    !CANONICAL_BASE64_PATTERN.test(token) ||
    token.length % 4 !== 0
  ) {
    return null;
  }

  const bytes = Buffer.from(token, "base64");
  if (
    bytes.length === 0 ||
    bytes.length > MAX_CREDENTIAL_BYTES * 2 + 1 ||
    bytes.toString("base64") !== token
  ) {
    return null;
  }

  let decoded;
  try {
    decoded = utf8Decoder.decode(bytes);
  } catch {
    return null;
  }
  if (CONTROL_CHARACTER_PATTERN.test(decoded)) {
    return null;
  }
  const separator = decoded.indexOf(":");
  if (separator <= 0) {
    return null;
  }
  return {
    user: decoded.slice(0, separator),
    password: decoded.slice(separator + 1),
  };
}

/**
 * @param {{
 *   authorization: string | null,
 *   operatorUser: string | undefined,
 *   operatorPassword: string | undefined,
 *   nodeEnv: string | undefined,
 * }} options
 * @returns {
 *   {state: "allow"} |
 *   {state: "unauthorized"} |
 *   {state: "misconfigured"}
 * }
 */
export function evaluateOperatorIngress(options) {
  const userConfigured = isConfigured(options.operatorUser);
  const passwordConfigured = isConfigured(options.operatorPassword);

  if (!userConfigured && !passwordConfigured) {
    return options.nodeEnv === "production"
      ? { state: "misconfigured" }
      : { state: "allow" };
  }
  if (!userConfigured || !passwordConfigured) {
    return { state: "misconfigured" };
  }

  const operatorUser = options.operatorUser;
  const operatorPassword = options.operatorPassword;
  if (!validConfiguredCredentials(operatorUser, operatorPassword)) {
    return { state: "misconfigured" };
  }

  const supplied = parseBasicCredentials(options.authorization);
  if (!supplied) {
    return { state: "unauthorized" };
  }
  const userMatches = constantTimeEqual(supplied.user, operatorUser);
  const passwordMatches = constantTimeEqual(
    supplied.password,
    operatorPassword,
  );
  return (Number(userMatches) & Number(passwordMatches)) === 1
    ? { state: "allow" }
    : { state: "unauthorized" };
}
