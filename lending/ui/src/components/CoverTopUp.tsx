import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { DESK_HOST, DeskError, topUpCover } from "../api";
import { xrp } from "../format";
import type { CoverTopUp as Result } from "../types";
import { Explorer } from "./bits";

const MAX_DROPS = 100_000_000n; // the desk refuses more than 100 XRP per top-up

/** "20" / "0.5" XRP -> drops, or null when it is not a positive amount with at most 6 decimals. */
function toDrops(s: string): bigint | null {
  const m = /^(\d+)(?:\.(\d{1,6}))?$/.exec(s.trim());
  if (!m) return null;
  return BigInt(m[1]) * 1_000_000n + BigInt((m[2] ?? "").padEnd(6, "0"));
}

function plainError(e: unknown): string {
  if (e instanceof DeskError) {
    if (e.message === "amount_out_of_range") return "Enter an amount above 0 and up to 100 XRP.";
    if (e.message === "cover_deposit_in_progress") return "Another top-up is still running. Wait for it to finish.";
    if (e.message.startsWith("ledger_unavailable"))
      return "The desk could not reach devnet, so no deposit was confirmed. Check the cover figure before you try again.";
    return `The desk refused the top-up (${e.message}).`;
  }
  return `The desk at ${DESK_HOST} did not answer, so no deposit was confirmed.`;
}

type Phase =
  | { k: "idle" }
  | { k: "edit"; error?: string }
  | { k: "confirm"; drops: bigint }
  | { k: "busy"; drops: bigint }
  | { k: "done"; drops: bigint; res: Result }
  | { k: "fail"; error: string };

/** "Top up cover" on the First-loss cover tile: LoanBrokerCoverDeposit signed by the broker key in the desk. */
export function CoverTopUp({ onDone }: { onDone: () => void }) {
  const [phase, setPhase] = useState<Phase>({ k: "idle" });
  const [amount, setAmount] = useState("20");
  const input = useRef<HTMLInputElement>(null);
  const confirmBtn = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (phase.k === "edit") input.current?.focus();
    if (phase.k === "confirm") confirmBtn.current?.focus();
  }, [phase.k]);

  const review = () => {
    const d = toDrops(amount);
    if (d == null || d <= 0n || d > MAX_DROPS) setPhase({ k: "edit", error: "Enter an amount above 0 and up to 100 XRP." });
    else setPhase({ k: "confirm", drops: d });
  };

  const submit = async (drops: bigint) => {
    setPhase({ k: "busy", drops });
    try {
      const res = await topUpCover(String(drops));
      if (res.engineResult === "tesSUCCESS") setPhase({ k: "done", drops, res });
      else setPhase({ k: "fail", error: `The ledger did not accept the deposit (${res.engineResult ?? "no result"}). Cover is unchanged.` });
    } catch (e) {
      setPhase({ k: "fail", error: plainError(e) });
    }
    onDone();
  };

  const cancel = () => setPhase({ k: "idle" });
  const onKey = (e: KeyboardEvent) => {
    if (e.key === "Escape" && (phase.k === "edit" || phase.k === "confirm")) cancel();
  };

  return (
    <div className="topup" onKeyDown={onKey}>
      {phase.k === "idle" && (
        <button type="button" className="link-btn" onClick={() => setPhase({ k: "edit" })}>
          Top up cover
        </button>
      )}
      {phase.k === "edit" && (
        <form
          className="row-f"
          onSubmit={(e) => {
            e.preventDefault();
            review();
          }}
        >
          <label htmlFor="topup-xrp">Add</label>
          <input
            id="topup-xrp"
            ref={input}
            inputMode="decimal"
            autoComplete="off"
            value={amount}
            aria-invalid={!!phase.error}
            aria-describedby={phase.error ? "topup-err" : undefined}
            onChange={(e) => setAmount(e.target.value)}
          />
          <span className="muted">XRP</span>
          <button type="submit" className="btn-sm">
            Review
          </button>
          <button type="button" className="link-btn" onClick={cancel}>
            Cancel
          </button>
          {phase.error && (
            <div id="topup-err" className="bad-t msg" role="alert">
              {phase.error}
            </div>
          )}
        </form>
      )}
      {phase.k === "confirm" && (
        <div className="row-f">
          <span className="msg">
            Deposit <b>{xrp(String(phase.drops))}</b> from the broker account into first-loss cover?
          </span>
          <button type="button" ref={confirmBtn} className="btn-sm" onClick={() => void submit(phase.drops)}>
            Confirm deposit
          </button>
          <button type="button" className="link-btn" onClick={() => setPhase({ k: "edit" })}>
            Back
          </button>
        </div>
      )}
      <div aria-live="polite">
        {phase.k === "busy" && (
          <div className="msg live">
            <i className="pulse" aria-hidden="true" />
            Depositing {xrp(String(phase.drops))}: the desk signs with the broker key and waits for the ledger…
          </div>
        )}
        {phase.k === "done" && (
          <div className="msg">
            <span className="ok-t">Cover topped up by {xrp(String(phase.drops))}.</span>{" "}
            {phase.res.coverAfterDrops != null
              ? `Now ${xrp(phase.res.coverAfterDrops)} (was ${xrp(phase.res.coverBeforeDrops)}).`
              : `Was ${xrp(phase.res.coverBeforeDrops)}.`}{" "}
            {phase.res.hash && <Explorer hash={phase.res.hash} />}{" "}
            <button type="button" className="link-btn" onClick={cancel}>
              Done
            </button>
          </div>
        )}
        {phase.k === "fail" && (
          <div className="msg" role="alert">
            <span className="bad-t">{phase.error}</span>{" "}
            <button type="button" className="link-btn" onClick={() => setPhase({ k: "edit" })}>
              Try again
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
