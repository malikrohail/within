import { useEffect, useRef, useState } from "react";
import {
  ApiError,
  getDelegation,
  getMerchants,
  getPolicy,
  getRequests,
  getStatus,
  WALLET_URL,
  type Delegation,
  type Merchant,
  type Policy,
  type WalletRequest,
  type WalletStatus,
} from "./api";
import { Feed } from "./components/Feed";
import { Merchants } from "./components/Merchants";
import { Pending } from "./components/Pending";
import { Permissions } from "./components/Permissions";
import { PolicyEditor } from "./components/PolicyEditor";
import { StatusBar } from "./components/StatusBar";
import { Tower } from "./components/Tower";

const POLL_MS = 1000;
const POLICY_POLL_MS = 5000;
const MERCHANTS_POLL_MS = 5000;
const DELEGATE_POLL_MS = 5000;
const LEND_URL = "http://localhost:5175";

const TABS = ["Treasury", "Pay", "Vet", "Permissions"] as const;
type Tab = (typeof TABS)[number];

export default function App() {
  const [status, setStatus] = useState<WalletStatus | null>(null);
  const [requests, setRequests] = useState<WalletRequest[]>([]);
  const [policy, setPolicy] = useState<Policy | null>(null);
  const [merchants, setMerchants] = useState<Merchant[] | "unavailable" | { error: string } | null>(null);
  const [delegation, setDelegationState] = useState<Delegation | "unavailable" | { error: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [now, setNow] = useState(Date.now());
  const [tab, setTab] = useState<Tab>("Treasury");
  const inFlight = useRef(false);

  const refresh = async () => {
    if (inFlight.current) return;
    inFlight.current = true;
    try {
      const [s, r] = await Promise.all([getStatus(), getRequests()]);
      setStatus(s);
      setRequests(r);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      inFlight.current = false;
      setNow(Date.now());
    }
  };

  // Replace the policy object only when the server's copy changed, so the editor form is not reset on every poll.
  const refreshPolicy = () =>
    getPolicy().then(
      (p) => setPolicy((prev) => (JSON.stringify(prev) === JSON.stringify(p) ? prev : p)),
      () => {},
    );

  // Kept out of refresh() so a wallet without /v1/merchants (404) shows a note in the panel, not the unreachable banner.
  const refreshMerchants = () =>
    getMerchants().then(setMerchants, (e) => {
      if (e instanceof ApiError && e.status === 404) setMerchants("unavailable");
      // A failed first load shows the error; later failures keep the last good list.
      else setMerchants((prev) => (!Array.isArray(prev) ? { error: e instanceof Error ? e.message : String(e) } : prev));
    });

  // Same shape as refreshMerchants: 404 = wallet build without /v1/delegate; a 503 device_unavailable shows as the error.
  const refreshDelegation = () =>
    getDelegation().then(setDelegationState, (e) => {
      if (e instanceof ApiError && e.status === 404) setDelegationState("unavailable");
      else
        setDelegationState((prev) =>
          prev === null || prev === "unavailable" || "error" in prev ? { error: e instanceof Error ? e.message : String(e) } : prev,
        );
    });

  useEffect(() => {
    refresh();
    refreshPolicy();
    refreshMerchants();
    refreshDelegation();
    const timer = setInterval(refresh, POLL_MS);
    const policyTimer = setInterval(refreshPolicy, POLICY_POLL_MS);
    const merchantsTimer = setInterval(refreshMerchants, MERCHANTS_POLL_MS);
    const delegateTimer = setInterval(refreshDelegation, DELEGATE_POLL_MS);
    return () => {
      clearInterval(timer);
      clearInterval(policyTimer);
      clearInterval(merchantsTimer);
      clearInterval(delegateTimer);
    };
  }, []);

  return (
    <div className="mx-auto max-w-7xl space-y-6 p-4 md:p-8">
      <header className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">
            Policy <span className="text-accent">Wallet</span>
          </h1>
          <p className="text-sm text-muted">Agent payments on XRPL testnet: auto under the cap, Ledger above it, refused off-policy.</p>
        </div>
        <div className="text-right font-mono text-xs text-muted">
          <div>
            hot <span className="text-fg">{status?.hotAccount ?? "—"}</span>
          </div>
          <div>
            device <span className="text-fg">{status?.deviceAccount ?? "—"}</span>
          </div>
          <div>{WALLET_URL}</div>
        </div>
      </header>
      {error && (
        <div className="rounded-lg border border-bad/50 bg-bad/10 px-4 py-2 text-sm text-bad">
          Wallet unreachable at {WALLET_URL}: {error}
        </div>
      )}
      <StatusBar status={status} policy={policy} />
      <nav className="flex flex-wrap gap-1 border-b border-line">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`-mb-px border-b-2 px-4 py-2 text-sm font-semibold ${tab === t ? "border-accent text-fg" : "border-transparent text-muted hover:text-fg"}`}
          >
            {t}
          </button>
        ))}
        <a href={LEND_URL} target="_blank" rel="noreferrer" className="px-4 py-2 text-sm font-semibold text-muted hover:text-fg">
          Lend ↗
        </a>
      </nav>
      {/* Held payments wait for a human on every tab; the empty panel only shows on Pay. */}
      {(tab === "Pay" || requests.some((r) => r.status === "held")) && <Pending requests={requests} policy={policy} now={now} onChange={refresh} />}
      {tab === "Treasury" && <Tower requests={requests} status={status} />}
      {tab === "Pay" && (
        <>
          <Feed requests={requests} now={now} />
          <PolicyEditor policy={policy} onSaved={setPolicy} />
        </>
      )}
      {tab === "Vet" && <Merchants merchants={merchants} policy={policy} status={status} onChange={refreshMerchants} />}
      {tab === "Permissions" && <Permissions delegation={delegation} status={status} onChange={refreshDelegation} />}
    </div>
  );
}
