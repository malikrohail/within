// Control tower data: known accounts, and ledger transactions turned into money flows.
import type { WalletRequest } from "../api";

export type Network = "testnet" | "devnet";
export type Role = "treasury" | "agent" | "merchant" | "broker" | "supplier" | "borrower" | "customer" | "vault" | "lending" | "unknown";
export type Kind = "auto" | "approved" | "refused" | "loan" | "deposit" | "repay" | "other";

export type Known = { address: string; name: string; role: string };
export type Accounts = { testnet: Known[]; devnet: Known[]; devnetObjects: { vaultId: string | null; loanBrokerId: string | null } };

export type GraphNode = { id: string; name: string; role: Role; network: Network };

/** One money movement: a validated transaction, or a refusal that never reached the ledger. */
export type Flow = {
  id: string;
  network: Network;
  from: string;
  to: string;
  drops: number;
  amount: string;
  kind: Kind;
  hash: string | null;
  ts: number;
  note?: string;
};

export const EXPLORER: Record<Network, string> = { testnet: "https://testnet.xrpl.org", devnet: "https://devnet.xrpl.org" };
export const WS_URLS: Record<Network, string[]> = {
  testnet: ["wss://s.altnet.rippletest.net:51233", "wss://testnet.xrpl-labs.com", "wss://clio.altnet.rippletest.net:51233"],
  devnet: ["wss://s.devnet.rippletest.net:51233"],
};

export const KIND_COLOR: Record<Kind, string> = {
  auto: "#2bb3a3",
  approved: "#e8a33d",
  refused: "#d9534f",
  loan: "#4a8fe7",
  deposit: "#9b87f5",
  repay: "#7cc4fa",
  other: "#5b6672",
};

export const KIND_LABEL: Record<Kind, string> = {
  auto: "auto (hot key)",
  approved: "approved on Ledger",
  refused: "refused",
  loan: "loan",
  deposit: "vault deposit",
  repay: "repayment",
  other: "other payment",
};

const RIPPLE_EPOCH = 946684800;
const TF_INNER_BATCH_TXN = 0x40000000;

function amountOf(v: unknown): { drops: number; text: string } {
  if (typeof v === "string" && /^\d+$/.test(v)) return { drops: Number(v), text: `${Number(v) / 1e6} XRP` };
  if (v && typeof v === "object") {
    const o = v as Record<string, string>;
    return { drops: 0, text: `${o.value} ${o.currency ?? "MPT"}` };
  }
  return { drops: 0, text: "" };
}

export type TxContext = {
  network: Network;
  roleOf: (address: string) => Role | undefined;
  /** VaultID → node id (the vault pseudo-account when resolved). */
  vaultNode: (vaultId: string | undefined) => string;
};

/**
 * Turns one validated, successful transaction into flows. Payments on testnet are coloured by who signed:
 * the hot key (auto), the treasury with a Delegate (auto, delegated), the treasury alone (approved on the Ledger).
 * A Batch gives no flows: its RawTransactions may have rolled back even when the outer Batch is tesSUCCESS, and
 * the legs that did apply are validated as their own transactions.
 */
export function flowsFromTx(tx: Record<string, unknown>, hash: string, date: number | undefined, ctx: TxContext): Flow[] {
  const type = tx.TransactionType as string;
  const account = tx.Account as string;
  const ts = date ? (date + RIPPLE_EPOCH) * 1000 : Date.now();
  const base = { network: ctx.network, hash, ts };
  if (type === "Payment") {
    const a = amountOf(tx.Amount);
    const role = ctx.roleOf(account);
    const kind: Kind = role === "agent" ? "auto" : role === "treasury" ? (tx.Delegate ? "auto" : "approved") : "other";
    // An applied Batch leg arrives as its own validated tx with tfInnerBatchTxn set.
    const note = (Number(tx.Flags) & TF_INNER_BATCH_TXN) !== 0 ? "batch" : tx.Delegate ? "delegated" : undefined;
    return [{ ...base, id: hash, from: account, to: tx.Destination as string, drops: a.drops, amount: a.text, kind, note }];
  }
  if (type === "LoanSet") {
    const a = amountOf(tx.PrincipalRequested);
    const parties = [account, tx.Counterparty as string].filter(Boolean);
    const borrower = parties.find((p) => ctx.roleOf(p) !== "broker") ?? account;
    return [{ ...base, id: hash, from: ctx.vaultNode(undefined), to: borrower, drops: a.drops, amount: a.text, kind: "loan" }];
  }
  if (type === "LoanPay") {
    const a = amountOf(tx.Amount);
    return [{ ...base, id: hash, from: account, to: ctx.vaultNode(undefined), drops: a.drops, amount: a.text, kind: "repay" }];
  }
  if (type === "VaultDeposit") {
    const a = amountOf(tx.Amount);
    return [{ ...base, id: hash, from: account, to: ctx.vaultNode(tx.VaultID as string), drops: a.drops, amount: a.text, kind: "deposit" }];
  }
  return [];
}

/** Wallet refusals never reach the ledger, so they come from GET /v1/requests. */
export function flowsFromRequests(rows: WalletRequest[], agent: string | null, treasury: string | null): Flow[] {
  return rows
    .filter((r) => r.status === "refused" && r.kind !== "delegate")
    .map((r) => {
      const from = (r.source === "treasury" ? treasury : agent) ?? "wallet";
      return {
        id: r.id, network: "testnet" as const, from, to: r.merchant, drops: Number(r.amountDrops) || 0,
        amount: `${Number(r.amountDrops) / 1e6} XRP`, kind: "refused" as const, hash: null, ts: Date.parse(r.ts), note: r.reason ?? undefined,
      };
    });
}

/** Wallet incidents (device or RPC trouble), not policy decisions. Hidden from "Latest run"; listed under "All" and in the Pay feed. */
export const INCIDENT_REASONS = new Set(["device_unavailable", "rpc_error"]);
export const isIncident = (f: Flow) => f.kind === "refused" && INCIDENT_REASONS.has(f.note ?? "");

/** Each network's latest run: flows within `windowMs` of that network's newest flow (anchored to the data, not the clock). */
export function latestRun(flows: Flow[], windowMs = 15 * 60_000): Flow[] {
  const newest = new Map<Network, number>();
  for (const f of flows) newest.set(f.network, Math.max(newest.get(f.network) ?? -Infinity, f.ts));
  return flows.filter((f) => f.ts >= newest.get(f.network)! - windowMs);
}

/** localStorage key for cached ledger flows: one per network and exact known-account set, so a rotated set starts empty. */
export const cacheKey = (network: Network, addresses: string[]) => `tower:v1:${network}:${[...addresses].sort().join(",")}`;
