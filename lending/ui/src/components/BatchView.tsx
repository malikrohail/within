import { useState } from "react";
import type { BatchInfo, LoanRequest } from "../types";
import { xrp } from "../format";
import { Addr, Hash, Icon } from "./bits";

export const batchOf = (r: LoanRequest): BatchInfo | null => (r.kind === "working_capital" && r.batch ? r.batch : null);

export const BatchPill = () => <span className="tag batch">Batch</span>;

function LegTag({ result }: { result: string | null }) {
  if (result === "tesSUCCESS") return <span className="tag ok">applied ✓</span>;
  if (result === "not_applied") return <span className="tag bad">not applied</span>;
  if (result === "not_validated") return <span className="tag warn">not validated</span>;
  if (!result) return <span className="tag">not sent</span>;
  return <span className="tag bad">{result}</span>;
}

/** Raw engine result for the expanded view: tesSUCCESS green, not_applied red "rolled back". */
function ResultTag({ result }: { result: string | null }) {
  if (result === "tesSUCCESS") return <span className="tag code ok">tesSUCCESS</span>;
  if (result === "not_applied") return <span className="tag code bad">not_applied · rolled back</span>;
  if (result === "not_validated") return <span className="tag code warn">not_validated</span>;
  if (!result) return <span className="tag code">not sent</span>;
  return <span className="tag code bad">{result}</span>;
}

/** One line: Batch pill, supplier amount and address, fee, invoice. */
export function BatchSummary({ batch }: { batch: BatchInfo }) {
  return (
    <div className="wc">
      <BatchPill />
      <span>
        <b>{xrp(batch.supplierDrops)}</b> to supplier <Addr addr={batch.supplier} />
      </span>
      <span>·</span>
      <span>
        fee <b>{xrp(batch.feeDrops)}</b>
      </span>
      <span>·</span>
      <span>
        invoice <span className="mono">{batch.invoice}</span>
      </span>
    </div>
  );
}

/** Expandable: 1 the LoanSet, 2 the outer all-or-nothing Batch, then (unless withLegs is false) each inner leg with its own result. */
export function BatchSteps({ r, batch, withLegs = true }: { r: LoanRequest; batch: BatchInfo; withLegs?: boolean }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="steps">
      <button type="button" className="more" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        {open ? "Hide the transactions" : "Show the transactions"}
        {Icon.chevron()}
      </button>
      {open && (
        <div className="list">
          <div>
            <span className="k">1 · LoanSet</span>
            <span>
              <b>{xrp(r.principalDrops)}</b> loan
            </span>
            <Hash hash={r.txHash} />
            <ResultTag result={r.engineResult} />
          </div>
          <div>
            <span className="k">2 · Batch</span>
            <span>all-or-nothing</span>
            <Hash hash={batch.hash} />
            <ResultTag result={batch.engineResult} />
          </div>
          {!withLegs ? null : batch.legs.length === 0 ? (
            <div className="leg">
              <span className="k">planned</span>
              <span>
                <b>{xrp(batch.supplierDrops)}</b> to supplier, <b>{xrp(batch.feeDrops)}</b> broker fee
              </span>
            </div>
          ) : (
            batch.legs.map((leg) => (
              <div className="leg" key={leg.hash || leg.index}>
                <span className="k">leg {leg.index + 1}</span>
                <span>{leg.type}</span>
                <span>
                  to <Addr addr={leg.destination} />
                </span>
                <b>{xrp(leg.amountDrops)}</b>
                <span>{leg.destination === batch.supplier ? "supplier" : "broker fee"}</span>
                <Hash hash={leg.hash} />
                <ResultTag result={leg.result} />
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}

/** The two batch legs as Activity sub-rows: supplier payment, then broker fee, each with its inner hash. */
export function BatchLegs({ r, batch }: { r: LoanRequest; batch: BatchInfo }) {
  const sup = batch.legs.find((l) => l.destination === batch.supplier) ?? batch.legs[0];
  const fee = batch.legs.find((l) => l !== sup);
  const rolledBack = batch.legs.length > 0 && batch.legs.every((l) => l.result === "not_applied");
  return (
    <div className="legs">
      <div>
        <b>{xrp(sup?.amountDrops ?? batch.supplierDrops)}</b> to supplier <Addr addr={batch.supplier} /> · invoice{" "}
        <span className="mono">{batch.invoice}</span>
        <LegTag result={sup?.result ?? null} />
        <Hash hash={sup?.hash} />
      </div>
      <div>
        <b>{xrp(fee?.amountDrops ?? batch.feeDrops)}</b> broker fee
        <LegTag result={fee?.result ?? null} />
        <Hash hash={fee?.hash} />
      </div>
      {rolledBack && (
        <div className="bad-t">The batch landed and its network fee was charged, but all-or-nothing rolled back both payments.</div>
      )}
      <BatchSteps r={r} batch={batch} withLegs={false} />
    </div>
  );
}
