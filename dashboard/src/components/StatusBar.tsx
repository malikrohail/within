import type { Policy, WalletStatus } from "../api";
import { dropsToXrp, explorerAccount, shortAccount } from "../format";

function Account({ label, account, balance }: { label: string; account: string | null; balance: string | null }) {
  return (
    <div className="min-w-0">
      <div className="text-xs uppercase tracking-wide text-muted">{label}</div>
      {account ? (
        <a className="font-mono text-sm text-fg hover:text-accent" href={explorerAccount(account)} target="_blank" rel="noreferrer">
          {shortAccount(account)}
        </a>
      ) : (
        <div className="font-mono text-sm text-muted">—</div>
      )}
      <div className="text-lg font-semibold tabular-nums">{dropsToXrp(balance)} XRP</div>
    </div>
  );
}

function Stat({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="text-xs uppercase tracking-wide text-muted">{label}</div>
      <div className="text-lg font-semibold tabular-nums">{children}</div>
    </div>
  );
}

export function StatusBar({ status, policy }: { status: WalletStatus | null; policy: Policy | null }) {
  if (!status) return <section className="panel text-muted">Waiting for wallet status…</section>;
  return (
    <section className="panel grid grid-cols-2 gap-6 md:grid-cols-5">
      <Account label="Hot account (auto)" account={status.hotAccount} balance={status.hotBalanceDrops} />
      <Account label="Device account (Ledger)" account={status.deviceAccount} balance={status.deviceBalanceDrops} />
      <Stat label="Device">
        <span className={status.deviceConnected ? "text-ok" : "text-bad"}>
          {status.deviceConnected ? "● connected" : "○ not connected"}
        </span>
        {status.deviceApp && <div className="text-xs font-normal text-muted">{status.deviceApp}</div>}
      </Stat>
      <Stat label="Spent today">
        {dropsToXrp(status.spentTodayDrops)} XRP
        {policy && <div className="text-xs font-normal text-muted">of {dropsToXrp(policy.dailyBudgetDrops)} XRP budget</div>}
      </Stat>
      <Stat label="Pending">
        <span className={status.pending > 0 ? "text-amber" : ""}>{status.pending}</span>
      </Stat>
    </section>
  );
}
