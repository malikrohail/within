// Formatters for the lending-era types (Vault*, LoanBroker*, Loan*, PermissionedDomainSet).
// Units checked against xrpl.js 5.3 validation: rates are tenths of a basis point
// (MAX_INTEREST_RATE = 100000 = 100%), intervals and grace periods are seconds.
import { account, currencyName, dropsToXrp, duration, hexText, short } from "./formats.js";
import type { Formatter } from "./types.js";

/** 500 → "0.5%" (tenths of a basis point). */
export function tenthBps(v: unknown): string {
  const n = Number(v);
  return `${(n / 1000).toLocaleString("en-US", { maximumFractionDigits: 3 })}%`;
}

export const LENDING_FORMATS: Record<string, Formatter> = {
  tenth_bps: (v) => tenthBps(v),
  /** STNumber amounts are in the vault asset's units; for an XRP vault that is drops. */
  vault_amount: (v) => {
    const s = String(v);
    return /^\d+$/.test(s) ? `${s} (${dropsToXrp(s)} if the vault holds XRP)` : s;
  },
  /** Vault asset: {currency:"XRP"} | {currency, issuer} | {mpt_issuance_id}. */
  asset: (v, _tx, ctx) => {
    const a = (v ?? {}) as Record<string, string>;
    if (a.mpt_issuance_id) return { value: `MPT ${short(a.mpt_issuance_id, 8, 4)}`, full: a.mpt_issuance_id };
    if (a.currency === "XRP" && !a.issuer) return "XRP";
    return `${currencyName(a.currency ?? "?")} issued by ${a.issuer ? account(a.issuer, ctx).value : "?"}`;
  },
  /** LoanSet needs both parties: Account signs the transaction, Counterparty signs CounterpartySignature. */
  loan_signed_by: (_v, tx, ctx) => {
    const submitter = typeof tx.Account === "string" ? account(tx.Account, ctx).value : "?";
    const cp = typeof tx.Counterparty === "string" ? account(tx.Counterparty, ctx).value : "the loan broker owner";
    const mine = typeof tx.TxnSignature === "string" && tx.TxnSignature !== "" ? "signed" : "not signed yet";
    const sig = tx.CounterpartySignature as { TxnSignature?: string; Signers?: unknown[] } | undefined;
    const theirs = sig?.TxnSignature || sig?.Signers?.length ? "signed" : "not signed yet";
    return { value: `${submitter}: ${mine}; ${cp}: ${theirs}`, ...(theirs === "signed" ? {} : { risk: "warn" as const }) };
  },
  seconds: (v) => duration(Number(v)),
  /** PermissionedDomainSet: who may join, as issuer + credential type. */
  accepted_credentials: (v, _tx, ctx) => {
    const list = Array.isArray(v) ? v : [];
    return list
      .map((c) => {
        const cred = ((c as { Credential?: Record<string, string> }).Credential ?? {}) as Record<string, string>;
        return `"${hexText(cred.CredentialType ?? "") ?? cred.CredentialType}" from ${account(cred.Issuer, ctx).value}`;
      })
      .join("; ");
  },
};
