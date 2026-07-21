import {
  lstat,
  readFile,
  readdir,
  realpath,
} from "node:fs/promises";
import { dirname } from "node:path";

const LOCK_OWNER_FILE = "owner.json";
const UUID =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export function validLockOwner(value, packetId) {
  return (
    value &&
    typeof value === "object" &&
    !Array.isArray(value) &&
    Object.keys(value).length === 4 &&
    value.version === 1 &&
    value.packet_id === packetId &&
    typeof value.owner_token === "string" &&
    UUID.test(value.owner_token) &&
    typeof value.acquired_at === "string" &&
    Number.isFinite(Date.parse(value.acquired_at))
  );
}

function snapshotRace(error) {
  return ["ENOENT", "ENOTDIR", "ESTALE", "ELOOP"].includes(
    String(error?.code),
  );
}

async function snapshotOperation(operation) {
  try {
    return await operation();
  } catch (error) {
    if (snapshotRace(error)) return null;
    throw error;
  }
}

function sameIdentity(left, right) {
  return left.dev === right.dev && left.ino === right.ino;
}

export function stableGeneration(left, right) {
  return (
    sameIdentity(left, right) &&
    ["mode", "uid", "gid", "nlink", "size", "mtimeMs", "ctimeMs"].every(
      (key) => left[key] === right[key],
    )
  );
}

export async function readStableLockSnapshot(
  root,
  paths,
  packetId,
  safeOwner,
) {
  const read = (operation) => snapshotOperation(operation);
  const info = await read(() => lstat(paths.lockDirectory));
  if (!info) return null;
  if (
    dirname(paths.lockDirectory) !== root ||
    info.isSymbolicLink() ||
    !info.isDirectory() ||
    !safeOwner(info) ||
    (info.mode & 0o777) !== 0o700
  ) {
    const confirmed = await read(() => lstat(paths.lockDirectory));
    if (!confirmed || !stableGeneration(info, confirmed)) return null;
    return { unsafe: true, info };
  }

  const resolved = await read(() => realpath(paths.lockDirectory));
  const entries = await read(() => readdir(paths.lockDirectory));
  if (resolved === null || entries === null) return null;
  entries.sort();
  const ownerExpected =
    entries.length === 1 && entries[0] === LOCK_OWNER_FILE;
  const entriesSafe = entries.length === 0 || ownerExpected;
  let ownerInfo = null;
  let ownerStatSafe = false;
  let ownerResolved = null;
  let ownerText = null;
  if (ownerExpected) {
    ownerInfo = await read(() => lstat(paths.lockOwnerPath));
    if (!ownerInfo) return null;
    ownerStatSafe =
      !ownerInfo.isSymbolicLink() &&
      ownerInfo.isFile() &&
      safeOwner(ownerInfo) &&
      (ownerInfo.mode & 0o777) === 0o600;
    if (ownerStatSafe) {
      ownerResolved = await read(() => realpath(paths.lockOwnerPath));
      if (ownerResolved === null) return null;
      if (ownerResolved === paths.lockOwnerPath) {
        ownerText = await read(() => readFile(paths.lockOwnerPath, "utf8"));
        if (ownerText === null) return null;
      }
    }
  }

  const resolvedAfter = await read(() => realpath(paths.lockDirectory));
  const entriesAfter = await read(() => readdir(paths.lockDirectory));
  const ownerAfter = ownerInfo
    ? await read(() => lstat(paths.lockOwnerPath))
    : null;
  const ownerResolvedAfter = ownerStatSafe
    ? await read(() => realpath(paths.lockOwnerPath))
    : null;
  const infoAfter = await read(() => lstat(paths.lockDirectory));
  if (
    resolvedAfter === null ||
    entriesAfter === null ||
    !infoAfter ||
    !stableGeneration(info, infoAfter) ||
    resolved !== resolvedAfter ||
    entries.join("\0") !== entriesAfter.sort().join("\0") ||
    (ownerInfo &&
      (!ownerAfter ||
        !stableGeneration(ownerInfo, ownerAfter) ||
        (ownerStatSafe &&
          (ownerResolvedAfter === null ||
            ownerResolved !== ownerResolvedAfter))))
  ) {
    return null;
  }
  if (resolved !== paths.lockDirectory || !entriesSafe) {
    return { unsafe: true, info };
  }
  if (!ownerExpected) {
    return { info, owner: null, timestamp: info.mtimeMs };
  }
  if (
    !ownerStatSafe ||
    ownerResolved !== paths.lockOwnerPath ||
    ownerText === null
  ) {
    return { unsafe: true, info };
  }
  let owner = null;
  try {
    owner = JSON.parse(ownerText);
  } catch {
    // A stable malformed owner remains a fail-closed lock generation.
  }
  return {
    info,
    owner,
    timestamp: validLockOwner(owner, packetId)
      ? Date.parse(owner.acquired_at)
      : info.mtimeMs,
  };
}
