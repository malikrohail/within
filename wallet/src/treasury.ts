// Treasury-side ledger calls for PermissionDelegation (amended after the spike).
// x402 stays on the hot account: the T54 facilitator refuses delegated blobs. Treasury payments
// (Account=treasury, Delegate=hot) are submitted here directly, and so are device-signed DelegateSets.
import type { DelegateSet } from "xrpl";
import type { XrplConnection } from "./xrpl.js";

export type DirectResult = { engineResult: string; txHash: string | null };
export type DelegateEntry = {
  Account: string;
  Authorize: string;
  Permissions: { Permission: { PermissionValue: string } }[];
};

export interface TreasuryLedger {
  autofill(tx: DelegateSet): Promise<DelegateSet>;
  validatedLedgerIndex(): Promise<number>;
  /**
   * Submits a signed blob and waits until it is validated or its LastLedgerSequence has passed.
   * A rejected preliminary result (ter/tef/tem/tel, e.g. terNO_DELEGATE_PERMISSION) returns at once
   * with txHash null: nothing is on the ledger. Never retried: a second submit could double-pay.
   */
  submit(blob: string, hash: string, lastLedger: number): Promise<DirectResult>;
  /** Validated Delegate entries owned by `account`. */
  delegates(account: string): Promise<DelegateEntry[]>;
}

/** grant = ["Payment"], revoke = [] (an empty list deletes the Delegate entry). */
export function delegateSet(treasury: string, agent: string, permissions: string[], lastLedger: number): DelegateSet {
  return {
    TransactionType: "DelegateSet",
    Account: treasury,
    Authorize: agent,
    Permissions: permissions.map((p) => ({ Permission: { PermissionValue: p } })),
    LastLedgerSequence: lastLedger,
  } as DelegateSet;
}

export function permissionsFor(entries: DelegateEntry[], agent: string): string[] {
  return entries.filter((e) => e.Authorize === agent).flatMap((e) => e.Permissions.map((p) => p.Permission.PermissionValue));
}

const realSleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

export function clientTreasury(xrpl: Pick<XrplConnection, "read" | "get">, sleep = realSleep): TreasuryLedger {
  return {
    autofill: (tx) => xrpl.read((c) => c.autofill(tx)),
    validatedLedgerIndex: () => xrpl.read((c) => c.getLedgerIndex()),
    async submit(blob, hash, lastLedger) {
      const prelim = (await (await xrpl.get()).request({ command: "submit", tx_blob: blob })).result.engine_result;
      if (!/^(tes|tec|terQUEUED)/.test(prelim)) return { engineResult: prelim, txHash: null };
      for (;;) {
        await sleep(1000);
        try {
          const tx = await xrpl.read((c) => c.request({ command: "tx", transaction: hash }));
          const meta = tx.result.meta;
          if (tx.result.validated && typeof meta === "object" && meta) return { engineResult: meta.TransactionResult, txHash: hash };
        } catch (e) {
          if ((e as { data?: { error?: string } }).data?.error !== "txnNotFound") throw e;
        }
        if ((await xrpl.read((c) => c.getLedgerIndex())) > lastLedger) return { engineResult: `${prelim} (not validated)`, txHash: null };
      }
    },
    async delegates(account) {
      const r = await xrpl.read((c) =>
        c.request({ command: "account_objects", account, type: "delegate", ledger_index: "validated" } as never),
      );
      return (r as { result: { account_objects: DelegateEntry[] } }).result.account_objects;
    },
  };
}
