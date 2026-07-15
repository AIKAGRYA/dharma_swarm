/**
 * DHARMA COMMAND -- Reconnecting WebSocket connection factory.
 *
 * Usage:
 *   const ws = new DharmaSocket("swarm", { onMessage: (evt) => ... });
 *   ws.connect();
 *   // later:
 *   ws.close();
 */

import { wsBaseUrl } from "./api";
import type { WsEvent } from "./types";

async function prepareDashboardWebSocketSession(): Promise<boolean> {
  if (typeof window === "undefined") return true;
  try {
    const response = await fetch("/dharma-internal/ws-auth", {
      method: "POST",
      credentials: "same-origin",
      cache: "no-store",
    });
    return response.ok;
  } catch {
    return false;
  }
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface DharmaSocketOptions {
  /** WebSocket channel / topic (appended to the URL path). */
  channel?: string;
  /** Called on every parsed message. */
  onMessage?: (event: WsEvent) => void;
  /** Called when connection opens. */
  onOpen?: () => void;
  /** Called when connection closes. */
  onClose?: (code: number, reason: string) => void;
  /** Called on error. */
  onError?: (error: Event) => void;
  /** Max reconnect attempts (default 10). 0 = infinite. */
  maxRetries?: number;
  /** Base delay in ms before first reconnect (default 1000). Doubles each attempt. */
  baseDelay?: number;
  /** Maximum delay between retries in ms (default 30000). */
  maxDelay?: number;
  /** Override the same-origin session bootstrap (primarily for tests). */
  sessionBootstrap?: () => Promise<boolean>;
}

// ---------------------------------------------------------------------------
// DharmaSocket
// ---------------------------------------------------------------------------

export class DharmaSocket {
  private ws: WebSocket | null = null;
  private generation = 0;
  private retries = 0;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private intentionallyClosed = false;
  private readonly url: string;
  private readonly sessionBootstrap: () => Promise<boolean>;
  private readonly opts: Required<
    Pick<DharmaSocketOptions, "maxRetries" | "baseDelay" | "maxDelay">
  > &
    DharmaSocketOptions;

  constructor(channel: string, options: DharmaSocketOptions = {}) {
    const base = wsBaseUrl();
    const ch = channel.startsWith("/") ? channel : `/${channel}`;
    this.url = `${base}/ws${ch}`;
    this.sessionBootstrap =
      options.sessionBootstrap ?? prepareDashboardWebSocketSession;
    this.opts = {
      maxRetries: 10,
      baseDelay: 1000,
      maxDelay: 30_000,
      ...options,
      channel,
    };
  }

  /** Open the WebSocket connection. */
  connect(): void {
    const generation = ++this.generation;
    this.intentionallyClosed = false;
    this._clearTimer();
    const previous = this.ws;
    this.ws = null;
    if (previous) {
      previous.close(1000, "client_reconnect");
      this.opts.onClose?.(1000, "client_reconnect");
    }
    this._open(generation);
  }

  /** Gracefully close and stop reconnecting. */
  close(): void {
    this.generation += 1;
    this.intentionallyClosed = true;
    this._clearTimer();
    const current = this.ws;
    this.ws = null;
    if (current) {
      current.close(1000, "client_close");
      this.opts.onClose?.(1000, "client_close");
    }
  }

  /** Send a JSON-serializable payload. */
  send(data: unknown): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    }
  }

  /** Current readyState. */
  get readyState(): number {
    return this.ws?.readyState ?? WebSocket.CLOSED;
  }

  get connected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  // -------------------------------------------------------------------------
  // Internals
  // -------------------------------------------------------------------------

  private _open(generation: number): void {
    void this._openAfterSessionBootstrap(generation);
  }

  private async _openAfterSessionBootstrap(generation: number): Promise<void> {
    if (!(await this.sessionBootstrap())) {
      if (generation === this.generation && !this.intentionallyClosed) {
        this._scheduleReconnect(generation);
      }
      return;
    }
    if (generation !== this.generation || this.intentionallyClosed) return;
    let socket: WebSocket;
    try {
      socket = new WebSocket(this.url);
      this.ws = socket;
    } catch {
      this._scheduleReconnect(generation);
      return;
    }

    socket.onopen = () => {
      if (generation !== this.generation || this.ws !== socket) return;
      this.retries = 0;
      this.opts.onOpen?.();
    };

    socket.onmessage = (raw: MessageEvent) => {
      if (generation !== this.generation || this.ws !== socket) return;
      try {
        const parsed: WsEvent = JSON.parse(String(raw.data));
        this.opts.onMessage?.(parsed);
      } catch {
        // Non-JSON messages are silently dropped.
      }
    };

    socket.onclose = (ev: CloseEvent) => {
      if (generation !== this.generation || this.ws !== socket) return;
      this.ws = null;
      this.opts.onClose?.(ev.code, ev.reason);
      if (!this.intentionallyClosed) {
        this._scheduleReconnect(generation);
      }
    };

    socket.onerror = (ev: Event) => {
      if (generation !== this.generation || this.ws !== socket) return;
      this.opts.onError?.(ev);
    };
  }

  private _scheduleReconnect(generation: number): void {
    if (generation !== this.generation || this.intentionallyClosed) return;
    const { maxRetries, baseDelay, maxDelay } = this.opts;

    if (maxRetries > 0 && this.retries >= maxRetries) {
      return; // Give up.
    }

    const jitter = Math.random() * 500;
    const delay = Math.min(baseDelay * 2 ** this.retries + jitter, maxDelay);
    this.retries += 1;

    this._clearTimer();
    this.timer = setTimeout(() => {
      if (generation === this.generation && !this.intentionallyClosed) {
        this._open(generation);
      }
    }, delay);
  }

  private _clearTimer(): void {
    if (this.timer != null) {
      clearTimeout(this.timer);
      this.timer = null;
    }
  }
}
