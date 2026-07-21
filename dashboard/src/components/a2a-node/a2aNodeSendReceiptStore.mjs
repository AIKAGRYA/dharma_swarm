import { createHash, randomUUID } from "node:crypto";
import {
  mkdir,
  readdir,
  rename,
  rm,
  rmdir,
  unlink,
} from "node:fs/promises";
import { join } from "node:path";
import {
  isRecord,
  observed,
  openReceiptRoot,
  packetPaths,
  provisionReceiptRoot,
  readSafeJson,
  receiptTimestamp,
  resolveReceiptStaleAfterMs,
  safePacketDirectory,
  SendReceiptStaleLockError,
  SendReceiptStoreError,
  syncDirectory,
  validateOwner,
  validateUuid,
  withPacketLock,
  writeExclusive,
} from "./a2aNodeSendReceiptFs.mjs";
import {
  pendingIsStale,
  publicStatus,
  recoveredUnknownState,
  storedResult,
  unknownError,
} from "./a2aNodeSendReceiptState.mjs";

const STATE_FILE = "state.json";

export {
  provisionReceiptRoot,
  resolveReceiptStaleAfterMs,
  SendReceiptStoreError,
};

export function requestFingerprint(input) {
  validateUuid(input?.packet_id);
  return createHash("sha256")
    .update(JSON.stringify([input.to, input.body]), "utf8")
    .digest("hex");
}

async function withTombstoneFallback(
  root,
  packetId,
  options,
  action,
  fallback,
) {
  try {
    return await withPacketLock(root, packetId, options, action);
  } catch (error) {
    if (error instanceof SendReceiptStaleLockError) {
      return fallback();
    }
    throw error;
  }
}

async function stateWithoutLock(root, paths) {
  if (!(await safePacketDirectory(paths.packetDirectory, root))) {
    return null;
  }
  return readSafeJson(paths.statePath);
}

function tombstoneStatus(state, packetId) {
  const status = publicStatus(state, packetId);
  if (status.state === "stored") return status;
  return {
    state: "unknown",
    status: "UNKNOWN",
    packet_id: packetId,
    target: status.target,
    error: unknownError(
      { kind: "upstream", status: 504 },
      packetId,
    ),
  };
}

async function atomicStateWrite(root, paths, state, options) {
  const temporary = join(
    paths.packetDirectory,
    `.state-${randomUUID()}.tmp`,
  );
  try {
    await writeExclusive(
      temporary,
      state,
      "transition:file-fsync",
      options,
    );
    await rename(temporary, paths.statePath);
    observed(options, "transition:rename");
    await syncDirectory(
      paths.packetDirectory,
      "transition:packet-dir-fsync",
      options,
    );
    await syncDirectory(root, "transition:root-fsync", options);
  } finally {
    await rm(temporary, { force: true }).catch(() => undefined);
  }
}

async function recoverPending(
  root,
  paths,
  current,
  packetId,
  force,
  options,
) {
  if (
    !isRecord(current) ||
    current.state !== "PENDING" ||
    (!force && !pendingIsStale(current, options))
  ) {
    return current;
  }
  const recovered = recoveredUnknownState(
    current,
    packetId,
    options,
  );
  await atomicStateWrite(root, paths, recovered, options);
  return recovered;
}

async function createPacket(root, paths, state, options) {
  const staging = join(
    root,
    `.${state.packet_id}-${randomUUID()}.tmp`,
  );
  try {
    await mkdir(staging, { mode: 0o700 });
    await writeExclusive(
      join(staging, STATE_FILE),
      state,
      "claim:file-fsync",
      options,
    );
    await syncDirectory(
      staging,
      "claim:staging-dir-fsync",
      options,
    );
    await rename(staging, paths.packetDirectory);
    observed(options, "claim:rename");
    await syncDirectory(root, "claim:root-fsync", options);
  } finally {
    await rm(staging, { recursive: true, force: true }).catch(
      () => undefined,
    );
  }
}

export async function claimPacket(
  receiptDir,
  input,
  options = {},
) {
  validateUuid(input?.packet_id);
  resolveReceiptStaleAfterMs(options.staleAfterMs);
  const root = await openReceiptRoot(receiptDir);
  const paths = packetPaths(root, input.packet_id);
  return withTombstoneFallback(
    root,
    input.packet_id,
    options,
    async () => {
      if (await safePacketDirectory(paths.packetDirectory, root)) {
        let existing = await readSafeJson(paths.statePath);
        existing = await recoverPending(
          root,
          paths,
          existing,
          input.packet_id,
          false,
          options,
        );
        if (
          isRecord(existing) &&
          existing.packet_id === input.packet_id &&
          existing.request_hash !== requestFingerprint(input)
        ) {
          return { state: "conflict" };
        }
        const status = publicStatus(existing, input.packet_id);
        if (status.state === "stored") {
          return { state: "stored", result: status.receipt };
        }
        if (status.state === "pending") return status;
        return { state: "unknown", error: status.error };
      }
      const ownerToken = randomUUID();
      const now = receiptTimestamp(options);
      await createPacket(
        root,
        paths,
        {
          version: 1,
          packet_id: input.packet_id,
          request_hash: requestFingerprint(input),
          to: input.to,
          state: "PENDING",
          owner_token: ownerToken,
          created_at: now,
          updated_at: now,
        },
        options,
      );
      return { state: "owner", ownerToken };
    },
    async () => {
      const existing = await stateWithoutLock(root, paths);
      if (
        isRecord(existing) &&
        typeof existing.request_hash === "string" &&
        existing.request_hash !== requestFingerprint(input)
      ) {
        return { state: "conflict" };
      }
      const status = tombstoneStatus(existing, input.packet_id);
      if (status.state === "stored") {
        return { state: "stored", result: status.receipt };
      }
      return { state: "unknown", error: status.error };
    },
  );
}

async function transitionPacket(
  receiptDir,
  input,
  terminal,
  ownerToken,
  options,
) {
  validateUuid(input?.packet_id);
  validateOwner(ownerToken);
  resolveReceiptStaleAfterMs(options?.staleAfterMs);
  const root = await openReceiptRoot(receiptDir);
  const paths = packetPaths(root, input.packet_id);
  return withTombstoneFallback(
    root,
    input.packet_id,
    options,
    async () => {
      if (!(await safePacketDirectory(paths.packetDirectory, root))) {
        return { state: "missing" };
      }
      let current = await readSafeJson(paths.statePath);
      current = await recoverPending(
        root,
        paths,
        current,
        input.packet_id,
        false,
        options,
      );
      const status = publicStatus(current, input.packet_id);
      if (status.state === "stored") {
        return {
          state: "stored",
          result: status.receipt,
          transitioned: false,
        };
      }
      if (status.state === "unknown") {
        return {
          state: "unknown",
          error: status.error,
          transitioned: false,
        };
      }
      if (
        !isRecord(current) ||
        current.owner_token !== ownerToken ||
        current.request_hash !== requestFingerprint(input)
      ) {
        return { state: "pending", transitioned: false };
      }
      await atomicStateWrite(
        root,
        paths,
        {
          version: 1,
          packet_id: input.packet_id,
          request_hash: current.request_hash,
          to: input.to,
          state: terminal.state,
          created_at: current.created_at,
          updated_at: receiptTimestamp(options),
          ...terminal.payload,
        },
        options,
      );
      return terminal.result;
    },
    async () => {
      const status = tombstoneStatus(
        await stateWithoutLock(root, paths),
        input.packet_id,
      );
      if (status.state === "stored") {
        return {
          state: "stored",
          result: status.receipt,
          transitioned: false,
        };
      }
      return {
        state: "unknown",
        error: status.error,
        transitioned: false,
      };
    },
  );
}

export async function persistStored(
  receiptDir,
  input,
  result,
  ownerToken,
  options = {},
) {
  validateUuid(input?.packet_id);
  const projected = storedResult(result, input.packet_id, input.to);
  if (!projected) {
    throw new SendReceiptStoreError("Stored receipt is invalid");
  }
  return transitionPacket(
    receiptDir,
    input,
    {
      state: "STORED",
      payload: { result: projected },
      result: {
        state: "stored",
        result: projected,
        transitioned: true,
      },
    },
    ownerToken,
    options,
  );
}

export async function persistUnknown(
  receiptDir,
  input,
  error,
  ownerToken,
  options = {},
) {
  validateUuid(input?.packet_id);
  const safeError = unknownError(error, input.packet_id);
  return transitionPacket(
    receiptDir,
    input,
    {
      state: "UNKNOWN",
      payload: { error: safeError },
      result: {
        state: "unknown",
        error: safeError,
        transitioned: true,
      },
    },
    ownerToken,
    options,
  );
}

export async function releasePacket(
  receiptDir,
  packetId,
  ownerToken,
  options = {},
) {
  validateUuid(packetId);
  validateOwner(ownerToken);
  resolveReceiptStaleAfterMs(options.staleAfterMs);
  const root = await openReceiptRoot(receiptDir);
  const paths = packetPaths(root, packetId);
  return withTombstoneFallback(
    root,
    packetId,
    options,
    async () => {
      if (!(await safePacketDirectory(paths.packetDirectory, root))) {
        return false;
      }
      let current = await readSafeJson(paths.statePath);
      current = await recoverPending(
        root,
        paths,
        current,
        packetId,
        false,
        options,
      );
      if (
        !isRecord(current) ||
        current.state !== "PENDING" ||
        current.owner_token !== ownerToken
      ) {
        return false;
      }
      const entries = await readdir(paths.packetDirectory);
      if (entries.length !== 1 || entries[0] !== STATE_FILE) {
        throw new SendReceiptStoreError(
          "Send receipt packet is unsafe",
        );
      }
      await unlink(paths.statePath);
      observed(options, "removal:state-unlink");
      await syncDirectory(
        paths.packetDirectory,
        "removal:packet-dir-fsync",
        options,
      );
      await rmdir(paths.packetDirectory);
      observed(options, "removal:packet-rmdir");
      await syncDirectory(root, "removal:root-fsync", options);
      return true;
    },
    () => false,
  );
}

export async function getPacketStatus(
  receiptDir,
  packetId,
  options = {},
) {
  validateUuid(packetId);
  resolveReceiptStaleAfterMs(options.staleAfterMs);
  const root = await openReceiptRoot(receiptDir);
  const paths = packetPaths(root, packetId);
  return withTombstoneFallback(
    root,
    packetId,
    options,
    async () => {
      if (!(await safePacketDirectory(paths.packetDirectory, root))) {
        return {
          state: "missing",
          status: "NOT_FOUND",
          packet_id: packetId,
        };
      }
      let state = await readSafeJson(paths.statePath);
      state = await recoverPending(
        root,
        paths,
        state,
        packetId,
        false,
        options,
      );
      return publicStatus(state, packetId);
    },
    async () =>
      tombstoneStatus(
        await stateWithoutLock(root, paths),
        packetId,
      ),
  );
}
