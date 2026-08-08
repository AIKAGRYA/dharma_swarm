// Shared bun test preload (wired via bunfig.toml [test].preload).
// Hermeticity guard: every suite runs with both terminal state-dir env vars
// pointed at disposable temp sandboxes, so no test can read or write the real
// ~/.dharma/terminal_supervisor tree (src/persistence.ts scans it whenever the
// env vars are unset). Re-applied before every test because app.test.ts and
// persistence.test.ts afterEach hooks delete both vars mid-process.
import {beforeEach} from "bun:test";
import {mkdtempSync} from "node:fs";
import os from "node:os";
import path from "node:path";

const SANDBOX_STATE_DIR = mkdtempSync(path.join(os.tmpdir(), "dharma-terminal-test-state-"));
const SANDBOX_SUPERVISOR_STATE_DIR = mkdtempSync(path.join(os.tmpdir(), "dharma-terminal-test-supervisor-"));

function applyStateDirSandbox(): void {
  process.env.DHARMA_TERMINAL_STATE_DIR = SANDBOX_STATE_DIR;
  process.env.DHARMA_TERMINAL_SUPERVISOR_STATE_DIR = SANDBOX_SUPERVISOR_STATE_DIR;
}

applyStateDirSandbox();
beforeEach(applyStateDirSandbox);
