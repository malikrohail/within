// Mirrors x402_xrpl.client.presigned_payment_payer.prepare_payment (invoice_binding="both").
import { createHash } from "node:crypto";
import type { Client, Memo, Payment } from "xrpl";
import type { Requirements } from "./types.js";

export const FACILITATOR_MEMO_TYPE = "urn:x402:facilitator";
export const FACILITATOR_MEMO_FORMAT = "application/json";
export const MAX_FEE_DROPS = 10_000;

export class PaymentError extends Error {}

export interface Ledger {
  validatedLedgerIndex(): Promise<number>;
  networkId(): Promise<number | undefined>;
  autofill(tx: Payment): Promise<Payment>;
}

export const clientLedger = (client: Client): Ledger => ({
  validatedLedgerIndex: () => client.getLedgerIndex(),
  networkId: async () => (await client.request({ command: "server_info" })).result.info.network_id,
  autofill: (tx) => client.autofill(tx),
});

export const textToMemoHex = (text: string) => Buffer.from(text, "utf8").toString("hex").toUpperCase();
export const invoiceIdField = (inv: string) => createHash("sha256").update(inv, "utf8").digest("hex").toUpperCase();

/** Python json.dumps(obj, separators=(",", ":")) — ensure_ascii escapes non-ASCII. */
const pyJson = (obj: unknown) =>
  JSON.stringify(obj).replace(/[\u0080-￿]/g, (c) => "\\u" + c.charCodeAt(0).toString(16).padStart(4, "0"));

function intTag(raw: unknown, name: string): number | undefined {
  if (raw === undefined || raw === null) return undefined;
  const n = typeof raw === "string" && /^\s*-?\d+\s*$/.test(raw) ? Number(raw) : raw;
  if (typeof n !== "number" || !Number.isInteger(n)) throw new PaymentError(`${name} must be an integer`);
  return n;
}

function facilitatorFrom(extra: Record<string, unknown>): { id: string; name?: string } | undefined {
  const f = extra.facilitator;
  if (!f || typeof f !== "object") return undefined;
  const { id, name } = f as { id?: unknown; name?: unknown };
  if (typeof id !== "string" || !id.trim()) return undefined;
  const out: { id: string; name?: string } = { id: id.trim().slice(0, 64) };
  if (typeof name === "string" && name.trim()) out.name = name.trim().slice(0, 128);
  return out;
}

/** The unsigned Payment before autofill (Fee, Sequence). Pure, for tests. */
export function basePayment(req: Requirements, account: string, validatedLedger: number): Payment {
  const extra = (req.extra ?? {}) as Record<string, unknown>;
  const inv = extra.invoiceId;
  if (typeof inv !== "string" || !inv) throw new PaymentError("invoice_id_required");
  if (req.asset.toUpperCase() !== "XRP") throw new PaymentError("asset_not_supported");

  const destinationTag = intTag(extra.destinationTag, "destinationTag");
  const sourceTag = intTag(extra.sourceTag, "sourceTag");

  const memos: Memo[] = [{ Memo: { MemoData: textToMemoHex(inv) } }];
  const fac = facilitatorFrom(extra);
  if (fac) {
    const obj: Record<string, unknown> = { id: fac.id };
    if (fac.name) obj.name = fac.name;
    if (sourceTag !== undefined) obj.sourceTag = sourceTag;
    memos.push({
      Memo: {
        MemoType: textToMemoHex(FACILITATOR_MEMO_TYPE),
        MemoData: textToMemoHex(pyJson(obj)),
        MemoFormat: textToMemoHex(FACILITATOR_MEMO_FORMAT),
      },
    });
  }

  const tx: Payment = {
    TransactionType: "Payment",
    Account: account,
    Destination: req.payTo,
    Amount: BigInt(req.amount).toString(),
    Memos: memos,
    InvoiceID: invoiceIdField(inv),
    LastLedgerSequence: validatedLedger + Math.ceil(req.maxTimeoutSeconds / 5) + 2,
  };
  if (sourceTag !== undefined) tx.SourceTag = sourceTag;
  if (destinationTag !== undefined) tx.DestinationTag = destinationTag;
  return tx;
}

/** Full builder: network check, LastLedgerSequence from the validated ledger, autofill, fee cap. */
export async function buildPayment(
  ledger: Ledger,
  req: Requirements,
  account: string,
  signingPubKey?: string,
  delegate?: string,
): Promise<Payment> {
  const expected = Number(req.network.split(":")[1]);
  const networkId = await ledger.networkId();
  if (networkId !== expected) throw new PaymentError("rpc_network_mismatch");

  const tx = basePayment(req, account, await ledger.validatedLedgerIndex());
  if (signingPubKey) tx.SigningPubKey = signingPubKey.toUpperCase();
  // PermissionDelegation: Account pays, the delegate signs.
  if (delegate) tx.Delegate = delegate;
  const filled = await ledger.autofill(tx);
  if (filled.NetworkID !== undefined && filled.NetworkID !== expected) throw new PaymentError("rpc_network_mismatch");
  const fee = filled.Fee ?? "";
  if (!/^\d+$/.test(fee) || Number(fee) < 1 || Number(fee) > MAX_FEE_DROPS) throw new PaymentError("fee_exceeds_payer_policy");
  return filled;
}
