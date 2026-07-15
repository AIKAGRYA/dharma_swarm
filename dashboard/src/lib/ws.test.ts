import assert from "node:assert/strict";
import test from "node:test";

import { DharmaSocket } from "./ws";

test("DharmaSocket bootstraps an HttpOnly session before opening", async () => {
  const originalWebSocket = globalThis.WebSocket;
  const calls: Array<{ url: string; protocols?: string | string[] }> = [];
  const order: string[] = [];

  class FakeWebSocket {
    static readonly OPEN = 1;
    static readonly CLOSED = 3;
    readyState = FakeWebSocket.OPEN;
    onopen: (() => void) | null = null;
    onmessage: ((event: MessageEvent) => void) | null = null;
    onclose: ((event: CloseEvent) => void) | null = null;
    onerror: ((event: Event) => void) | null = null;

    constructor(url: string | URL, protocols?: string | string[]) {
      order.push("socket");
      calls.push({ url: String(url), protocols });
    }

    close(): void {}
    send(): void {}
  }

  globalThis.WebSocket = FakeWebSocket as unknown as typeof WebSocket;
  try {
    new DharmaSocket("chat/session/dash-test-session", {
      sessionBootstrap: async () => {
        order.push("bootstrap");
        return true;
      },
    }).connect();
    await new Promise((resolve) => setImmediate(resolve));

    assert.equal(calls.length, 1);
    assert.deepEqual(order, ["bootstrap", "socket"]);
    assert.doesNotMatch(calls[0]!.url, /credential|token=/);
    assert.equal(calls[0]!.protocols, undefined);
  } finally {
    globalThis.WebSocket = originalWebSocket;
  }
});

test("superseded bootstraps and sockets cannot create duplicate connections", async () => {
  const originalWebSocket = globalThis.WebSocket;
  const sockets: FakeWebSocket[] = [];
  const closes: Array<{ code: number; reason: string }> = [];
  let bootstrapCalls = 0;
  let resolveFirst!: (ready: boolean) => void;

  class FakeWebSocket {
    static readonly OPEN = 1;
    static readonly CLOSED = 3;
    readyState = FakeWebSocket.OPEN;
    onopen: (() => void) | null = null;
    onmessage: ((event: MessageEvent) => void) | null = null;
    onclose: ((event: CloseEvent) => void) | null = null;
    onerror: ((event: Event) => void) | null = null;

    constructor() {
      sockets.push(this);
    }

    close(): void {}
    send(): void {}
  }

  const sessionBootstrap = (): Promise<boolean> => {
    bootstrapCalls += 1;
    if (bootstrapCalls === 1) {
      return new Promise((resolve) => {
        resolveFirst = resolve;
      });
    }
    return Promise.resolve(true);
  };

  globalThis.WebSocket = FakeWebSocket as unknown as typeof WebSocket;
  try {
    const socket = new DharmaSocket("chat/session/generation-guard", {
      sessionBootstrap,
      baseDelay: 0,
      maxDelay: 0,
      onClose: (code, reason) => closes.push({ code, reason }),
    });

    socket.connect();
    socket.close();
    socket.connect();
    await new Promise((resolve) => setImmediate(resolve));
    resolveFirst(true);
    await new Promise((resolve) => setImmediate(resolve));
    assert.equal(sockets.length, 1, "superseded bootstrap created a socket");

    const stale = sockets[0]!;
    socket.connect();
    await new Promise((resolve) => setImmediate(resolve));
    assert.equal(sockets.length, 2);
    assert.deepEqual(closes, [{ code: 1000, reason: "client_reconnect" }]);
    stale.onclose?.({ code: 1006, reason: "stale" } as CloseEvent);
    await new Promise((resolve) => setTimeout(resolve, 5));
    assert.equal(sockets.length, 2, "stale close scheduled a reconnect");
    assert.equal(closes.length, 1, "stale close emitted a duplicate callback");
    socket.close();
    assert.deepEqual(closes, [
      { code: 1000, reason: "client_reconnect" },
      { code: 1000, reason: "client_close" },
    ]);
  } finally {
    globalThis.WebSocket = originalWebSocket;
  }
});
