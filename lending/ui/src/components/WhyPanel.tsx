import type { ReactNode } from "react";
import { flagWords, ifApproved, purposeLabel } from "../copy";
import { duration, paymentsWord, pct1, sumDrops, xrp } from "../format";
import type { Breakdown, Evidence, LoanRequest, Policy, Vault } from "../types";
import { Addr } from "./bits";

function KV({ k, v }: { k: string; v: ReactNode }) {
  return (
    <div className="kv">
      <span>{k}</span>
      <span className="num">{v}</span>
    </div>
  );
}

function Score({ value }: { value: number | null }) {
  return value == null ? (
    <>
      <div className="sc">
        –<small>no score</small>
      </div>
      <div className="sbar" />
    </>
  ) : (
    <>
      <div className="sc num">
        {value}
        <small>out of 100</small>
      </div>
      <div className="sbar">
        <i style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />
      </div>
    </>
  );
}

const noneOr = (n: number, v: ReactNode) => (n === 0 ? "None" : v);

const SO_VERDICT = { agree: "Agrees with the policy", hold: "Would hold for a human", deny: "Would deny" } as const;
const SO_TONE = { agree: "ok", hold: "warn", deny: "bad" } as const;

/** Fourth block: the model's memo and flags. It can only tighten; it never approves. */
function SecondOpinionBlock({ r }: { r: LoanRequest }) {
  const so = r.secondOpinion;
  const ms = r.secondOpinionMs;
  return (
    <div className="so">
      <div className="so-head">
        <h4>Second opinion</h4>
        {ms != null && <small className="num">{(ms / 1000).toFixed(1)} s</small>}
      </div>
      {so === "off" ? (
        <p>Second opinion off (scripted run). The policy's decision stands.</p>
      ) : so ? (
        <>
          <div className="so-verdict">
            <span className={`tag ${SO_TONE[so.recommendation]}`}>{SO_VERDICT[so.recommendation]}</span>
            {so.flags.length > 0 && <span className="so-flags">{flagWords(so.flags)}</span>}
          </div>
          <p>{so.memo}</p>
        </>
      ) : (
        <p>No second opinion{ms != null ? ". The model gave no usable answer in time, so the policy's decision stands." : "."}</p>
      )}
    </div>
  );
}

/** Three columns from breakdown + evidence, then the plain-sentence summary. */
export function WhyBody({
  r,
  evidence,
  breakdown,
  vault,
  policy,
  paymentTotal,
}: {
  r: LoanRequest;
  evidence: Evidence;
  breakdown: Breakdown;
  vault: Vault | null;
  policy: Policy | null;
  paymentTotal: number | null;
}) {
  const w = breakdown.weights;
  const l = evidence.ledger;
  const d = evidence.declared;
  const bank = evidence.bank;
  const after = vault ? ifApproved(r, vault) : null;
  const parts = [`${breakdown.ledger.score} on-chain at ${w.ledger}%`];
  if (w.bank > 0 && breakdown.bank) parts.push(`${breakdown.bank.score} from the bank at ${w.bank}%`);
  parts.push(`${breakdown.declared.score} from their application at ${w.declared}%`);
  const b = r.kind === "working_capital" ? r.batch : undefined;
  // Credential points and weight come from the breakdown, never hard-coded.
  const credPts = breakdown.ledger.rules.find((x) => x.rule === "hasAcceptedCredential")?.points ?? 0;
  const cred = l.credentialIssuer && credPts > 0 ? { pts: credPts, total: Math.round((credPts * w.ledger) / 100) } : null;

  return (
    <div className="body">
      <div className="cols">
        <div className="col">
          <h4>On-chain history</h4>
          <div className="w">Counts for {w.ledger}% of the score</div>
          <Score value={breakdown.ledger.score} />
          <KV k="x402 income" v={l.x402Payments ? `${xrp(l.x402IncomeDrops ?? "0")} from ${l.x402Payers} paying customer${l.x402Payers === 1 ? "" : "s"}` : "None"} />
          <KV k="Payments received" v={l.inboundPaymentCount} />
          <KV k="Total received" v={xrp(l.inboundVolumeDrops)} />
          <KV k="Different payers" v={l.distinctPayers} />
          <KV k="Largest payer" v={l.inboundPaymentCount ? `${pct1(l.topPayerSharePct)}% of volume` : "None"} />
          <KV
            k="Active days"
            v={`${l.activeDays} of ${evidence.windowDays}${
              l.memoDatedPayments && l.ledgerActiveDays !== undefined && l.ledgerActiveDays !== l.activeDays
                ? " (from invoice memos, demo seed)"
                : ""
            }`}
          />
          <KV k="Open loans" v={noneOr(l.activeLoans, `${l.activeLoans} · ${xrp(l.loanDebtDrops)}`)} />
          <KV k="Past defaults" v={noneOr(l.pastDefaults, <span className="bad-t">{l.pastDefaults}</span>)} />
        </div>
        <div className="col">
          <h4>Bank</h4>
          {bank ? (
            <>
              <div className="w">Counts for {w.bank}% of the score</div>
              <Score value={breakdown.bank?.score ?? null} />
              <KV k="Monthly inflow" v={`$${bank.avgMonthlyInflowUsd.toLocaleString("en-US")}`} />
              <KV k="Average balance" v={`$${bank.avgBalanceUsd.toLocaleString("en-US")}`} />
              <KV k="In vs out" v={bank.inflowOutflowRatio.toFixed(2)} />
              <KV k="Bounced payments" v={noneOr(bank.nsfCount, bank.nsfCount)} />
              <KV k="History" v={`${bank.days} days`} />
            </>
          ) : (
            <>
              <div className="w">Not connected</div>
              <Score value={null} />
              <p>Bank data isn't connected, so its share of the score moved to on-chain history. No credit bureaus are used.</p>
            </>
          )}
        </div>
        <div className="col">
          <h4>What they told us</h4>
          <div className="w">Counts for {w.declared}% of the score</div>
          <Score value={breakdown.declared.score} />
          <KV k="Purpose" v={purposeLabel(d.purpose)} />
          <KV k="Amount" v={xrp(d.principalDrops)} />
          <KV k="Term" v={`${duration(d.termSeconds)}${paymentTotal ? `, ${paymentsWord(paymentTotal)}` : ""}`} />
          <KV k="Existing debt" v={noneOr(Number(d.existingDebtDrops), xrp(d.existingDebtDrops))} />
        </div>
      </div>
      <SecondOpinionBlock r={r} />
      <ul className="sum">
        <li>
          <span>
            Combined score is <b>{breakdown.total}</b>: {parts.join(" plus ")}.
          </span>
        </li>
        {cred && (
          <li>
            <span>
              KYB credential {l.credentialType ?? "kyb-borrower"}, issued by the broker{" "}
              <span className="mono" title={l.credentialIssuer}>{l.credentialIssuer?.slice(0, 5)}…</span>: +{cred.pts} ledger points
              (about +{cred.total} on the score).
            </span>
          </li>
        )}
        {r.policyHash && (
          <li>
            <span>
              Decided under policy <span className="mono" title={r.policyHash}>{r.policyHash.slice(0, 6)}…</span>, the
              hash of the rules in force at the time.
            </span>
          </li>
        )}
        {breakdown.capped && (
          <li className="bad">
            <span>The score is capped because this borrower has defaulted before.</span>
          </li>
        )}
        {after && policy && (
          <li className={after.utilPct > policy.maxUtilizationPct ? "bad" : ""}>
            <span>
              If approved, <b>{pct1(after.utilPct)}%</b> of the vault would be lent out. The limit is {policy.maxUtilizationPct}%.
            </span>
          </li>
        )}
        {after && policy && (
          <li className={after.coverPct < policy.minCoverRatioPct ? "bad" : ""}>
            <span>
              First-loss cover would be <b>{pct1(after.coverPct)}%</b> of debt. The minimum is {policy.minCoverRatioPct}%.
            </span>
          </li>
        )}
        {b && (
          <li>
            <span>
              <b>{xrp(b.supplierDrops)}</b> would go straight to the supplier <Addr addr={b.supplier} plain /> with invoice{" "}
              <span className="mono">{b.invoice}</span>, and <b>{xrp(b.feeDrops)}</b> to the broker, in one all-or-nothing batch
              {BigInt(sumDrops(b.supplierDrops, b.feeDrops)) < BigInt(r.principalDrops)
                ? `; the borrower keeps the other ${xrp(String(BigInt(r.principalDrops) - BigInt(sumDrops(b.supplierDrops, b.feeDrops))))}`
                : ""}
              .
            </span>
          </li>
        )}
        <li>
          <span>The loan needs two signatures: the borrower already signed, your click adds the broker's.</span>
        </li>
      </ul>
    </div>
  );
}
