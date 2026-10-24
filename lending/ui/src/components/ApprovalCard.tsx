import { useEffect, useRef, useState } from "react";
import { DeskError, WalletError, approveHeld, deny } from "../api";
import { deskErrorWords, purposePhrase, reasonSentence, walletErrorWords } from "../copy";
import { clock, duration, groupInt, paymentsWord, xrpNum } from "../format";
import { txLedgerIndex } from "../ledger";
import type { Breakdown, Evidence, LoanRequest, Policy, Vault } from "../types";
import { batchOf, BatchSteps, BatchSummary } from "./BatchView";
import { Addr, Dot, Hash, Icon, LatestNote } from "./bits";
import { WhyBody } from "./WhyPanel";

const C = 2 * Math.PI * 52;

function band(score: number, p: Policy | null): { label: string; tone: "ok" | "warn" | "bad" } {
  if (p && score >= p.minScoreAuto) return { label: "High confidence", tone: "ok" };
  if (p && score >= p.minScore) return { label: "Medium confidence", tone: "warn" };
  return { label: "Low confidence", tone: "bad" };
}

function Ring({ score, policy, policyHash }: { score: number | null; policy: Policy | null; policyHash?: string }) {
  const s = score ?? 0;
  const b = band(s, policy);
  return (
    <div className="ring">
      <svg viewBox="0 0 120 120" role="img" aria-label={`Score ${score ?? "unknown"} out of 100`}>
        <circle cx="60" cy="60" r="52" fill="none" stroke="var(--line)" strokeWidth="8" />
        <circle
          cx="60"
          cy="60"
          r="52"
          fill="none"
          stroke="var(--fg)"
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={C.toFixed(1)}
          strokeDashoffset={(C * (1 - Math.max(0, Math.min(100, s)) / 100)).toFixed(1)}
          transform="rotate(-90 60 60)"
        />
        <text x="60" y="60" textAnchor="middle" dominantBaseline="central" fill="var(--fg)" fontFamily="Inter, system-ui, sans-serif" fontWeight="600" fontSize="30">
          {score ?? "–"}
        </text>
      </svg>
      <div className="lab">
        <Dot tone={b.tone} />
        {b.label}
      </div>
      <div className="lab2">Score out of 100</div>
      {policyHash && (
        <div className="lab2 mono" title={`Decided under policy ${policyHash} (sha256 of the policy JSON)`}>
          policy {policyHash.slice(0, 6)}…
        </div>
      )}
    </div>
  );
}

const WHY_KEY = "lending.why-open";
function initialWhy(): boolean {
  try {
    const q = new URLSearchParams(location.search).get("why");
    if (q) return q === "open";
    return localStorage.getItem(WHY_KEY) === "1";
  } catch {
    return false;
  }
}

/** Approve progress: 1 co-signing, 2 submitted, 3 validated (from the response), or failed. */
export type Progress = { step: 1 | 2 | 3; rec?: LoanRequest; ledgerIndex?: number | null; error?: string; denied?: boolean };

const hasEvidence = (r: LoanRequest): r is LoanRequest & { evidence: Evidence } => !!r.evidence && "ledger" in r.evidence;
const breakdownOf = (r: LoanRequest): Breakdown | null => (r.breakdown && "weights" in r.breakdown ? (r.breakdown as Breakdown) : null);

export function ApprovalCard({
  r,
  policy,
  vault,
  now,
  paymentInterval,
  progress,
  setProgress,
  onChange,
  onDismiss,
}: {
  r: LoanRequest;
  policy: Policy | null;
  vault: Vault | null;
  now: number;
  paymentInterval: number | null;
  progress: Progress | undefined;
  setProgress: (p: Progress | undefined) => void;
  onChange: () => void;
  onDismiss: () => void;
}) {
  const [why, setWhy] = useState(initialWhy);
  const [busy, setBusy] = useState<"approve" | "deny" | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => () => void (timer.current && clearTimeout(timer.current)), []);

  const toggleWhy = () => {
    setWhy((o) => {
      try {
        localStorage.setItem(WHY_KEY, o ? "0" : "1");
      } catch {
        /* storage blocked */
      }
      return !o;
    });
  };

  const words = (e: unknown) =>
    e instanceof WalletError
      ? walletErrorWords(e.status, e.reason)
      : e instanceof DeskError
        ? deskErrorWords(e.status, e.message, policy)
        : deskErrorWords(0, String(e), policy);

  async function onApprove() {
    setBusy("approve");
    setErr(null);
    setProgress({ step: 1 });
    // The desk call is synchronous: co-sign, submit, wait for validation. Show step 2 while it is in flight.
    timer.current = setTimeout(() => setProgress({ step: 2 }), 1200);
    try {
      const rec = await approveHeld(r.id);
      if (timer.current) clearTimeout(timer.current);
      if (rec.status === "approved" && rec.txHash) {
        setProgress({ step: 3, rec, ledgerIndex: undefined });
        const li = await txLedgerIndex(rec.txHash);
        setProgress({ step: 3, rec, ledgerIndex: li });
      } else {
        setProgress({ step: 2, rec, error: reasonSentence(rec, policy, vault).lead + " " + reasonSentence(rec, policy, vault).rest });
      }
    } catch (e) {
      if (timer.current) clearTimeout(timer.current);
      setProgress(undefined);
      setErr(words(e));
    } finally {
      setBusy(null);
      onChange();
    }
  }

  async function onDeny() {
    setBusy("deny");
    setErr(null);
    try {
      await deny(r.id);
      setProgress({ step: 1, denied: true });
    } catch (e) {
      setErr(words(e));
    } finally {
      setBusy(null);
      onChange();
    }
  }

  const done = progress?.step === 3 || !!progress?.error || progress?.denied;
  const live = r.status === "held" && !done;
  const left = policy ? r.ts + policy.holdTimeoutSeconds - now : null;
  const n = paymentInterval ? Math.max(1, Math.floor(r.termSeconds / paymentInterval)) : null;
  const held = reasonSentence(r, policy, vault);
  const ev = hasEvidence(r) ? r.evidence : null;
  const bd = breakdownOf(r);
  const result = progress?.rec;
  const batch = batchOf(r);
  const shown = result ?? r; // after approve, the record the desk returned carries the batch legs

  return (
    <article className="card" aria-label={`Loan request ${r.id}`}>
      <div className="top">
        <div>
          <div className="amt num">
            {xrpNum(r.principalDrops)}
            <small>XRP</small>
          </div>
          <p className="story">
            <Addr addr={r.borrower} /> wants a loan {purposePhrase(r)}. They would pay it back over {duration(r.termSeconds)}
            {n ? ` in ${paymentsWord(n)}` : ""}.
          </p>
          <LatestNote r={r} />
          {batch && (
            <>
              <BatchSummary batch={batch} />
              <BatchSteps r={shown} batch={batchOf(shown) ?? batch} />
            </>
          )}
        </div>
        <Ring score={r.score} policy={policy} policyHash={r.policyHash} />
      </div>

      {progress?.denied ? (
        <div className="held">
          <Dot tone="bad" />
          <b>You denied this request.</b> No transaction was made.
        </div>
      ) : progress?.step === 3 ? (
        <div className="held">
          <Dot tone="ok" />
          <b>Approved by you.</b> The broker key co-signed the borrower's LoanSet and devnet validated it.
          {result?.approvedBy && (
            <>
              {" "}
              Approved by {result.approvedBy === "operator" ? "the operator" : <Addr addr={result.approvedBy} />}
              {result.approvedAt ? ` at ${new Date(result.approvedAt * 1000).toLocaleTimeString()}` : ""}.
            </>
          )}
        </div>
      ) : (
        held.lead && (
          <div className="held">
            <Dot tone={held.tone} />
            <b>{held.lead}</b> {held.rest}
          </div>
        )
      )}

      <div className="actions">
        {done ? (
          <button type="button" className="btn-ghost" onClick={onDismiss}>
            Dismiss
          </button>
        ) : (
          <>
            <button type="button" className="btn-ok" disabled={!live || busy !== null} onClick={onApprove}>
              {busy === "approve" ? "Working…" : "Approve"}
            </button>
            <button type="button" className="btn-ghost" disabled={!live || busy !== null} onClick={onDeny}>
              {busy === "deny" ? "Denying…" : "Deny"}
            </button>
          </>
        )}
        {live && left != null && (
          <div className="expires">
            Expires in <span className="t num">{left > 0 ? clock(left) : "now"}</span>
          </div>
        )}
      </div>

      {err && (
        <div className="err" role="alert">
          <span>●</span>
          <span>{err}</span>
        </div>
      )}

      {progress && !progress.denied && (
        <div className="progress" aria-live="polite">
          <div className={`step ${progress.step > 1 || done ? "done" : "live"}`}>
            <i />
            Co-signing on the broker key…
          </div>
          <div className={`step ${progress.error ? "fail" : progress.step >= 3 ? "done" : progress.step === 2 ? "live" : ""}`}>
            <i />
            Submitted to devnet, waiting for validation…
          </div>
          {progress.error ? (
            <div className="step fail">
              <i />
              <span className="bad-t">{progress.error}</span>
              {result?.txHash && <Hash hash={result.txHash} />}
            </div>
          ) : (
            <div className={`step ${progress.step === 3 ? "done" : ""}`}>
              <i />
              {progress.step === 3 && result?.txHash ? (
                <span>
                  Validated
                  {progress.ledgerIndex ? (
                    <>
                      {" "}
                      in ledger <span className="num">{groupInt(progress.ledgerIndex)}</span>
                    </>
                  ) : progress.ledgerIndex === undefined ? (
                    " …"
                  ) : null}{" "}
                  · tx <Hash hash={result.txHash} /> · the loan is live
                  {result.batch?.hash && (
                    <>
                      {" "}
                      · batch <Hash hash={result.batch.hash} />
                    </>
                  )}
                </span>
              ) : (
                "Validated"
              )}
            </div>
          )}
        </div>
      )}

      {ev && bd && (
        <div className={`why ${why ? "open" : ""}`}>
          <button type="button" aria-expanded={why} onClick={toggleWhy}>
            Why this score
            <span>
              {why ? "" : "Three sources, one plain breakdown"}
              {Icon.chevron()}
            </span>
          </button>
          {why && <WhyBody r={r} evidence={ev} breakdown={bd} vault={vault} policy={policy} paymentTotal={n} />}
        </div>
      )}
    </article>
  );
}
