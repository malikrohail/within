import { Fragment, useState } from "react";
import type { WalletRequest } from "../api";
import { dropsToXrp, explorerTx, reasonText, relativeTime, shortAccount, shortHash } from "../format";
import { Pill } from "./Pill";
import { PreviewCard } from "./PreviewCard";

// An XRPL engine result (terNO_DELEGATE_PERMISSION, tec…) means the ledger itself refused the transaction.
const isEngineResult = (reason: string) => /^te[rcfm]/.test(reason);

export function Feed({ requests, now }: { requests: WalletRequest[]; now: number }) {
  // Rows with a v1.5 preview expand to its card on click.
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const toggle = (id: string) => setOpen(({ [id]: was, ...rest }) => (was ? rest : { ...rest, [id]: true }));

  return (
    <section className="panel">
      <h2 className="panel-title">Live feed</h2>
      {requests.length === 0 ? (
        <p className="text-muted">No requests yet.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-xs uppercase tracking-wide text-muted">
              <tr>
                <th className="py-2 pr-4 font-medium">When</th>
                <th className="py-2 pr-4 font-medium">Status</th>
                <th className="py-2 pr-4 font-medium">Merchant</th>
                <th className="py-2 pr-4 text-right font-medium">Amount</th>
                <th className="py-2 pr-4 font-medium">Purpose</th>
                <th className="py-2 pr-4 font-medium">Signer</th>
                <th className="py-2 font-medium">Tx</th>
              </tr>
            </thead>
            <tbody>
              {requests.map((r) => (
                // Keyed on status too, so a row that changes (held -> approved) fades in again.
                <Fragment key={`${r.id}:${r.status}`}>
                  <tr
                    className={`fade-in border-t border-line ${r.preview ? "cursor-pointer hover:bg-white/5" : ""}`}
                    onClick={r.preview ? () => toggle(r.id) : undefined}
                  >
                    <td className="whitespace-nowrap py-2 pr-4 text-muted" title={r.ts}>
                      {relativeTime(r.ts, now)}
                    </td>
                    <td className="py-2 pr-4">
                      <Pill status={r.status} />
                      {r.reason &&
                        (isEngineResult(r.reason) ? (
                          <span className="ml-2 text-xs text-bad" title={r.reason}>
                            ledger refused <span className="font-mono">{r.reason}</span>
                          </span>
                        ) : (
                          <span className="ml-2 text-xs text-bad" title={r.reason}>
                            {reasonText(r.reason)}
                          </span>
                        ))}
                    </td>
                    <td className="py-2 pr-4 font-mono" title={r.merchant}>
                      {shortAccount(r.merchant)}
                    </td>
                    <td className="whitespace-nowrap py-2 pr-4 text-right tabular-nums">
                      {r.kind === "delegate" ? <span className="text-muted">—</span> : `${dropsToXrp(r.amountDrops)} XRP`}
                    </td>
                    <td className="py-2 pr-4">
                      {r.purpose}
                      {r.preview && <span className="ml-2 text-xs text-muted">{open[r.id] ? "▾" : "▸"} details</span>}
                    </td>
                    <td className="whitespace-nowrap py-2 pr-4 text-muted">
                      {r.signer ?? "—"}
                      {r.source === "treasury" && (
                        <span className="ml-2 rounded px-1.5 py-0.5 text-xs text-accent ring-1 ring-accent/40">treasury</span>
                      )}
                    </td>
                    <td className="py-2 font-mono">
                      {r.txHash ? (
                        <a
                          className="text-accent hover:underline"
                          href={explorerTx(r.txHash)}
                          target="_blank"
                          rel="noreferrer"
                          title={r.txHash}
                          onClick={(e) => e.stopPropagation()}
                        >
                          {shortHash(r.txHash)}
                        </a>
                      ) : (
                        <span className="text-muted">—</span>
                      )}
                    </td>
                  </tr>
                  {r.preview && open[r.id] && (
                    <tr>
                      <td colSpan={7} className="pb-3">
                        <PreviewCard preview={r.preview} compact />
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
