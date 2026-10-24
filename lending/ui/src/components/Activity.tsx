import type { ReactNode } from "react";
import { reasonSentence } from "../copy";
import { ago, xrp } from "../format";
import type { Loan, LoanRequest, Policy, Sweep, Vault } from "../types";
import { batchOf, BatchLegs, BatchPill } from "./BatchView";
import { Addr, Explorer, Icon, LatestNote } from "./bits";

type Look = { icon: ReactNode; tone: "ok" | "warn" | "bad" | "dim"; headline: string; detail: ReactNode };

function look(r: LoanRequest, policy: Policy | null, vault: Vault | null): Look {
  const wc = r.kind === "working_capital";
  const s = reasonSentence(r, policy, vault);
  const score = r.score != null ? `Score ${r.score}` : null;
  switch (r.status) {
    case "held":
      return {
        icon: Icon.clock(),
        tone: "warn",
        headline: "Waiting for your approval",
        detail: r.reason === "over_auto_limit" ? "Over the auto-approve limit" : s.rest,
      };
    case "auto":
      return {
        icon: Icon.check(),
        tone: "ok",
        headline: wc ? "Working capital sent to the supplier" : "Loan approved automatically",
        detail: [score, "within the auto-approve limit"].filter(Boolean).join(", "),
      };
    case "approved":
      return {
        icon: Icon.check(),
        tone: "ok",
        headline: wc ? "Working capital sent to the supplier" : "Loan approved by you",
        detail: wc ? "Approved by you: loan co-signed, then one all-or-nothing batch" : "Approved after review",
      };
    case "refused":
      return {
        icon: Icon.x(),
        tone: "bad",
        headline: r.reason === "batch_unfunded" ? "Batch refused before signing" : "Request refused",
        detail: s.rest,
      };
    case "denied":
      return { icon: Icon.x(), tone: "bad", headline: "You denied this request", detail: "No transaction was made." };
    case "expired":
      return { icon: Icon.clock(), tone: "dim", headline: "Request expired", detail: s.rest || "Nobody approved in time, no transaction made." };
    case "failed":
      return { icon: Icon.warn(), tone: "bad", headline: s.lead.replace(/[.:]$/, "") || "Failed", detail: s.rest };
  }
  return { icon: Icon.clock(), tone: "dim", headline: r.status, detail: null };
}

function Row({ r, policy, vault, now }: { r: LoanRequest; policy: Policy | null; vault: Vault | null; now: number }) {
  const l = look(r, policy, vault);
  const batch = batchOf(r);
  return (
    <div className="row">
      <div className={`ic ${l.tone}`}>{l.icon}</div>
      <div style={{ minWidth: 0 }}>
        <div className="h">
          {l.headline}
          {batch && <BatchPill />}
        </div>
        <div className="sub">
          <Addr addr={r.borrower} />
          <span>·</span>
          <span>{l.detail}</span>
          {r.txHash && (
            <>
              <span>·</span>
              <Explorer hash={r.txHash}>{batch ? "Loan on explorer" : "View on explorer"}</Explorer>
            </>
          )}
          {batch?.hash && (
            <>
              <span>·</span>
              <Explorer hash={batch.hash}>Batch on explorer</Explorer>
            </>
          )}
        </div>
        <LatestNote r={r} />
        {batch && <BatchLegs r={r} batch={batch} />}
      </div>
      <div className="r num">
        {xrp(r.principalDrops)}
        <small>{ago(r.ts, now)}</small>
      </div>
    </div>
  );
}

// A customer's x402 payment and the installment the borrower's sweeper paid from it. Amounts from the record.
function SweepRow({ s, now }: { s: Sweep; now: number }) {
  const ok = s.status === "repaid";
  return (
    <div className="row">
      <div className={`ic ${ok ? "ok" : "bad"}`}>{ok ? Icon.check() : Icon.warn()}</div>
      <div style={{ minWidth: 0 }}>
        <div className="h">
          {ok
            ? `Customer paid ${xrp(s.incomeDrops)} → installment ${xrp(s.drops)} paid automatically`
            : `Customer paid ${xrp(s.incomeDrops)} → automatic repayment failed: ${s.engineResult}`}
        </div>
        <div className="sub">
          <Addr addr={s.borrower} />
          <span>·</span>
          <Explorer hash={s.incomeHash}>Customer payment on explorer</Explorer>
          <span>·</span>
          <Explorer hash={s.loanPayHash}>{ok ? "Installment on explorer" : "Failed LoanPay on explorer"}</Explorer>
        </div>
      </div>
      <div className="r num">
        {xrp(s.drops)}
        <small>{ago(s.at, now)}</small>
      </div>
    </div>
  );
}

export function Activity({ requests, loans, policy, vault, now }: { requests: LoanRequest[]; loans: Loan[]; policy: Policy | null; vault: Vault | null; now: number }) {
  const items = [
    ...requests.map((r) => ({ ts: r.ts, key: r.id, node: <Row key={r.id} r={r} policy={policy} vault={vault} now={now} /> })),
    ...loans.flatMap((l) => l.sweeps ?? []).map((s) => ({ ts: s.at, key: s.loanPayHash, node: <SweepRow key={s.loanPayHash} s={s} now={now} /> })),
  ].sort((a, b) => b.ts - a.ts);
  return (
    <section>
      <h3>Activity</h3>
      {items.length === 0 ? (
        <div className="empty">No loan requests yet.</div>
      ) : (
        <div className="rows">{items.map((i) => i.node)}</div>
      )}
    </section>
  );
}
