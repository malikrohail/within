// Reason code -> plain sentence. Every number comes from the record,
// the vault or GET /v1/policy; nothing here is a hard-coded cap.
import { pct1, sumDrops, xrpNum } from "./format";
import type { Evidence, LoanRequest, Policy, Vault } from "./types";

export type Tone = "ok" | "warn" | "bad" | "dim";

/** Lead word + rest, e.g. ["Held for you.", "60 XRP is more than ..."]. */
export type Sentence = { lead: string; rest: string; tone: Tone };

const amt = (r: LoanRequest) => xrpNum(r.principalDrops);

/** If this loan were made now: share of the vault out on loan (%), and cover as % of debt. */
export function ifApproved(r: LoanRequest, v: Vault) {
  const p = Number(r.principalDrops);
  const total = Number(v.assetsTotalDrops);
  const out = Number(v.loansOutstandingDrops) + p;
  const debt = Number(v.debtTotalDrops) + p;
  return {
    utilPct: total > 0 ? (100 * out) / total : 0,
    coverPct: debt > 0 ? (100 * Number(v.coverDrops)) / debt : 100,
  };
}

/** wait_for_tx's results for a tx that passed its LastLedgerSequence unvalidated (the wall-clock backstop is timeout_waiting). */
const EXPIRED = new Set(["txnNotFound", "not_validated"]);

export function reasonSentence(r: LoanRequest, policy: Policy | null, vault: Vault | null): Sentence {
  const code = r.reason ?? "";
  const s = r.score ?? "-";
  const P = policy;
  // The policy is today's; a decided record may predate an edit. Quote a threshold only when it still explains
  // the decision, otherwise say it in words.
  const amtN = BigInt(r.principalDrops || "0");
  const sc = r.score ?? 0;
  switch (code) {
    case "over_auto_limit":
      return {
        lead: "Held for you.",
        rest: P && amtN > BigInt(P.maxAutoPrincipalDrops)
          ? `${amt(r)} XRP is more than the ${xrpNum(P.maxAutoPrincipalDrops)} XRP the desk approves on its own. The score itself looks fine.`
          : `${amt(r)} XRP is over the desk's auto-approve limit. The score itself looks fine.`,
        tone: "warn",
      };
    case "score_below_auto":
      return {
        lead: "Held for you.",
        rest: P && sc < P.minScoreAuto
          ? `The score is ${s}, under the ${P.minScoreAuto} the desk needs to approve on its own.`
          : `The score is ${s}, under what the desk needs to approve on its own.`,
        tone: "warn",
      };
    case "policy_changed_mid_flight":
      return {
        lead: r.status === "held" ? "Held for you." : "Refused.",
        rest: "The policy changed while this request was in flight, and the new policy does not allow it. Nothing was signed.",
        tone: r.status === "held" ? "warn" : "bad",
      };
    case "no_broker_credential":
      return {
        lead: "Held for you.",
        rest: "The borrower has no KYB credential from this broker yet.",
        tone: "warn",
      };
    case "score_too_low":
      return {
        lead: "Refused.",
        rest:
          P && sc < P.minScore
            ? `The score is ${s}; the desk lends from ${P.minScore}. No transaction was made.`
            : `The score is ${s}, under the desk's minimum at the time. No transaction was made.`,
        tone: "bad",
      };
    case "over_max_principal":
      return {
        lead: "Refused.",
        rest:
          P && amtN > BigInt(P.maxPrincipalDrops)
            ? `${amt(r)} XRP is above the ${xrpNum(P.maxPrincipalDrops)} XRP cap. No transaction was made.`
            : `${amt(r)} XRP was above the desk's cap at the time. No transaction was made.`,
        tone: "bad",
      };
    case "vault_utilization": {
      // Only a still-open request can say what this loan would do to today's vault.
      const pct = vault && r.status === "held" ? `${pct1(ifApproved(r, vault).utilPct)}%` : null;
      const max = P ? `${P.maxUtilizationPct}%` : "the limit";
      return {
        lead: "Refused.",
        rest: pct
          ? `This loan would put ${pct} of the vault out on loan; the limit is ${max}.`
          : `This loan would have put more of the vault out on loan than the ${max} limit. No transaction was made.`,
        tone: "bad",
      };
    }
    case "cover_below_minimum":
      return {
        lead: "Refused.",
        rest: `The broker's cover would fall under ${P ? P.minCoverRatioPct : "the minimum"}% of debt. No transaction was made.`,
        tone: "bad",
      };
    case "declared_debt_understated": {
      // Declared existing debt below the borrower's on-ledger loan principal (policy.decide, before the score).
      const ev = r.evidence as Partial<Evidence>;
      return {
        lead: "Refused.",
        rest: `They declared ${xrpNum(ev.declared?.existingDebtDrops)} XRP of existing debt but the ledger shows ${xrpNum(ev.ledger?.loanPrincipalDrops)} XRP outstanding. No transaction was made.`,
        tone: "bad",
      };
    }
    case "batch_unfunded": {
      const b = r.batch;
      const sum = b ? xrpNum(sumDrops(b.supplierDrops, b.feeDrops)) : "-";
      return {
        lead: "Refused.",
        rest: `The supplier and fee legs (${sum} XRP) are more than the loan (${amt(r)} XRP). No transaction was made.`,
        tone: "bad",
      };
    }
    case "second_opinion_hold":
    case "second_opinion_deny": {
      // Agent 2: the second opinion held a request the policy would have approved, or advised denial.
      const so = r.secondOpinion === "off" ? null : r.secondOpinion;
      const flags = so?.flags.length ? flagWords(so.flags) : "this request";
      const memo = so?.memo || r.memo || "no memo was given.";
      return { lead: "Held for you.", rest: `The second opinion flagged ${flags}: ${memo}`, tone: code === "second_opinion_deny" ? "bad" : "warn" };
    }
    case "hold_timeout":
      return { lead: "Request expired.", rest: "Nobody approved in time, no transaction made.", tone: "dim" };
  }
  if (r.status === "denied") return { lead: "You denied this request.", rest: "No transaction was made.", tone: "bad" };
  if (code === "timeout_waiting")
    return {
      lead: "Timed out waiting for validation.",
      rest: "The desk stopped waiting before devnet reached the transaction's last valid ledger, so it may still apply. Check it on the explorer.",
      tone: "bad",
    };
  if (code === "batch:timeout_waiting")
    return { lead: "Loan made, timed out waiting for the batch.", rest: "The desk stopped waiting before the supplier batch validated. Check it on the explorer.", tone: "bad" };
  if (EXPIRED.has(code))
    return {
      lead: "Expired before validation.",
      rest: "Devnet passed the transaction's last valid ledger without including it, so it can no longer apply. No loan was made.",
      tone: "bad",
    };
  if (code.startsWith("batch:") && EXPIRED.has(code.slice(6)))
    return { lead: "Loan made, batch expired before validation.", rest: "The supplier batch never made it into a validated ledger, so no leg moved.", tone: "bad" };
  if (code.startsWith("batch:"))
    return { lead: "Loan made, batch failed.", rest: `The ledger refused the supplier batch: ${code.slice(6)}.`, tone: "bad" };
  if (code.startsWith("ledger_unavailable"))
    return { lead: "Not submitted.", rest: "The desk could not reach the ledger.", tone: "bad" };
  if (code) return { lead: "The ledger refused it:", rest: `${code}.`, tone: "bad" };
  return { lead: "", rest: "", tone: "dim" };
}

/** ["single_payer", "fresh_account"] -> "single payer, fresh account". */
export const flagWords = (flags: string[]) => flags.map((f) => f.replace(/_/g, " ")).join(", ");

/** Desk HTTP error -> plain words for the red line under Approve/Deny. */
export function deskErrorWords(status: number, detail: string, policy: Policy | null): string {
  if (status === 409) {
    if (detail.startsWith("not_held")) {
      const now = detail.split(":")[1]?.trim();
      return `This request is no longer waiting for you${now ? ` (it is ${now} now)` : ""}. Nothing was signed.`;
    }
    if (detail === "approve_in_progress") return "An approval for this request is already running.";
    if (detail === "vault_utilization")
      return `The vault has changed: this loan would now put it over the ${policy?.maxUtilizationPct ?? "-"}% lending limit. Nothing was signed.`;
    if (detail === "cover_below_minimum")
      return `The vault has changed: the broker's cover would now fall under ${policy?.minCoverRatioPct ?? "-"}% of debt. Nothing was signed.`;
    if (detail === "score_too_low" || detail === "over_max_principal")
      return `The policy has changed and now refuses this loan (${detail.replace(/_/g, " ")}). Nothing was signed.`;
  }
  if (status === 409 && (detail.startsWith("approval_") || detail.startsWith("tx_lookup_failed")))
    return `The Ledger approval did not check out (${detail}). Nothing was signed.`;
  if (status === 422 && detail === "approval_tx_required")
    return "This desk needs a Ledger-signed approval for this loan. Nothing was signed.";
  if (status === 401) return "The desk needs the operator token (VITE_DESK_TOKEN). Nothing was signed.";
  if (status === 503 && detail === "operator_token_unset")
    return "The desk has no operator token set (DESK_TOKEN), so it signs nothing. Nothing was signed.";
  if (status === 503) return "The desk could not reach the ledger. Nothing was signed; try again in a moment.";
  if (status === 0) return "The desk did not answer. Check that it is running on port 7500.";
  return `The desk said no (${status}): ${detail}`;
}

/** wallet POST /v1/lend/approve failed: say what the wallet said, plainly. */
export function walletErrorWords(status: number, reason: string): string {
  if (reason === "denied_on_device") return "You declined the approval on the Ledger. Nothing was signed.";
  if (reason === "hold_timeout") return "The Ledger approval timed out before anyone confirmed it. Nothing was signed.";
  if (reason === "device_unavailable") return "The Ledger is not connected to the wallet. Nothing was signed.";
  if (status === 0) return `The wallet on port 7402 did not answer (${reason}). Nothing was signed.`;
  return `The wallet refused the Ledger approval (${status}): ${reason}. Nothing was signed.`;
}

const PURPOSE: Record<string, string> = {
  inventory: "to buy inventory",
  payroll: "to cover payroll",
  equipment: "to buy equipment",
  receivables: "against unpaid invoices",
};

export function purposePhrase(r: LoanRequest): string {
  if (r.kind === "working_capital") return "to prepay a supplier";
  return PURPOSE[r.purpose] ?? `for ${r.purpose}`;
}

export const purposeLabel = (p: string) => (p ? p[0].toUpperCase() + p.slice(1) : "-");
