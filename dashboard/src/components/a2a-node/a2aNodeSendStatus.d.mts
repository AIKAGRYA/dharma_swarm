export type A2ASendResolutionStatus =
  | "PENDING"
  | "UNKNOWN"
  | "STORED";

export interface A2ASendUnresolvedDescriptor {
  packet_id: string;
  target: string;
  status: "PENDING" | "UNKNOWN";
}

export interface A2ASendStatusReceipt {
  ok: true;
  subject: string;
  seq: number;
  from: string;
  packet_id: string;
  evidence_tier: "STORED";
}

export type A2ASendStatusResult =
  | A2ASendUnresolvedDescriptor
  | {
      packet_id: string;
      target: string;
      status: "STORED";
      receipt: A2ASendStatusReceipt;
    };

export const A2A_SEND_SESSION_KEY: string;

export function parseA2ASendUnresolved(
  value: string | null,
): A2ASendUnresolvedDescriptor | null;

export function serializeA2ASendUnresolved(
  value: A2ASendUnresolvedDescriptor,
): string;

export class A2AStatusRequestError extends Error {
  readonly kind: string;
  readonly status: number | null;
}

export function requestA2ASendStatus(
  packetId: string,
  options?: { fetcher?: typeof fetch },
): Promise<A2ASendStatusResult>;
