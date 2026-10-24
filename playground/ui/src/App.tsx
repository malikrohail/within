import { useCallback, useEffect, useRef, useState } from "react";
import { api, EXPLORER, short, xrp, type Facts, type Loan, type Rule, type Session } from "./api";

// ---- small pieces -------------------------------------------------------------------------------------------
const SESSION_KEY = "playground.session";
const ACH_KEY = "playground.achievements";
const THEME_KEY = "playground.theme";
const ACHIEVEMENTS = [
  ["income", "First income"],
  ["vetted", "Vetted"],
  ["auto", "Borrowed without a human"],
  ["repaid", "Repaid in my sleep"],
  ["default", "Defaulted and the vault survived"],
] as const;
type AchKey = (typeof ACHIEVEMENTS)[number][0];
type Achievements = Partial<Record<AchKey, string>>;

function load<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}
function save(key: string, value: unknown) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* private window or blocked storage: the page still works */
  }
}

function Tx({ hash, label }: { hash: string; label?: string }) {
  return (
    <span className="hash">
      {label ? `${label} ` : ""}
      <a href={`${EXPLORER}/transactions/${hash}`} target="_blank" rel="noreferrer">
        {hash.slice(0, 12)}… ↗
      </a>
    </span>
  );
}

function useNow() {
  const [now, setNow] = useState(() => Math.floor(Date.now() / 1000));
  useEffect(() => {
    const t = setInterval(() => setNow(Math.floor(Date.now() / 1000)), 1000);
    return () => clearInterval(t);
  }, []);
  return now;
}

function Countdown({ until, label }: { until: number; label: string }) {
  const now = useNow();
  const left = Math.max(0, until - now);
  const mm = String(Math.floor(left / 60)).padStart(2, "0");
  const ss = String(left % 60).padStart(2, "0");
  return (
    <span className="count">
      {label} {mm}:{ss}
    </span>
  );
}

function Ring({ score, facts }: { score: number; facts: Facts | null }) {
  const r = 86;
  const c = 2 * Math.PI * r;
  const auto = facts?.minScoreAuto ?? 70;
  const min = facts?.minScore ?? 40;
  const tone = score >= auto ? "ok" : score >= min ? "warn" : "";
  const caption = score >= auto ? "the desk would co-sign on its own" : score >= min ? "a person would have to say yes" : "nobody trusts you yet";
  const mark = (v: number) => {
    const a = (v / 100) * 2 * Math.PI - Math.PI / 2;
    return { x1: 100 + (r - 9) * Math.cos(a), y1: 100 + (r - 9) * Math.sin(a), x2: 100 + (r + 9) * Math.cos(a), y2: 100 + (r + 9) * Math.sin(a) };
  };
  return (
    <div className="ring" role="img" aria-label={`score ${score} of 100`}>
      <svg viewBox="0 0 200 200" width="200" height="200">
        <circle className="track" cx="100" cy="100" r={r} />
        <circle className={`arc ${tone}`} cx="100" cy="100" r={r} strokeDasharray={c} strokeDashoffset={c * (1 - score / 100)} />
        <line className="mark" {...mark(min)} />
        <line className="mark" {...mark(auto)} />
      </svg>
      <div className="center">
        <div className="big num">{score}</div>
        <div className="muted" style={{ fontSize: 12 }}>
          {caption}
        </div>
      </div>
    </div>
  );
}

const RULE_WORDS: Record<string, string> = {
  activeDays: "days with income (10 / 20 for points)",
  inboundVolumeDrops: "income volume (20 / 50 XRP)",
  distinctPayers: "distinct payers (2 / 4)",
  topPayerSharePct: "biggest payer's share (≤40 % / ≤70 %)",
  activeLoans: "no open loan",
  pastDefaults: "no past default",
  hasAcceptedCredential: "broker credential",
};
function Why({ rules }: { rules: Rule[] }) {
  const show = (r: Rule) =>
    r.rule === "inboundVolumeDrops" ? xrp(String(r.value)) : r.rule === "topPayerSharePct" ? `${r.value} %` : typeof r.value === "boolean" ? (r.value ? "yes" : "no") : String(r.value);
  return (
    <div className="why">
      {rules.map((r) => (
        <div className="row" key={r.rule}>
          <span className="muted">{RULE_WORDS[r.rule] ?? r.rule}</span>
          <span>
            <span className="mono">{show(r)}</span> <span className={`pts ${r.points ? "on" : "off"}`}>+{r.points}</span>
          </span>
        </div>
      ))}
    </div>
  );
}

function Level({ n, title, unlocked, children }: { n: number; title: string; unlocked: boolean; children: React.ReactNode }) {
  return (
    <section className={`level ${unlocked ? "" : "locked"}`} aria-disabled={!unlocked}>
      <div className="level-head">
        <span className="level-n">LEVEL {n}</span>
        <h2 className="display">{title}</h2>
        {!unlocked && <span className="lock">🔒 finish the level above</span>}
      </div>
      {children}
    </section>
  );
}

// ---- page ---------------------------------------------------------------------------------------------------
export default function App() {
  const [facts, setFacts] = useState<Facts | null>(null);
  const [s, setS] = useState<Session | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [ach, setAch] = useState<Achievements>(() => load(ACH_KEY, {}));
  const [theme, setTheme] = useState<string>(() => load(THEME_KEY, "auto"));
  const [ask, setAsk] = useState(2);
  const [brokerAway, setBrokerAway] = useState(false);
  const [skipUntil, setSkipUntil] = useState<number | null>(null);
  const [lastIncome, setLastIncome] = useState<{ hash: string; sweep?: string } | null>(null);
  const skipFired = useRef(false);

  useEffect(() => {
    document.documentElement.dataset.theme = theme === "auto" ? "" : theme;
    save(THEME_KEY, theme);
  }, [theme]);

  useEffect(() => {
    api.facts().then(setFacts).catch((e: Error) => setErr(`backend on :7510 not answering (${e.message}); run playground/bin/up.sh`));
    const id = load<string | null>(SESSION_KEY, null);
    if (id) api.get(id).then(setS).catch(() => save(SESSION_KEY, null));
  }, []);

  const unlock = useCallback((k: AchKey, hash: string) => {
    setAch((a) => {
      if (a[k]) return a;
      const next = { ...a, [k]: hash };
      save(ACH_KEY, next);
      return next;
    });
  }, []);

  // Poll while the desk is deciding or a person is being asked.
  const loan = s?.loan ?? null;
  useEffect(() => {
    if (!s || !loan || !["deciding", "held"].includes(loan.status)) return;
    const t = setInterval(() => api.get(s.id).then(setS).catch(() => {}), 3000);
    return () => clearInterval(t);
  }, [s, loan]);
  useEffect(() => {
    if (loan?.status === "auto" && loan.txHash) unlock("auto", loan.txHash);
  }, [loan, unlock]);

  const run = async (label: string, fn: () => Promise<void>) => {
    setBusy(label);
    setErr(null);
    try {
      await fn();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  const born = () =>
    run("born", async () => {
      const next = await api.create();
      save(SESSION_KEY, next.id);
      setS(next);
      setLastIncome(null);
      setSkipUntil(null);
      skipFired.current = false;
    });
  const reset = () =>
    run("reset", async () => {
      if (s) await api.reset(s.id).catch(() => {});
      save(SESSION_KEY, null);
      setS(null);
      setLastIncome(null);
      setSkipUntil(null);
    });
  const income = () =>
    run("income", async () => {
      if (!s) return;
      const r = await api.income(s.id);
      setS(r.session);
      unlock("income", r.payment.hash);
      const sweep = r.sweeps[0];
      setLastIncome({ hash: r.payment.hash, sweep: sweep?.loanPayHash });
      if (sweep && sweep.engineResult === "tesSUCCESS") unlock("repaid", sweep.loanPayHash);
    });
  const credential = () =>
    run("credential", async () => {
      if (!s) return;
      const r = await api.credential(s.id);
      setS(r.session);
      if (r.away) setBrokerAway(true);
      else if (r.credential) unlock("vetted", r.credential.acceptHash);
    });
  const borrow = () =>
    run("borrow", async () => {
      if (!s) return;
      setS(await api.borrow(s.id, ask));
    });
  const skip = () => {
    if (!loan?.activeAt || !facts) return;
    skipFired.current = false;
    setSkipUntil(loan.activeAt + facts.paymentInterval + facts.gracePeriod + 8);
  };
  const now = useNow();
  useEffect(() => {
    if (skipUntil == null || now < skipUntil || skipFired.current || !s) return;
    skipFired.current = true;
    run("default", async () => {
      const r = await api.default(s.id);
      setS(r.session);
      if (r.default?.engineResult === "tesSUCCESS") unlock("default", r.default.hash);
    });
  }, [now, skipUntil, s]);

  const level = s?.level ?? 1;
  const active = loan?.status === "auto" || loan?.status === "approved";
  const ceiling = s?.credential ? facts?.ceiling.withCredential : facts?.ceiling.noCredential;

  return (
    <div className="wrap">
      <header className="top">
        <div>
          <div className="display" style={{ fontSize: 30, lineHeight: 1.1 }}>
            Be the agent
          </div>
          <div className="muted" style={{ fontSize: 13 }}>
            Five real devnet transactions, one score ring. The playground holds your demo key for the session.
          </div>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="chip-btn" onClick={() => setTheme(theme === "dark" ? "light" : theme === "light" ? "auto" : "dark")} aria-label="theme">
            {theme === "dark" ? "dark" : theme === "light" ? "light" : "auto"}
          </button>
          {s && (
            <button className="chip-btn" onClick={reset} disabled={busy != null}>
              start over
            </button>
          )}
        </div>
      </header>

      {err && <div className="err">{err}</div>}

      <div className="hero">
        <Ring score={s?.score ?? 0} facts={facts} />
        <div style={{ display: "grid", gap: 8, width: "100%" }}>
          {s ? (
            <>
              <div>
                <span className="mono">{short(s.address)}</span>{" "}
                <a href={`${EXPLORER}/accounts/${s.address}`} target="_blank" rel="noreferrer">
                  account ↗
                </a>
                <span className="muted"> · {xrp(s.balanceDrops)}</span>
              </div>
              <Why rules={s.breakdown.ledger.rules} />
              <div className="dim" style={{ fontSize: 12 }}>
                ledger {s.breakdown.ledger.score}/100 × {s.breakdown.weights.ledger} % + declared {s.breakdown.declared.score}/100 × {s.breakdown.weights.declared} % = {s.score}.
                {facts && ` Auto at ${facts.minScoreAuto}, refused under ${facts.minScore}. Policy ${facts.policyHash}.`}
              </div>
            </>
          ) : (
            <p className="muted">No agent yet. Every point on this ring will come from a payment you watch land on the XRP Ledger devnet.</p>
          )}
        </div>
      </div>

      <Level n={1} title="Get born" unlocked>
        <p className="muted">Claim a funded devnet account from the playground pool. The ledger knows it exists and nothing else.</p>
        <div className="actions">
          <button className="btn" onClick={born} disabled={busy != null || s != null}>
            {busy === "born" ? "claiming…" : s ? "born" : "Create my agent"}
          </button>
          {s && (
            <span className="result ok">
              You are <span className="mono">{s.address}</span>. Score {s.score}: {s.score < (facts?.minScore ?? 40) ? "nobody trusts you yet." : "someone might."}
            </span>
          )}
        </div>
      </Level>

      <Level n={2} title="Earn" unlocked={level >= 2}>
        <p className="muted">
          A customer pays you {facts ? xrp(facts.incomeDrops) : "5 XRP"} with an invoice memo. Three customers take turns, so distinct payers rise. The ring moves only after the ledger validates.
        </p>
        <div className="actions">
          <button className="btn" onClick={income} disabled={busy != null || level < 2 || active}>
            {busy === "income" ? "waiting for validation…" : "A customer pays me"}
          </button>
          {busy === "income" && <Countdown until={now + 5} label="ledger" />}
          {s && s.payments.length > 0 && (
            <span className="muted" style={{ fontSize: 13 }}>
              {s.payments.length} payment{s.payments.length > 1 ? "s" : ""} from {String(s.ledger.distinctPayers)} payer{Number(s.ledger.distinctPayers) > 1 ? "s" : ""}
            </span>
          )}
        </div>
        {s && s.payments.length > 0 && (
          <div className="result ok">
            {s.payments.slice(-3).reverse().map((p) => (
              <Tx key={p.hash} hash={p.hash} label={`${xrp(p.drops)} from ${short(p.payer)}`} />
            ))}
            <span className="muted">
              The ledger now knows {s.payments.length} invoice{s.payments.length > 1 ? "s" : ""} were paid to you today. A fresh account tops out at {ceiling ?? "…"} this way; the credential and time do the rest.
            </span>
          </div>
        )}
      </Level>

      <Level n={3} title="Get vetted" unlocked={level >= 3}>
        <p className="muted">
          Ask the broker for a <span className="mono">kyb-borrower</span> credential, then accept it with your own key. +15 ledger points and the lock on automatic loans opens. Skippable.
        </p>
        <div className="actions">
          <button className="btn" onClick={credential} disabled={busy != null || level < 3 || !!s?.credential || brokerAway}>
            {busy === "credential" ? "asking…" : s?.credential ? "vetted" : "Ask the broker for a credential"}
          </button>
          {brokerAway && <span className="result warn">The broker is away. You can skip this level; the desk will hold your loan for a person instead.</span>}
          {s?.credential && (
            <span className="result ok">
              {s.credential.createHash && <Tx hash={s.credential.createHash} label="broker issued" />}
              <Tx hash={s.credential.acceptHash} label="you accepted" />
              <span className="muted">🔓 automatic loans unlocked: the ledger now carries an accepted credential from {short(s.credential.issuer)}.</span>
            </span>
          )}
        </div>
      </Level>

      <Level n={4} title="Borrow" unlocked={level >= 4}>
        <p className="muted">
          Sign a LoanSet with your key and send it to the desk. The desk scores the ledger, never you. Over {facts?.minScoreAuto ?? 70} it co-signs alone; between {facts?.minScore ?? 40} and{" "}
          {facts?.minScoreAuto ?? 70} a person has to say yes within {facts?.holdTimeoutSeconds ?? 120} s; under {facts?.minScore ?? 40} it refuses. Asks are capped at 5 XRP.
        </p>
        <div className="slider">
          <input type="range" min={1} max={5} step={0.5} value={ask} onChange={(e) => setAsk(Number(e.target.value))} disabled={level < 4 || !!loan} aria-label="ask in XRP" />
          <span className="mono num">{ask} XRP</span>
        </div>
        <div className="actions">
          <button className="btn" onClick={borrow} disabled={busy != null || level < 4 || (!!loan && !["denied", "refused", "expired", "failed", "defaulted"].includes(loan.status))}>
            {busy === "borrow" ? "signing…" : loan && !["denied", "refused", "expired", "failed", "defaulted"].includes(loan.status) ? "asked" : "Ask for the loan"}
          </button>
          {loan && facts && <Decision loan={loan} facts={facts} />}
        </div>
      </Level>

      <Level n={5} title="Repay or default" unlocked={level >= 5}>
        <p className="muted">
          With a loan open, every customer payment is swept into the installment by a sweeper holding only your key. Or skip it, wait out the grace period, and watch the first-loss cover take the hit before the vault does.
        </p>
        <div className="actions">
          <button className="btn" onClick={income} disabled={busy != null || level < 5 || !active || skipUntil != null}>
            {busy === "income" ? "paying and sweeping…" : "A customer pays me"}
          </button>
          <button className="btn ghost" onClick={skip} disabled={busy != null || level < 5 || !active || skipUntil != null}>
            Skip my payment
          </button>
          {skipUntil != null && now < skipUntil && <Countdown until={skipUntil} label="grace" />}
          {skipUntil != null && now >= skipUntil && busy === "default" && <span className="count busy">asking the desk to default…</span>}
        </div>
        {lastIncome && level >= 5 && (
          <div className={`result ${lastIncome.sweep ? "ok" : "warn"}`}>
            <Tx hash={lastIncome.hash} label="income" />
            {lastIncome.sweep ? (
              <>
                <Tx hash={lastIncome.sweep} label="LoanPay" />
                <span className="muted">Nobody touched it: the sweeper saw the income and paid the installment.</span>
              </>
            ) : (
              <span className="muted">Income landed; no installment was due within one payment interval, or the sweeper kept its reserve.</span>
            )}
          </div>
        )}
        {s?.default && (
          <div className={`result ${s.default.engineResult === "tesSUCCESS" ? "bad" : "warn"}`}>
            <Tx hash={s.default.hash} label={`LoanManage default ${s.default.engineResult}`} />
            {s.default.engineResult === "tesSUCCESS" ? (
              <span className="muted">
                Cover first: {xrp(s.default.coverAbsorbedDrops)} came out of the broker's first-loss cover. Vault second: depositors absorbed {xrp(s.default.vaultLossDrops)} of the {xrp(s.default.defaultAmountDrops)} that was outstanding.
              </span>
            ) : (
              <span className="muted">The ledger did not accept the default yet (it needs the grace period to have passed in ledger time). Try again in a moment.</span>
            )}
          </div>
        )}
      </Level>

      <section>
        <div className="level-n" style={{ marginBottom: 8 }}>
          ACHIEVEMENTS
        </div>
        <div className="badges">
          {ACHIEVEMENTS.map(([k, label]) => (
            <span key={k} className={`badge ${ach[k] ? "on" : ""}`} title={ach[k] ?? "not yet"}>
              {ach[k] ? "★ " : "☆ "}
              {label}
              {ach[k] && (
                <>
                  {" "}
                  <a href={`${EXPLORER}/transactions/${ach[k]}`} target="_blank" rel="noreferrer">
                    ↗
                  </a>
                </>
              )}
            </span>
          ))}
        </div>
      </section>
    </div>
  );
}

function Decision({ loan, facts }: { loan: Loan; facts: Facts }) {
  const now = useNow();
  switch (loan.status) {
    case "deciding":
      return <span className="result busy">The desk is reading the ledger and asking for a second opinion…</span>;
    case "auto":
      return (
        <span className="result ok">
          The desk co-signed, no human. Score {loan.score}.
          {loan.txHash && <Tx hash={loan.txHash} label="LoanSet" />}
        </span>
      );
    case "held":
      return (
        <span className="result warn">
          A person has to say yes. Score {loan.score} ({loan.reason}). {loan.deskTs && <Countdown until={loan.deskTs + facts.holdTimeoutSeconds} label="hold" />}
          {loan.memo && <span className="muted">Second opinion: {loan.memo}</span>}
        </span>
      );
    case "approved":
      return (
        <span className="result ok">
          A person said yes ({loan.decidedBy}). {loan.txHash && <Tx hash={loan.txHash} label="LoanSet" />}
        </span>
      );
    case "refused":
      return (
        <span className="result bad">
          The desk refused: <span className="mono">{loan.reason}</span>. Score {loan.score}. Nothing was signed.
        </span>
      );
    case "expired":
      return <span className="result warn">Nobody answered within {facts.holdTimeoutSeconds} s, so the hold expired. Nothing was signed. Earn more, or get vetted, and ask again.</span>;
    case "denied":
      return <span className="result bad">A person said no ({loan.reason ?? "no reason given"}). Nothing was signed.</span>;
    case "defaulted":
      return <span className="result bad">Defaulted {now - (loan.activeAt ?? now)} s after it started.</span>;
    default:
      return (
        <span className="result bad">
          Failed: <span className="mono">{loan.reason}</span>
        </span>
      );
  }
}
