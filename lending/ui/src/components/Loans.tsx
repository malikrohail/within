import { useEffect, useRef, useState, type ReactNode } from "react";
import { clock, short, xrp, xrpFixed } from "../format";
import { findDefaults, type DefaultInfo } from "../ledger";
import type { Loan, LoanRequest } from "../types";
import { Addr, Dot, Explorer } from "./bits";

const STATUS = {
  active: { tone: "ok", label: "Active" },
  impaired: { tone: "warn", label: "Impaired" },
  defaulted: { tone: "bad", label: "Defaulted" },
  paid: { tone: "dim", label: "Paid off" },
} as const;

const RETRY_FIRST_MS = 2000;
const RETRY_MAX_MS = 30000;

/** Fallback only: for defaulted loans the desk has no `default` for yet, look the LoanManage(default)
 *  up on devnet over WebSocket. A failure or a miss retries with backoff (2 s doubling to 30 s). */
function useDefaultFallback(broker: string | undefined, ids: string[]): Record<string, DefaultInfo> {
  const [found, setFound] = useState<Record<string, DefaultInfo>>({});
  const need = ids.filter((id) => !found[id]);
  const key = need.join(",");
  const delay = useRef(RETRY_FIRST_MS);
  useEffect(() => {
    if (!broker || need.length === 0) return;
    delay.current = RETRY_FIRST_MS; // a new set of loans to find starts the backoff over
    let stop = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const retry = () => {
      timer = setTimeout(attempt, delay.current);
      delay.current = Math.min(delay.current * 2, RETRY_MAX_MS);
    };
    const attempt = () => {
      findDefaults(broker, need)
        .then((m) => {
          if (stop) return;
          const hits = need.filter((id) => m[id]);
          if (hits.length) setFound((f) => ({ ...f, ...Object.fromEntries(hits.map((id) => [id, m[id]])) }));
          if (hits.length < need.length) retry();
        })
        .catch(() => {
          if (!stop) retry(); // devnet unreachable: try again later, never give up silently
        });
    };
    attempt();
    return () => {
      stop = true;
      clearTimeout(timer);
    };
  }, [broker, key]);
  return found;
}

function LoanRow({ l, req, now, dflt }: { l: Loan; req: LoanRequest | undefined; now: number; dflt: DefaultInfo | undefined }) {
  const st = STATUS[l.status] ?? STATUS.active;
  // Original size and schedule come from the request; the ledger zeroes them on a default.
  const original = req?.principalDrops ?? l.principalDrops;
  const total = req ? Math.max(1, Math.floor(req.termSeconds / l.paymentInterval)) : null;
  const made = total != null ? total - l.paymentRemaining : null;
  const left = l.nextPaymentDue - now;

  let progLeft: ReactNode;
  let progRight: ReactNode;
  let fill = 0;
  if (l.status === "defaulted") {
    progLeft = total ? `${total}-payment loan` : "Payment missed";
    progRight = <span className="bad-t">Missed</span>;
    fill = 100;
  } else if (l.status === "paid") {
    progLeft = total ? (
      <span>
        <b>{total} of {total}</b> payments made
      </span>
    ) : (
      "All payments made"
    );
    progRight = "Paid off";
    fill = 100;
  } else {
    progLeft =
      total != null && made != null ? (
        <span>
          <b>
            {made} of {total}
          </b>{" "}
          payments made
        </span>
      ) : (
        `${l.paymentRemaining} payments left`
      );
    progRight =
      left >= 0 ? (
        <span>
          next due in <b className="num">{clock(left)}</b>
        </span>
      ) : (
        <span className="warn-t num">
          overdue {clock(-left)} · {-left < l.gracePeriod ? `grace ${clock(l.gracePeriod + left)} left` : "grace over"}
        </span>
      );
    fill = total && made != null ? (100 * made) / total : 0;
  }

  return (
    <div className="loan-wrap">
      <div className={`loan ${l.status === "defaulted" ? "bad" : l.status === "paid" ? "paid" : ""}`}>
        <div className="who">
          <Addr addr={l.borrower} />
          <small>{xrpFixed(original)} XRP loan</small>
        </div>
        <div className="prog">
          <div className="l">
            <span>{progLeft}</span>
            {progRight}
          </div>
          <div className="bar">
            <i style={{ width: `${fill}%` }} />
          </div>
        </div>
        <div className="r num">
          {xrpFixed(l.totalOutstandingDrops)} XRP
          <small className={`${st.tone}-t`}>
            <Dot tone={st.tone} />
            {st.label}
          </small>
        </div>
      </div>
      {(l.sweeps ?? []).map((s) => (
        <div className="strip" role="note" key={s.loanPayHash}>
          {s.status === "repaid" ? (
            <>
              <Dot tone="ok" />
              <span>
                Repaid automatically from x402 income · <b>{xrp(s.drops)}</b> ·{" "}
                <Explorer hash={s.loanPayHash}>{short(s.loanPayHash)}</Explorer>
              </span>
            </>
          ) : (
            <>
              <Dot tone="bad" />
              <span>
                Automatic repayment failed: <b>{s.engineResult}</b> ·{" "}
                <Explorer hash={s.loanPayHash}>{short(s.loanPayHash)}</Explorer>
              </span>
            </>
          )}
        </div>
      ))}
      {l.status === "defaulted" && (
        <div className="strip" role="note">
          <Dot tone="bad" />
          <b>Missed payment.</b>
          {dflt?.coverAbsorbedDrops != null ? (
            // stated once: the depositor line below repeats the cover hit when the vault loss is known
            dflt.vaultLossDrops == null && (
              <span>
                Broker cover absorbed <b>{xrp(dflt.coverAbsorbedDrops)}</b>.
              </span>
            )
          ) : (
            <span className="muted" aria-live="polite">
              Cover hit loading…
            </span>
          )}
          {dflt?.hash && <Explorer hash={dflt.hash}>View the default on explorer</Explorer>}
          {dflt?.coverAbsorbedDrops != null && dflt.vaultLossDrops != null && (
            <span className="strip-line">
              Cover absorbed <b>{xrp(dflt.coverAbsorbedDrops)}</b> first, depositors absorbed <b>{xrp(dflt.vaultLossDrops)}</b>.
            </span>
          )}
        </div>
      )}
    </div>
  );
}

export function Loans({ loans, requests, broker, now }: { loans: Loan[]; requests: LoanRequest[]; broker: string | undefined; now: number }) {
  // The desk's stored default wins; the devnet lookup runs only for loans it has none for yet.
  const fallback = useDefaultFallback(
    broker,
    loans.filter((l) => l.status === "defaulted" && !l.default).map((l) => l.loanId),
  );
  const byId = new Map(requests.map((r) => [r.id, r]));
  return (
    <section>
      <h3>
        Loans <span className="count">{loans.length}</span>
      </h3>
      {loans.length === 0 ? (
        <div className="empty">No loans on the ledger yet.</div>
      ) : (
        loans.map((l) => (
          <LoanRow key={l.loanId} l={l} req={l.requestId ? byId.get(l.requestId) : undefined} now={now} dflt={l.default ?? fallback[l.loanId]} />
        ))
      )}
    </section>
  );
}
