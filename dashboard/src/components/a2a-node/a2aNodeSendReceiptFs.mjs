import { randomUUID } from "node:crypto";
import {
  lstat,
  mkdir,
  open,
  readFile,
  readdir,
  realpath,
  rmdir,
  unlink,
} from "node:fs/promises";
import {
  dirname,
  isAbsolute,
  join,
  parse,
  relative,
  resolve,
} from "node:path";
import {
  readStableLockSnapshot,
  stableGeneration,
  validLockOwner,
} from "./a2aNodeSendLockSnapshot.mjs";

const LOCK_OWNER_FILE = "owner.json";
const UUID =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const DEFAULT_STALE_AFTER_MS = 60_000;
const MIN_STALE_AFTER_MS = 15_000;
const MAX_STALE_AFTER_MS = 86_400_000;

export class SendReceiptStoreError extends Error {
  constructor(message = "Send receipt cache is unavailable") {
    super(message);
    this.name = "SendReceiptStoreError";
  }
}

export class SendReceiptStaleLockError extends SendReceiptStoreError {
  constructor(packetId) {
    super("Send receipt lock is a stale tombstone");
    this.name = "SendReceiptStaleLockError";
    this.packetId = packetId;
  }
}

export function isRecord(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

export function hasCode(error, code) {
  return isRecord(error) && String(error.code) === code;
}

export function observed(options, event) {
  options?.observe?.(event);
}

export function validateUuid(packetId) {
  if (typeof packetId !== "string" || !UUID.test(packetId)) {
    throw new SendReceiptStoreError("Send receipt identifier is invalid");
  }
}

export function validateOwner(ownerToken) {
  if (typeof ownerToken !== "string" || !UUID.test(ownerToken)) {
    throw new SendReceiptStoreError("Send receipt owner is invalid");
  }
}

export function resolveReceiptStaleAfterMs(value) {
  const candidate =
    value === undefined ? DEFAULT_STALE_AFTER_MS : value;
  if (
    (typeof candidate !== "number" &&
      (typeof candidate !== "string" ||
        !/^\d+$/.test(candidate))) ||
    !Number.isSafeInteger(Number(candidate)) ||
    Number(candidate) < MIN_STALE_AFTER_MS ||
    Number(candidate) > MAX_STALE_AFTER_MS
  ) {
    throw new SendReceiptStoreError(
      "Send receipt stale threshold is invalid",
    );
  }
  return Number(candidate);
}

export function receiptNow(options = {}) {
  const value = options.now ? options.now() : Date.now();
  if (!Number.isFinite(value)) {
    throw new SendReceiptStoreError("Send receipt clock is invalid");
  }
  return value;
}

export function receiptTimestamp(options = {}) {
  return new Date(receiptNow(options)).toISOString();
}

function configuredRoot(receiptDir) {
  if (
    typeof receiptDir !== "string" ||
    !isAbsolute(receiptDir)
  ) {
    throw new SendReceiptStoreError("Send receipt root is invalid");
  }
  return resolve(receiptDir);
}

async function walkDirectoriesWithoutLinks(target) {
  const root = parse(target).root;
  const parts = relative(root, target)
    .split(/[\\/]/u)
    .filter(Boolean);
  let current = root;
  const currentUid =
    typeof process.getuid === "function" ? process.getuid() : null;
  for (const part of [null, ...parts]) {
    if (part !== null) current = join(current, part);
    let info;
    try {
      info = await lstat(current);
    } catch (error) {
      if (hasCode(error, "ENOENT")) {
        throw new SendReceiptStoreError(
          "Send receipt root is not provisioned",
        );
      }
      throw error;
    }
    if (info.isSymbolicLink() || !info.isDirectory()) {
      throw new SendReceiptStoreError(
        "Send receipt root ancestry is unsafe",
      );
    }
    const trustedOwner =
      currentUid === null ||
      info.uid === 0 ||
      info.uid === currentUid;
    const writableByOthers = (info.mode & 0o022) !== 0;
    const rootOwnedSticky =
      info.uid === 0 && (info.mode & 0o1000) !== 0;
    if (
      !trustedOwner ||
      (writableByOthers && !rootOwnedSticky)
    ) {
      throw new SendReceiptStoreError(
        "Send receipt root ancestry is untrusted",
      );
    }
  }
}

export async function openReceiptRoot(receiptDir) {
  const root = configuredRoot(receiptDir);
  await walkDirectoriesWithoutLinks(root);
  const info = await lstat(root);
  const currentUid =
    typeof process.getuid === "function" ? process.getuid() : null;
  if (
    info.isSymbolicLink() ||
    !info.isDirectory() ||
    (currentUid !== null && info.uid !== currentUid) ||
    (info.mode & 0o777) !== 0o700 ||
    (await realpath(root)) !== root
  ) {
    throw new SendReceiptStoreError("Send receipt root is unsafe");
  }
  return root;
}

export async function syncDirectory(directory, event, options) {
  const handle = await open(directory, "r");
  try {
    await handle.sync();
    if (event) observed(options, event);
  } finally {
    await handle.close();
  }
}

export async function provisionReceiptRoot(receiptDir) {
  const root = configuredRoot(receiptDir);
  try {
    return await openReceiptRoot(root);
  } catch (error) {
    if (
      !(error instanceof SendReceiptStoreError) ||
      error.message !== "Send receipt root is not provisioned"
    ) {
      throw error;
    }
  }
  const parent = dirname(root);
  await walkDirectoriesWithoutLinks(parent);
  try {
    await mkdir(root, { mode: 0o700 });
  } catch (error) {
    if (!hasCode(error, "EEXIST")) throw error;
  }
  const validated = await openReceiptRoot(root);
  await syncDirectory(validated);
  await syncDirectory(parent);
  return validated;
}

export function packetPaths(root, packetId) {
  validateUuid(packetId);
  const packetDirectory = resolve(root, packetId);
  const lockDirectory = resolve(root, `.lock-${packetId}`);
  if (
    dirname(packetDirectory) !== root ||
    dirname(lockDirectory) !== root
  ) {
    throw new SendReceiptStoreError(
      "Send receipt path escaped its root",
    );
  }
  return {
    packetDirectory,
    statePath: join(packetDirectory, "state.json"),
    lockDirectory,
    lockOwnerPath: join(lockDirectory, LOCK_OWNER_FILE),
  };
}

function safeOwner(info) {
  const currentUid =
    typeof process.getuid === "function" ? process.getuid() : null;
  return currentUid === null || info.uid === currentUid;
}

export async function safePacketDirectory(path, root) {
  let info;
  try {
    info = await lstat(path);
  } catch (error) {
    if (hasCode(error, "ENOENT")) return false;
    throw error;
  }
  if (
    dirname(path) !== root ||
    info.isSymbolicLink() ||
    !info.isDirectory() ||
    !safeOwner(info) ||
    (info.mode & 0o777) !== 0o700 ||
    (await realpath(path)) !== path
  ) {
    throw new SendReceiptStoreError(
      "Send receipt packet path is unsafe",
    );
  }
  return true;
}

export async function readSafeJson(path) {
  let info;
  try {
    info = await lstat(path);
  } catch (error) {
    if (hasCode(error, "ENOENT")) return null;
    throw error;
  }
  if (
    info.isSymbolicLink() ||
    !info.isFile() ||
    !safeOwner(info) ||
    (info.mode & 0o777) !== 0o600 ||
    (await realpath(path)) !== path
  ) {
    throw new SendReceiptStoreError("Send receipt file is unsafe");
  }
  try {
    return JSON.parse(await readFile(path, "utf8"));
  } catch {
    return null;
  }
}

export async function writeExclusive(
  path,
  value,
  event,
  options,
) {
  const handle = await open(path, "wx", 0o600);
  try {
    await handle.writeFile(`${JSON.stringify(value)}\n`, "utf8");
    await handle.sync();
    if (event) observed(options, event);
  } finally {
    await handle.close();
  }
}

async function lockSnapshot(root, paths, packetId) {
  return readStableLockSnapshot(
    root,
    paths,
    packetId,
    safeOwner,
  );
}

function sameIdentity(left, right) {
  return left.dev === right.dev && left.ino === right.ino;
}

async function removeKnownLock(
  root,
  directory,
  ownerPath,
  options,
  event,
) {
  const entries = await readdir(directory);
  if (
    entries.some((entry) => entry !== LOCK_OWNER_FILE) ||
    entries.length > 1
  ) {
    throw new SendReceiptStoreError("Send receipt lock is unsafe");
  }
  if (entries.length === 1) await unlink(ownerPath);
  await syncDirectory(directory);
  await rmdir(directory);
  await syncDirectory(root);
  if (event) observed(options, event);
}

async function staleLockExists(root, paths, packetId, options) {
  const snapshot = await lockSnapshot(root, paths, packetId);
  if (!snapshot) return false;
  if (snapshot.unsafe) {
    throw new SendReceiptStoreError("Send receipt lock is unsafe");
  }
  const staleAfterMs = resolveReceiptStaleAfterMs(
    options?.staleAfterMs,
  );
  const now = receiptNow(options);
  if (now - snapshot.timestamp < staleAfterMs) return false;
  const confirmed = await lockSnapshot(root, paths, packetId);
  return Boolean(
    confirmed &&
      !confirmed.unsafe &&
      stableGeneration(snapshot.info, confirmed.info) &&
      snapshot.timestamp === confirmed.timestamp &&
      JSON.stringify(snapshot.owner) ===
        JSON.stringify(confirmed.owner) &&
      now - confirmed.timestamp >= staleAfterMs,
  );
}

async function createLock(root, paths, packetId, options) {
  const ownerToken = randomUUID();
  await mkdir(paths.lockDirectory, { mode: 0o700 });
  await writeExclusive(
    paths.lockOwnerPath,
    {
      version: 1,
      packet_id: packetId,
      owner_token: ownerToken,
      acquired_at: receiptTimestamp(options),
    },
    "lock:file-fsync",
    options,
  );
  await syncDirectory(
    paths.lockDirectory,
    "lock:dir-fsync",
    options,
  );
  await syncDirectory(root, "lock:root-fsync", options);
  return {
    ownerToken,
    info: await lstat(paths.lockDirectory),
  };
}

async function releaseOwnLock(root, paths, packetId, lock, options) {
  const snapshot = await lockSnapshot(root, paths, packetId);
  if (snapshot?.unsafe) {
    if (!sameIdentity(snapshot.info, lock.info)) return;
    throw new SendReceiptStoreError("Send receipt lock is unsafe");
  }
  if (
    !snapshot ||
    !sameIdentity(snapshot.info, lock.info) ||
    !validLockOwner(snapshot.owner, packetId) ||
    snapshot.owner.owner_token !== lock.ownerToken
  ) {
    return;
  }
  await removeKnownLock(
    root,
    paths.lockDirectory,
    paths.lockOwnerPath,
    options,
    "lock:released",
  );
}

export async function withPacketLock(
  root,
  packetId,
  options,
  action,
) {
  const paths = packetPaths(root, packetId);
  let lock = null;
  for (let attempt = 0; attempt < 200; attempt += 1) {
    try {
      lock = await createLock(root, paths, packetId, options);
      break;
    } catch (error) {
      if (!hasCode(error, "EEXIST")) throw error;
      if (await staleLockExists(root, paths, packetId, options)) {
        throw new SendReceiptStaleLockError(packetId);
      }
      await new Promise((resolveWait) => setTimeout(resolveWait, 5));
    }
  }
  if (!lock) {
    throw new SendReceiptStoreError("Send receipt packet is busy");
  }
  try {
    return await action({
      lockOwnerToken: lock.ownerToken,
    });
  } finally {
    await releaseOwnLock(root, paths, packetId, lock, options);
  }
}
