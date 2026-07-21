import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import test from "node:test";

const composeUrl = new URL("./A2ANodeCompose.tsx", import.meta.url);
const panelSource = readFileSync(
  new URL("./A2ANodePanels.tsx", import.meta.url),
  "utf8",
);
const shellSource = readFileSync(
  new URL("./A2ANodeShell.tsx", import.meta.url),
  "utf8",
);
const composeSource = existsSync(composeUrl)
  ? readFileSync(composeUrl, "utf8")
  : "";

test("Stream mounts one bounded compose surface and shell no longer claims read-only", () => {
  assert.equal(existsSync(composeUrl), true, "compose component must exist");
  assert.match(panelSource, /import \{ A2ANodeCompose \}/);
  assert.match(panelSource, /<A2ANodeCompose\s*\/>/);
  assert.equal(panelSource.match(/<A2ANodeCompose\s*\/>/g)?.length, 1);
  assert.doesNotMatch(shellSource, />\s*read only\s*</i);
  assert.match(shellSource, />\s*bounded send\s*</i);
  assert.match(composeSource, /no delivery,\s*task, or effect authority/i);
});

test("compose uses labelled controls and native plus explicit keyboard submit", () => {
  assert.match(composeSource, /<form[\s\S]*onSubmit=\{handleSubmit\}/);
  assert.match(composeSource, /htmlFor="a2a-compose-recipient"/);
  assert.match(composeSource, /id="a2a-compose-recipient"/);
  assert.match(composeSource, /htmlFor="a2a-compose-message"/);
  assert.match(composeSource, /id="a2a-compose-message"/);
  assert.match(composeSource, /type="submit"/);
  assert.match(composeSource, /event\.key === "Enter"/);
  assert.match(composeSource, /event\.(?:metaKey|ctrlKey)/);
  assert.match(composeSource, /requestSubmit\(\)/);
});

test("compose disables controls during its single pending attempt", () => {
  assert.match(composeSource, /if \(pending\) return/);
  assert.match(composeSource, /setPending\(true\)/);
  assert.match(composeSource, /setPending\(false\)/);
  assert.match(
    composeSource,
    /const fieldsDisabled =\s*!sessionReady \|\| pending \|\| unresolved !== null/,
  );
  assert.ok(
    (composeSource.match(/disabled=\{fieldsDisabled\}/g) ?? []).length >= 2,
    "recipient and message must disable while pending or retained",
  );
  assert.match(
    composeSource,
    /type="submit"[\s\S]*disabled=\{pending \|\| !sessionReady\}/,
  );
  assert.equal(
    composeSource.match(/await sendA2AMessageAttempt\(/g)?.length,
    1,
  );
  assert.doesNotMatch(composeSource, /\buseMutation\b|\bsetTimeout\b/);
});

test("compose renders exact STORED sequence evidence and typed safe failures", () => {
  assert.match(composeSource, /sendOutcomeText\(outcome\)/);
  assert.match(composeSource, /role="status"/);
  assert.match(composeSource, /aria-live="polite"/);
  assert.match(composeSource, /sendFailureView\(error\)/);
  assert.match(composeSource, /role="alert"/);
  assert.doesNotMatch(
    composeSource,
    /A2A_GATEWAY_TOKEN|A2A_GATEWAY_URL|Bearer\s/,
  );
});

test("compose retains and exposes one packet ID after an unknown outcome", () => {
  assert.match(composeSource, /unresolved/);
  assert.match(composeSource, /if \(unresolved\) return/);
  assert.match(composeSource, /failureView\.outcome === "UNKNOWN"/);
  assert.match(composeSource, /setUnresolved\(descriptor\)/);
  assert.match(composeSource, /persistUnresolved\(descriptor\)/);
  assert.match(composeSource, /failure\.packetId/);
  assert.match(composeSource, /Check status/);
  assert.doesNotMatch(composeSource, /\buseMutation\b|\bsetTimeout\b/);
});

test("reload restores safe session descriptor and only queries status", () => {
  assert.match(composeSource, /\buseEffect\b/);
  assert.match(composeSource, /sessionReady/);
  assert.match(composeSource, /if \(!sessionReady\) return/);
  assert.match(
    composeSource,
    /parseA2ASendUnresolved\(\s*sessionStorage\.getItem\(/,
  );
  assert.match(composeSource, /checkA2ASendStatus\(/);
  assert.match(
    composeSource,
    /sessionStorage\.setItem\([\s\S]*serializeA2ASendUnresolved\(/,
  );
  assert.match(composeSource, /status === "STORED"/);
  assert.match(composeSource, /sessionStorage\.removeItem\(/);
  assert.match(composeSource, /Dismiss local status/);
  assert.match(composeSource, /if \(unresolved\) return/);
  assert.doesNotMatch(
    composeSource,
    /sessionStorage\.setItem\([\s\S]{0,160}\b(?:message|body|token)\b/,
  );
});

test("local dismissal never implies the durable record is resend-safe", () => {
  assert.match(composeSource, /Dismiss local status/);
  assert.match(composeSource, /server receipt remains/i);
  assert.match(composeSource, /do not resend/i);
  assert.doesNotMatch(composeSource, /Discard unresolved packet/);
});
