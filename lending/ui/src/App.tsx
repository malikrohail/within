import { useCallback, useEffect, useRef, useState } from "react";
import { DESK_HOST, getLoans, getPolicy, getRequests, getVault } from "./api";
import { Activity } from "./components/Activity";
import { CoverTopUp } from "./components/CoverTopUp";
import { ApprovalCard, type Progress } from "./components/ApprovalCard";
import { Dot, Icon } from "./components/bits";
import { Loans } from "./components/Loans";
import { PolicyEditor } from "./components/PolicyEditor";
import { clock, groupInt, pct1, xrpFixed, xrpNum } from "./format";
import type { Loan, LoanRequest, Policy, Vault, VaultPhase } from "./types";

const POLL_MS = 2000;

function useNow(): number {
  const [now, setNow] = useState(() => Date.now() / 1000);
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now() / 1000), 1000);
    return () => clearInterval(t);
  }, []);
  return now;
}

// ---------- theme (per viewer; ?theme=light|dark wins, for screenshots) ----------
type Theme = "light" | "dark" | null;
const THEME_KEY = "lending.theme";
function initialTheme(): Theme {
  try {
    const q = new URLSearchParams(location.search).get("theme");
    if (q === "light" || q === "dark") return q;
    const s = localStorage.getItem(THEME_KEY);
    return s === "light" || s === "dark" ? s : null;
  } catch {
    return null;
  }
}
function useTheme(): [boolean, () => void] {
  const [theme, setTheme] = useState<Theme>(initialTheme);
  const sysDark = () => !window.matchMedia?.("(prefers-color-scheme: light)").matches;
  useEffect(() => {
    if (theme) document.documentElement.dataset.theme = theme;
    else delete document.documentElement.dataset.theme;
  }, [theme]);
  const dark = theme ? theme === "dark" : sysDark();
  const toggle = () => {
    const next = dark ? "light" : "dark";
    setTheme(next);
    try {
      localStorage.setItem(THEME_KEY, next);
    } catch {
      /* storage blocked */
    }
  };
  return [dark, toggle];
}

function phaseOf(v: Vault, now: number): VaultPhase {
  if (v.phase) return v.phase;
  if (now < v.subscriptionDate) return "subscription";
  if (v.redemptionDate && now >= v.redemptionDate) return "redemption";
  return "lending";
}

// ---------- header ----------
function Header({
  vault,
  policy,
  error,
  onPolicy,
  dark,
  toggleTheme,
}: {
  vault: Vault | null;
  policy: Policy | null;
  error: string | null;
  onPolicy: () => void;
  dark: boolean;
  toggleTheme: () => void;
}) {
  return (
    <header>
      <div className="brand">
        Lending Desk
        <span className="chip">
          <Dot />
          Devnet
        </span>
      </div>
      <div className="right">
        {error && (
          <span className="chip bad" title={error}>
            <Dot tone="bad" />
            Desk unreachable
          </span>
        )}
        {vault && (
          <span className="num">
            Ledger {groupInt(vault.ledgerIndex)}
          </span>
        )}
        {policy && (
          <button type="button" className="chip btn" title="Open the policy editor" onClick={onPolicy}>
            Auto-approves up to {xrpNum(policy.maxAutoPrincipalDrops)} XRP · edit
          </button>
        )}
        <button type="button" className="icon-btn" aria-label={dark ? "Switch to light theme" : "Switch to dark theme"} onClick={toggleTheme}>
          {dark ? Icon.moon() : Icon.sun()}
        </button>
      </div>
    </header>
  );
}

// ---------- phase line + vault hero ----------
function VaultHero({
  vault,
  policy,
  loans,
  now,
  fetchedAt,
  onChange,
}: {
  vault: Vault;
  policy: Policy | null;
  loans: Loan[];
  now: number;
  fetchedAt: number;
  onChange: () => void;
}) {
  const phase = phaseOf(vault, now);
  const total = Number(vault.assetsTotalDrops);
  const availPct = total > 0 ? (100 * Number(vault.assetsAvailableDrops)) / total : 0;
  const active = loans.filter((l) => l.status === "active" || l.status === "impaired").length;
  const maxU = policy?.maxUtilizationPct ?? vault.policy?.maxUtilizationPct;
  const minC = policy?.minCoverRatioPct ?? vault.policy?.minCoverRatioPct;
  const toLending = (vault.secondsToLending ?? vault.subscriptionDate - fetchedAt) - (now - fetchedAt);

  return (
    <section className="vault" aria-label="Vault">
      {phase === "subscription" ? (
        <div className="phase warn">
          <Dot tone="warn" />
          Raising funds. Lending opens in <span className="num">{clock(toLending)}</span>
        </div>
      ) : phase === "lending" ? (
        <div className="phase">
          <Dot />
          Lending is open
          {vault.redemptionDate > now && (
            <span className="muted" style={{ fontWeight: 400 }}>
              {" "}
              · redemption in <span className="num">{clock(vault.redemptionDate - now)}</span>
            </span>
          )}
        </div>
      ) : (
        <div className="phase dimmed">
          <Dot tone="dim" />
          Redemption. No new loans
        </div>
      )}
      <h2>Vault assets</h2>
      <div className="big num">
        {xrpFixed(vault.assetsTotalDrops)}
        <small>XRP</small>
      </div>
      <div className="util">
        <span>
          <b>{pct1(vault.utilizationPct)}%</b> <span className="muted">lent out</span>
        </span>
        {maxU != null && <span className="muted">Limit {maxU}%</span>}
      </div>
      <div className="bar" role="img" aria-label={`${pct1(vault.utilizationPct)}% lent out${maxU != null ? `, limit ${maxU}%` : ""}`}>
        <i style={{ width: `${Math.min(100, vault.utilizationPct)}%` }} />
        {maxU != null && <b style={{ left: `${maxU}%` }} />}
      </div>
      <div className="tiles">
        <div className="tile">
          <div className="l">Available</div>
          <div className="v num">
            {xrpFixed(vault.assetsAvailableDrops)}
            <small>XRP</small>
          </div>
          <div className="s">{pct1(availPct)}% ready to lend</div>
        </div>
        <div className="tile">
          <div className="l">Out on loan</div>
          <div className="v num">
            {xrpFixed(vault.loansOutstandingDrops)}
            <small>XRP</small>
          </div>
          <div className="s">
            {active} active loan{active === 1 ? "" : "s"}
          </div>
        </div>
        <div className="tile">
          <div className="l">First-loss cover</div>
          <div className="v num">
            {xrpFixed(vault.coverDrops)}
            <small>XRP</small>
          </div>
          <div className={`s ${minC != null && vault.coverRatioPct < minC ? "bad-t" : ""}`}>
            {Number(vault.debtTotalDrops) > 0 ? `${pct1(vault.coverRatioPct)}% of debt` : "No debt yet"}
            {minC != null ? `, minimum ${minC}%` : ""}
          </div>
          <CoverTopUp onDone={onChange} />
        </div>
      </div>
    </section>
  );
}

// ---------- approvals ----------
function Approvals({
  requests,
  policy,
  vault,
  loans,
  now,
  onChange,
}: {
  requests: LoanRequest[];
  policy: Policy | null;
  vault: Vault | null;
  loans: Loan[];
  now: number;
  onChange: () => void;
}) {
  // A card the reviewer acted on stays (with its progress) until dismissed, even after it leaves "held".
  const [progress, setProgress] = useState<Record<string, Progress | undefined>>({});
  const [kept, setKept] = useState<Record<string, LoanRequest>>({});
  const held = requests.filter((r) => r.status === "held");
  const heldIds = new Set(held.map((r) => r.id));
  const cards = [...held, ...Object.values(kept).filter((r) => !heldIds.has(r.id))].sort((a, b) => b.ts - a.ts);
  const paymentInterval = loans[0]?.paymentInterval ?? null;

  return (
    <section>
      <h3>
        Needs your approval <span className="count">{held.length}</span>
      </h3>
      {cards.length === 0 ? (
        <div className="empty">Nothing is waiting for you. Requests over the auto-approve limit, or with a borderline score, land here.</div>
      ) : (
        <div className="stack">
          {cards.map((r) => (
            <ApprovalCard
              key={r.id}
              r={r}
              policy={policy}
              vault={vault}
              now={now}
              paymentInterval={paymentInterval}
              progress={progress[r.id]}
              setProgress={(p) => {
                setProgress((m) => ({ ...m, [r.id]: p }));
                if (p) setKept((k) => ({ ...k, [r.id]: k[r.id] ?? r }));
              }}
              onChange={onChange}
              onDismiss={() => {
                setKept(({ [r.id]: _drop, ...rest }) => rest);
                setProgress(({ [r.id]: _p, ...rest }) => rest);
              }}
            />
          ))}
        </div>
      )}
    </section>
  );
}

export default function App() {
  const now = useNow();
  const [dark, toggleTheme] = useTheme();
  const [vault, setVault] = useState<Vault | null>(null);
  const [policy, setPolicy] = useState<Policy | null>(null);
  const [fetchedAt, setFetchedAt] = useState(() => Date.now() / 1000);
  const [requests, setRequests] = useState<LoanRequest[]>([]);
  const [loans, setLoans] = useState<Loan[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);

  const inFlight = useRef(false);
  const refresh = useCallback(async () => {
    if (inFlight.current) return; // vault and loans read devnet (~1 s each); never stack polls
    inFlight.current = true;
    // Each answer paints as soon as it lands: requests and policy are instant, vault and loans are not.
    const calls = [
      getRequests().then(setRequests),
      getPolicy().then(setPolicy),
      getVault().then((v) => {
        setVault(v);
        setFetchedAt(Date.now() / 1000);
      }),
      getLoans().then((l) => setLoans(l.loans)),
    ];
    const res = await Promise.allSettled(calls);
    inFlight.current = false;
    const failed = res.find((x) => x.status === "rejected") as PromiseRejectedResult | undefined;
    setError(failed ? String(failed.reason?.message ?? failed.reason) : null);
  }, []);

  useEffect(() => {
    void refresh();
    const t = setInterval(refresh, POLL_MS);
    return () => clearInterval(t);
  }, [refresh]);

  return (
    <div className="wrap">
      <Header vault={vault} policy={policy} error={error} onPolicy={() => setEditing((e) => !e)} dark={dark} toggleTheme={toggleTheme} />
      {editing && policy && <PolicyEditor policy={policy} onClose={() => setEditing(false)} onSaved={refresh} />}
      {vault ? (
        <VaultHero vault={vault} policy={policy} loans={loans} now={now} fetchedAt={fetchedAt} onChange={refresh} />
      ) : (
        <div className="waiting">{error ? `Waiting for the desk at ${DESK_HOST}…` : "Loading the vault…"}</div>
      )}
      <Approvals requests={requests} policy={policy} vault={vault} loans={loans} now={now} onChange={refresh} />
      <Activity requests={requests} loans={loans} policy={policy} vault={vault} now={now} />
      <Loans loans={loans} requests={requests} broker={vault?.accounts?.broker} now={now} />
      <footer>
        <span>Live data from the desk at {DESK_HOST} · XRP Ledger devnet</span>
        <span>Refreshes every {POLL_MS / 1000} s</span>
      </footer>
    </div>
  );
}
