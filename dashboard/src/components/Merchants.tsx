import { useEffect, useState } from "react";
import { getDomain, revokeMerchant, setDomain, vetMerchant, type Domain, type Merchant, type Policy, type WalletStatus } from "../api";
import { explorerAccount, explorerTx, shortAccount, shortHash } from "../format";
import { describe, walletCtx } from "../preview";
import { PreviewCard } from "./PreviewCard";

const pill = "inline-block rounded-full px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wide ring-1";

/** "x402-merchant" -> "783430322D6D65726368616E74", as the wallet's credentialTypeHex. */
const hex = (text: string) =>
  Array.from(new TextEncoder().encode(text), (b) => b.toString(16).padStart(2, "0"))
    .join("")
    .toUpperCase();

/** `merchants` is null before the first load, "unavailable" when the wallet has no /v1/merchants route (404), and { error } when the first load failed. */
export function Merchants({
  merchants,
  policy,
  status,
  onChange,
}: {
  merchants: Merchant[] | "unavailable" | { error: string } | null;
  policy: Policy | null;
  status: WalletStatus | null;
  onChange: () => void;
}) {
  const [address, setAddress] = useState("");
  const [vetting, setVetting] = useState(false);
  const [vetError, setVetError] = useState<string | null>(null);
  // Revoke asks for a second click on the same row instead of a browser dialog.
  const [confirming, setConfirming] = useState<string | null>(null);
  const [revoking, setRevoking] = useState<string | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});

  // The Permissioned Domain built from the vet credential: undefined while loading, null when none exists.
  const [domain, setDomainState] = useState<Domain | null | undefined>(undefined);
  const [domainBusy, setDomainBusy] = useState(false);
  const [domainError, setDomainError] = useState<string | null>(null);

  useEffect(() => setVetError(null), [address]);
  useEffect(() => {
    getDomain().then(
      (r) => setDomainState(r.domain),
      (e) => setDomainError(e instanceof Error ? e.message : String(e)),
    );
  }, []);

  const createDomain = async () => {
    setDomainBusy(true);
    setDomainError(null);
    try {
      setDomainState((await setDomain()).domain);
    } catch (e) {
      setDomainError(e instanceof Error ? e.message : String(e));
    } finally {
      setDomainBusy(false);
    }
  };

  const vet = async () => {
    setVetting(true);
    setVetError(null);
    try {
      await vetMerchant(address.trim());
      setAddress("");
      onChange();
    } catch (e) {
      setVetError(e instanceof Error ? e.message : String(e));
    } finally {
      setVetting(false);
    }
  };

  // The CredentialCreate that Vet sends, shown once an address is typed.
  const vetPreview =
    address.trim() && policy?.credentialIssuer && policy.credentialType
      ? describe(
          {
            TransactionType: "CredentialCreate",
            Account: policy.credentialIssuer,
            Subject: address.trim(),
            CredentialType: hex(policy.credentialType),
          },
          walletCtx(status),
        )
      : null;

  const revoke = async (addr: string) => {
    if (confirming !== addr) {
      setConfirming(addr);
      return;
    }
    setConfirming(null);
    setRevoking(addr);
    setErrors(({ [addr]: _, ...rest }) => rest);
    try {
      await revokeMerchant(addr);
      onChange();
    } catch (e) {
      setErrors((s) => ({ ...s, [addr]: e instanceof Error ? e.message : String(e) }));
    } finally {
      setRevoking(null);
    }
  };

  return (
    <section className="panel">
      <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="panel-title !mb-0">Vetted merchants</h2>
        <div className="text-xs text-muted">
          {domain ? (
            <>
              Domain{" "}
              <a className="font-mono text-accent hover:underline" href={explorerTx(domain.txHash)} target="_blank" rel="noreferrer" title={domain.domainId}>
                {shortHash(domain.domainId)}
              </a>{" "}
              · membership = <span className="font-mono text-fg">{domain.acceptedCredentials.map((c) => c.credentialType).join(", ")}</span> credential
            </>
          ) : domain === null ? (
            <button
              className="rounded-lg border border-accent px-3 py-1 font-semibold text-accent hover:bg-accent/10 disabled:opacity-50"
              disabled={domainBusy}
              onClick={createDomain}
            >
              {domainBusy ? "Creating domain…" : "Create Permissioned Domain"}
            </button>
          ) : null}
          {domainError && <span className="ml-2 text-bad">{domainError}</span>}
        </div>
      </div>
      <p className="-mt-2 mb-4 text-xs text-muted">
        The allowlist lives on the ledger: Credential objects from issuer{" "}
        {policy?.credentialIssuer ? (
          <a className="font-mono text-fg hover:text-accent" href={explorerAccount(policy.credentialIssuer)} target="_blank" rel="noreferrer">
            {shortAccount(policy.credentialIssuer)}
          </a>
        ) : (
          "—"
        )}{" "}
        of type <span className="font-mono text-fg">{policy?.credentialType ?? "—"}</span>, accepted by the merchant.
      </p>
      {merchants === "unavailable" ? (
        <p className="text-muted">Not available on this wallet build (no /v1/merchants).</p>
      ) : merchants === null ? (
        <p className="text-muted">Loading…</p>
      ) : !Array.isArray(merchants) ? (
        <p className="text-bad">Could not load merchants: {merchants.error}</p>
      ) : (
        <>
          {merchants.length === 0 ? (
            <p className="text-muted">No merchants vetted yet.</p>
          ) : (
            <ul className="divide-y divide-line">
              {merchants.map((m) => (
                <li key={m.address} className="flex flex-wrap items-center gap-4 py-2 text-sm">
                  <a
                    className="font-mono text-fg hover:text-accent"
                    href={explorerAccount(m.address)}
                    target="_blank"
                    rel="noreferrer"
                    title={m.address}
                  >
                    {shortAccount(m.address)}
                  </a>
                  <span className={`${pill} ${m.accepted ? "bg-ok/15 text-ok ring-ok/40" : "bg-amber/15 text-amber ring-amber/40"}`}>
                    {m.accepted ? "accepted" : "pending acceptance"}
                  </span>
                  {m.txHash && (
                    <a className="font-mono text-accent hover:underline" href={explorerTx(m.txHash)} target="_blank" rel="noreferrer" title={m.txHash}>
                      {shortHash(m.txHash)}
                    </a>
                  )}
                  <div className="ml-auto flex items-center gap-2">
                    {errors[m.address] && <span className="text-xs text-bad">{errors[m.address]}</span>}
                    {confirming === m.address && (
                      <button className="text-xs text-muted hover:text-fg" onClick={() => setConfirming(null)}>
                        Cancel
                      </button>
                    )}
                    <button
                      className="rounded-lg border border-bad px-3 py-1 text-xs font-semibold text-bad hover:bg-bad/10 disabled:cursor-not-allowed disabled:opacity-50"
                      disabled={revoking !== null}
                      onClick={() => revoke(m.address)}
                    >
                      {revoking === m.address ? "Revoking…" : confirming === m.address ? "Confirm revoke" : "Revoke"}
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <input
              className="min-w-0 flex-1 rounded-lg border border-line bg-ink px-3 py-2 font-mono text-sm focus:border-accent focus:outline-none"
              placeholder="r… merchant address"
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              spellCheck={false}
            />
            <button
              className="rounded-lg bg-accent px-5 py-2 font-semibold text-ink hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-50"
              disabled={vetting || !address.trim()}
              onClick={vet}
            >
              {vetting ? "Vetting…" : "Vet"}
            </button>
          </div>
          {vetPreview && (
            <div className="mt-3">
              <PreviewCard preview={vetPreview} compact />
            </div>
          )}
          {vetError && <p className="mt-2 text-sm text-bad">{vetError}</p>}
        </>
      )}
    </section>
  );
}
