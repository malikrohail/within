import { useState } from "react";
import { deny, deviceTap, type Policy, type WalletRequest } from "../api";
import { dropsToXrp, relativeTime, shortAccount } from "../format";
import { PreviewCard } from "./PreviewCard";

type Action = "approve" | "deny";

export function Pending({ requests, policy, now, onChange }: { requests: WalletRequest[]; policy: Policy | null; now: number; onChange: () => void }) {
  const held = requests.filter((r) => r.status === "held");
  // A sent tap stays "sent" until the wallet resolves the row and it leaves this list.
  const [sent, setSent] = useState<Record<string, Action>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});

  const act = async (id: string, action: Action) => {
    setSent((s) => ({ ...s, [id]: action }));
    setErrors(({ [id]: _, ...rest }) => rest);
    try {
      await (action === "approve" ? deviceTap(id) : deny(id));
      onChange();
    } catch (e) {
      setSent(({ [id]: _, ...rest }) => rest);
      setErrors((s) => ({ ...s, [id]: e instanceof Error ? e.message : String(e) }));
    }
  };

  return (
    <section className={`panel ${held.length > 0 ? "border-2 border-amber" : ""}`}>
      <h2 className="panel-title">
        Pending approvals{held.length > 0 && <span className="ml-2 text-amber">({held.length})</span>}
      </h2>
      {held.length === 0 ? (
        <p className="text-muted">Nothing waiting</p>
      ) : (
        <ul className="space-y-3">
          {held.map((r) => (
            <li key={r.id} className="flex flex-wrap items-center gap-4 rounded-lg bg-amber/10 p-4">
              <div className="min-w-0 flex-1">
                {r.kind === "delegate" ? (
                  // A DelegateSet from the treasury: no amount, the purpose is the headline.
                  <div className="text-xl font-semibold text-amber">{r.purpose || "Permission change"}</div>
                ) : (
                  <>
                    <div className="text-xl font-semibold tabular-nums text-amber">{dropsToXrp(r.amountDrops)} XRP</div>
                    <div className="truncate">{r.purpose || "—"}</div>
                  </>
                )}
                <div className="text-xs text-muted">
                  {r.kind === "delegate" ? "agent" : "to"}{" "}
                  <span className="font-mono" title={r.merchant}>{shortAccount(r.merchant)}</span> · waiting{" "}
                  {relativeTime(r.ts, now).replace(" ago", "")} · review is on the Ledger screen
                </div>
                {/* v1.6: the policy this request was decided under, and when that policy stops paying. */}
                {r.policyHash && (
                  <div className="text-xs text-muted">
                    policy <span className="font-mono" title={r.policyHash}>{r.policyHash.slice(0, 8)}…</span> ·{" "}
                    {policy?.expiresAt ? `expires ${new Date(policy.expiresAt).toLocaleString()}` : "no expiry"}
                  </div>
                )}
                {errors[r.id] && <div className="mt-1 text-sm text-bad">{errors[r.id]}</div>}
              </div>
              {/* v1.5: read the plain-English card, then approve on the Ledger. Older wallets send no preview. */}
              {r.loanPreview && (
                <div className="basis-full">
                  <div className="mb-1 text-xs font-semibold uppercase tracking-wider text-muted">The loan you are approving</div>
                  <PreviewCard preview={r.loanPreview} />
                  <div className="mb-1 mt-3 text-xs font-semibold uppercase tracking-wider text-muted">What the Ledger signs</div>
                </div>
              )}
              {r.preview && (
                <div className="basis-full">
                  <PreviewCard preview={r.preview} />
                </div>
              )}
              <div className="ml-auto flex gap-2">
                <button
                  className="rounded-lg bg-accent px-4 py-2 font-semibold text-ink hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-50"
                  disabled={r.id in sent}
                  onClick={() => act(r.id, "approve")}
                >
                  {sent[r.id] === "approve" ? "Signing on device…" : "Approve on device"}
                </button>
                <button
                  className="rounded-lg border border-bad px-4 py-2 font-semibold text-bad hover:bg-bad/10 disabled:cursor-not-allowed disabled:opacity-50"
                  disabled={r.id in sent}
                  onClick={() => act(r.id, "deny")}
                >
                  {sent[r.id] === "deny" ? "Denying…" : "Deny"}
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
