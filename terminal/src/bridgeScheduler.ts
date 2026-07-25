export type BridgeRequest = {
  id: string;
  type: string;
  [key: string]: unknown;
};

/**
 * Keeps slow, read-only telemetry from starving operator requests.
 *
 * The Python bridge is deliberately serial.  We therefore admit at most one
 * background request to its stdin and coalesce newer requests by type while it
 * is busy.  Foreground requests do not pass through this queue and can become
 * the bridge's next request as soon as the active background probe completes.
 */
export class BridgeBackgroundScheduler {
  private active: BridgeRequest | null = null;
  private readonly queuedByType = new Map<string, BridgeRequest>();

  enqueue(request: BridgeRequest): BridgeRequest | null {
    if (this.active === null) {
      this.active = request;
      return request;
    }
    this.queuedByType.set(request.type, request);
    return null;
  }

  complete(requestId: string): BridgeRequest | null {
    if (this.active?.id !== requestId) {
      return null;
    }
    this.active = null;
    const nextEntry = this.queuedByType.entries().next();
    if (nextEntry.done) {
      return null;
    }
    const [type, next] = nextEntry.value;
    this.queuedByType.delete(type);
    this.active = next;
    return next;
  }

  reset(): void {
    this.active = null;
    this.queuedByType.clear();
  }

  snapshot(): {activeId: string | null; queuedTypes: string[]} {
    return {
      activeId: this.active?.id ?? null,
      queuedTypes: [...this.queuedByType.keys()],
    };
  }
}
