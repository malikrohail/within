import { useState } from "react";
import { setDelegation, type DelegateAction, type DelegateResult, type Delegation, type WalletStatus } from "../api";
import { explorerAccount, explorerTx, shortAccount, shortHash } from "../format";
import { describe, walletCtx } from "../preview";
import { PreviewCard } from "./PreviewCard";

const BLIND_NOTE = "The Ledger shows this as 'Transaction Type: Unknown'; this card is what it actually does.";

const pill = "inline-block rounded-full px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wide ring-1";

function Account({ address }: { address: string | undefined }) {
  return address ? (
    <a className="font-mono text-fg hover:text-accent" href={explorerAccount(address)} target="_blank" rel="noreferrer" title={address}>
      {shortAccount(address)}
    </a>
  ) : (
    <span className="font-mono">—</span>
  );
}

/** `delegation` is null before the first load, "unavailable" when the wallet has no /v1/delegate route (404), and { error } when the first load failed. */
export function Permissions({
  delegation,
  status,
  onChange,
}: {
  delegation: Delegation | "unavailable" | { error: string } | null;
  status: WalletStatus | null;
  onChange: () => void;
}) {
  // The POST blocks until someone approves on the Ledger, so the buttons show a waiting state until it resolves.
  const [busy, setBusy] = useState<DelegateAction | null>(null);
  // Revoke asks for a second click instead of a browser dialog.
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [last, setLast] = useState<DelegateResult | null>(null);

  const send = (action: DelegateAction) => {
    if (action === "revoke" && !confirming) {
      setConfirming(true);
      return;
    }
    setConfirming(false);
    setBusy(action);
    setError(null);
    setLast(null);
    setDelegation(action)
      .then((res) => {
        setLast(res);
        onChange();
      })
      .catch((e) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setBusy(null));
  };

  const d = delegation !== null && typeof delegation === "object" && "treasury" in delegation ? delegation : null;
  // The DelegateSet each button sends, built here so the card can be read before the Ledger shows it blind.
  const treasury = d?.treasury ?? status?.deviceAccount;
  const agent = d?.agent ?? status?.hotAccount;
  const previewOf = (grant: boolean) =>
    treasury && agent
      ? describe(
          {
            TransactionType: "DelegateSet",
            Account: treasury,
            Authorize: agent,
            Permissions: grant ? [{ Permission: { PermissionValue: "Payment" } }] : [],
          },
          walletCtx(status),
        )
      : null;
  const revokePreview = confirming ? previewOf(false) : null;
  const grantPreview = previewOf(true);

  return (
    <section className="panel">
      <h2 className="panel-title">Agent permissions</h2>
      <p className="-mt-2 mb-4 text-xs text-muted">
        Treasury <Account address={d?.treasury} /> delegates on-ledger permissions to agent <Account address={d?.agent} />. Grant and revoke are
        DelegateSet transactions signed on the Ledger: approve them in Pending approvals. The Ledger shows a blind-signing warning first
        (XRP app 2.8.1 cannot clear-sign DelegateSet).
      </p>
      {delegation === "unavailable" ? (
        <p className="text-muted">Not available on this wallet build (no /v1/delegate).</p>
      ) : delegation === null ? (
        <p className="text-muted">Loading…</p>
      ) : !d ? (
        <p className="text-bad">Could not load permissions: {(delegation as { error: string }).error}</p>
      ) : (
        <div className="flex flex-wrap items-center gap-2 text-sm">
          {d.permissions.length === 0 ? (
            <span className={`${pill} bg-bad/15 text-bad ring-bad/40`}>no permissions</span>
          ) : (
            d.permissions.map((p) => (
              <span key={p} className={`${pill} bg-ok/15 text-ok ring-ok/40`}>
                {p}
              </span>
            ))
          )}
        </div>
      )}
      {delegation !== "unavailable" && (
        <>
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <button
              className="rounded-lg border border-bad px-4 py-2 text-sm font-semibold text-bad hover:bg-bad/10 disabled:cursor-not-allowed disabled:opacity-50"
              disabled={busy !== null}
              onClick={() => send("revoke")}
            >
              {busy === "revoke" ? "Revoking…" : confirming ? "Confirm revoke" : "Revoke agent"}
            </button>
            {confirming && (
              <button className="text-xs text-muted hover:text-fg" onClick={() => setConfirming(false)}>
                Cancel
              </button>
            )}
            <button
              className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-ink hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-50"
              disabled={busy !== null}
              onClick={() => send("grant")}
            >
              {busy === "grant" ? "Granting…" : "Re-grant"}
            </button>
            {grantPreview && !confirming && busy === null && (
              <details className="text-xs text-muted">
                <summary className="cursor-pointer hover:text-fg">What Re-grant sends</summary>
                <div className="mt-2 max-w-xl space-y-1">
                  <PreviewCard preview={grantPreview} compact />
                  <p>{BLIND_NOTE}</p>
                </div>
              </details>
            )}
            {busy && <span className="text-sm text-amber">Waiting for approval on the Ledger…</span>}
          </div>
          {revokePreview && (
            <div className="mt-3 max-w-xl space-y-1">
              <PreviewCard preview={revokePreview} />
              <p className="text-xs text-muted">{BLIND_NOTE}</p>
            </div>
          )}
          {error && <p className="mt-2 text-sm text-bad">{error}</p>}
          {last && (
            <p className="mt-2 text-xs text-muted">
              {last.action === "grant" ? "Granted" : "Revoked"} · {last.engineResult} ·{" "}
              <a className="font-mono text-accent hover:underline" href={explorerTx(last.txHash)} target="_blank" rel="noreferrer" title={last.txHash}>
                {shortHash(last.txHash)}
              </a>
            </p>
          )}
        </>
      )}
    </section>
  );
}
