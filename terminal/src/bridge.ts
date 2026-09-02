import {execFileSync, spawn, type ChildProcess} from "node:child_process";
import {
  constants as fsConstants,
  closeSync,
  createWriteStream,
  existsSync,
  fchmodSync,
  lstatSync,
  mkdirSync,
  openSync,
  type WriteStream,
} from "node:fs";
import path from "node:path";
import {createInterface} from "node:readline";
import {fileURLToPath} from "node:url";

import {BridgeBackgroundScheduler, type BridgeRequest} from "./bridgeScheduler.ts";

export type BridgeEvent = Record<string, unknown>;
export type BridgeProcessFactory = () => ChildProcess;
export type GitCommonDirResolver = (repoRoot: string) => string | undefined;

const THIS_DIR = path.dirname(fileURLToPath(import.meta.url));
const TERMINAL_ROOT = path.resolve(THIS_DIR, "..");
const REPO_ROOT = path.resolve(TERMINAL_ROOT, "..");

function bridgeStderrLogPath(env: NodeJS.ProcessEnv = process.env): string | undefined {
  const stateDir = env.DHARMA_TERMINAL_SUPERVISOR_STATE_DIR?.trim()
    || env.DHARMA_TERMINAL_STATE_DIR?.trim()
    || env.DHARMA_TERMINAL_TUI_STATE_DIR?.trim();
  return stateDir ? path.join(path.resolve(stateDir), "bridge.stderr.log") : undefined;
}

function openBridgeStderrLog(logPath: string | undefined): WriteStream | undefined {
  if (!logPath) {
    return undefined;
  }
  try {
    mkdirSync(path.dirname(logPath), {recursive: true, mode: 0o700});
    if (existsSync(logPath)) {
      const current = lstatSync(logPath);
      if (current.isSymbolicLink() || !current.isFile()) {
        return undefined;
      }
    }
    const fd = openSync(
      logPath,
      fsConstants.O_APPEND | fsConstants.O_CREAT | fsConstants.O_WRONLY | fsConstants.O_NOFOLLOW,
      0o600,
    );
    fchmodSync(fd, 0o600);
    let stream: WriteStream;
    try {
      stream = createWriteStream(logPath, {fd, autoClose: true});
    } catch (error) {
      closeSync(fd);
      throw error;
    }
    stream.on("error", () => {
      // An unavailable diagnostic path is not application truth and never
      // becomes an alternate-screen event.
    });
    return stream;
  } catch {
    return undefined;
  }
}

function routeBridgeStderr(child: ChildProcess, env: NodeJS.ProcessEnv = process.env): () => void {
  if (!child.stderr) {
    return () => {};
  }
  const stderr = child.stderr;
  const log = openBridgeStderrLog(bridgeStderrLogPath(env));
  let released = false;
  const onData = (chunk: Buffer | string): void => {
    if (log && !log.destroyed) {
      log.write(chunk);
    }
  };
  const onError = (): void => {
    // The transport lifecycle reports stdout/stdin failures. Stderr is an
    // append-only diagnostic lane and intentionally has no UI projection.
  };
  stderr.on("data", onData);
  stderr.on("error", onError);
  return () => {
    if (released) {
      return;
    }
    released = true;
    stderr.off("data", onData);
    stderr.off("error", onError);
    if (log && !log.destroyed) {
      log.end();
    }
  };
}

function resolveGitCommonDir(repoRoot: string): string | undefined {
  try {
    const commonDir = execFileSync(
      "git",
      ["-C", repoRoot, "rev-parse", "--path-format=absolute", "--git-common-dir"],
      // Bounded: a hung mount must degrade to the next candidate, never block
      // the bridge spawn (and with it the whole UI) indefinitely.
      {encoding: "utf8", stdio: ["ignore", "pipe", "ignore"], timeout: 1_500},
    ).trim();
    return commonDir || undefined;
  } catch {
    return undefined;
  }
}

export function resolvePython(
  env: NodeJS.ProcessEnv = process.env,
  repoRoot = REPO_ROOT,
  pathExists: (candidate: string) => boolean = existsSync,
  gitCommonDir: GitCommonDirResolver = resolveGitCommonDir,
): string {
  const configured = env.DHARMA_PYTHON?.trim();
  if (configured) {
    return configured;
  }

  const commonDir = gitCommonDir(repoRoot);
  const canonicalCheckout = commonDir && path.basename(commonDir) === ".git"
    ? path.dirname(commonDir)
    : "";
  const candidates = [
    path.join(repoRoot, ".venv", "bin", "python"),
    env.VIRTUAL_ENV?.trim() ? path.join(env.VIRTUAL_ENV.trim(), "bin", "python") : "",
    canonicalCheckout ? path.join(canonicalCheckout, ".venv", "bin", "python") : "",
    // Worktrees intentionally do not duplicate the large Python environment.
    // Fall back to the canonical checkout's venv when Helm runs from a sibling
    // worktree such as dharma_helm_build. Git's common directory handles the
    // repository's nested ~/worktrees/<repo>/<stem>_YYYYMMDD estate layout.
    path.join(path.dirname(repoRoot), "dharma_swarm", ".venv", "bin", "python"),
  ];
  for (const candidate of candidates) {
    if (candidate && pathExists(candidate)) {
      return candidate;
    }
  }

  return "python3";
}

export class DharmaBridge {
  private child: ChildProcess;
  private nextId = 1;
  private alive = false;
  private closed = false;
  private stderrCleanup?: () => void;
  private readonly onEvent: (event: BridgeEvent) => void;
  private readonly processFactory: BridgeProcessFactory;
  private readonly backgroundScheduler = new BridgeBackgroundScheduler();

  constructor(onEvent: (event: BridgeEvent) => void, processFactory?: BridgeProcessFactory) {
    this.onEvent = onEvent;
    this.processFactory = processFactory ?? (() => spawn(resolvePython(), ["-m", "dharma_swarm.terminal_bridge", "stdio"], {
      cwd: REPO_ROOT,
      env: process.env,
      stdio: ["pipe", "pipe", "pipe"],
    }));
    this.child = this.spawnChild();
  }

  private spawnChild(): ChildProcess {
    const child = this.processFactory();
    this.alive = true;
    const releaseStderr = routeBridgeStderr(child);
    this.stderrCleanup = releaseStderr;

    if (!child.stdout || !child.stdin) {
      releaseStderr();
      this.stderrCleanup = undefined;
      throw new Error("bridge child process streams are unavailable");
    }

    const reader = createInterface({input: child.stdout});
    reader.on("line", (line) => {
      // A terminated child can still flush buffered stdout after its successor
      // has started. Never let an old runtime epoch reach state projection or
      // complete the new child's background request.
      if (this.closed || child !== this.child || !this.alive) {
        return;
      }
      const trimmed = line.trim();
      if (!trimmed) {
        return;
      }
      try {
        const event = JSON.parse(trimmed) as BridgeEvent;
        try {
          this.onEvent(event);
        } finally {
          this.releaseBackgroundRequest(event);
        }
      } catch {
        this.failTransport(child, "invalid_bridge_json", trimmed);
      }
    });
    child.on("exit", (code, signal) => {
      releaseStderr();
      if (this.stderrCleanup === releaseStderr) {
        this.stderrCleanup = undefined;
      }
      if (this.closed || child !== this.child || !this.alive) {
        return;
      }
      this.alive = false;
      this.backgroundScheduler.reset();
      this.onEvent({
        type: "bridge.error",
        code: "bridge_exit",
        message: `bridge exited (${code ?? "null"}${signal ? `, ${signal}` : ""})`,
      });
    });
    child.on("error", (error) => {
      this.failTransport(child, "bridge_spawn_error", error.message);
    });
    child.stdin.on("error", (error) => {
      this.failTransport(child, "bridge_stdin_error", error.message);
    });
    return child;
  }

  private ensureChild(): void {
    if (this.closed) {
      throw new Error("bridge is closed");
    }
    if (this.alive && this.child.stdin && !this.child.stdin.destroyed) {
      return;
    }
    this.backgroundScheduler.reset();
    this.child = this.spawnChild();
  }

  send(type: string, payload: Record<string, unknown> = {}): string {
    const id = String(this.nextId++);
    const request = {...payload, id, type};
    this.writeRequest(request);
    return id;
  }

  sendBackground(type: string, payload: Record<string, unknown> = {}): string {
    this.ensureChild();
    const id = String(this.nextId++);
    const request: BridgeRequest = {...payload, id, type};
    const admitted = this.backgroundScheduler.enqueue(request);
    if (admitted) {
      this.writeRequest(admitted);
    }
    return id;
  }

  private writeRequest(request: BridgeRequest): void {
    this.ensureChild();
    if (!this.child.stdin || this.child.stdin.destroyed) {
      this.failTransport(this.child, "bridge_stdin_unavailable", "bridge stdin is unavailable");
      return;
    }
    try {
      this.child.stdin.write(`${JSON.stringify(request)}\n`);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      this.failTransport(this.child, "bridge_send_failed", message);
    }
  }

  private failTransport(child: ChildProcess, code: string, message: string): void {
    if (this.closed || child !== this.child || !this.alive) {
      return;
    }
    this.alive = false;
    this.backgroundScheduler.reset();
    this.stderrCleanup?.();
    this.stderrCleanup = undefined;
    if (!child.killed) {
      child.kill("SIGTERM");
    }
    this.onEvent({type: "bridge.error", code, message});
  }

  private releaseBackgroundRequest(event: BridgeEvent): void {
    const eventType = String(event.type ?? "");
    const requestId = String(event.request_id ?? "");
    if (
      !requestId ||
      !(
        eventType.endsWith(".result")
        || eventType === "helm.on_call_projection"
        || eventType === "bridge.error"
        || eventType === "error"
      )
    ) {
      return;
    }
    const next = this.backgroundScheduler.complete(requestId);
    if (next) {
      this.writeRequest(next);
    }
  }

  close(): void {
    if (this.closed) {
      return;
    }
    this.closed = true;
    this.alive = false;
    this.backgroundScheduler.reset();
    this.stderrCleanup?.();
    this.stderrCleanup = undefined;
    if (!this.child.killed) {
      this.child.kill("SIGTERM");
    }
  }
}
