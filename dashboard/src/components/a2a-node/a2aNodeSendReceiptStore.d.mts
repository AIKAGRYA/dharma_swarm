export interface SendReceiptInput {
  to: string;
  body: string;
  packet_id: string;
}

export interface StoredSendReceipt {
  ok: true;
  subject: string;
  seq: number;
  from: string;
  packet_id: string;
  evidence_tier: "STORED";
}

export interface ReceiptOptions {
  observe?: (event: string) => void;
  staleAfterMs?: number | string;
  now?: () => number;
}

export class SendReceiptStoreError extends Error {}

export function requestFingerprint(input: SendReceiptInput): string;

export function resolveReceiptStaleAfterMs(
  value: number | string | undefined,
): number;

export function provisionReceiptRoot(receiptDir: string): Promise<string>;

export type ReceiptTransition =
  | {
      state: "stored";
      result: StoredSendReceipt;
      transitioned: boolean;
    }
  | {
      state: "unknown";
      error: Record<string, unknown>;
      transitioned: boolean;
    }
  | { state: "pending"; transitioned: false }
  | { state: "missing" };

export function claimPacket(
  receiptDir: string,
  input: SendReceiptInput,
  options?: ReceiptOptions,
): Promise<
  | { state: "owner"; ownerToken: string }
  | { state: "stored"; result: StoredSendReceipt }
  | {
      state: "pending";
      status: "PENDING";
      packet_id: string;
      target: string;
    }
  | { state: "unknown"; error: Record<string, unknown> }
  | { state: "conflict" }
>;

export function persistStored(
  receiptDir: string,
  input: SendReceiptInput,
  result: StoredSendReceipt,
  ownerToken: string,
  options?: ReceiptOptions,
): Promise<ReceiptTransition>;

export function persistUnknown(
  receiptDir: string,
  input: SendReceiptInput,
  error: Record<string, unknown>,
  ownerToken: string,
  options?: ReceiptOptions,
): Promise<ReceiptTransition>;

export function releasePacket(
  receiptDir: string,
  packetId: string,
  ownerToken: string,
  options?: ReceiptOptions,
): Promise<boolean>;

export function getPacketStatus(
  receiptDir: string,
  packetId: string,
  options?: ReceiptOptions,
): Promise<
  | { state: "missing"; status: "NOT_FOUND"; packet_id: string }
  | {
      state: "pending" | "unknown";
      status: "PENDING" | "UNKNOWN";
      packet_id: string;
      target: string;
    }
  | {
      state: "stored";
      status: "STORED";
      packet_id: string;
      target: string;
      receipt: StoredSendReceipt;
    }
>;
