import { useEffect, useState } from "react";
import { putPolicy, type Policy } from "../api";
import { dropsToXrp, xrpToDrops } from "../format";

interface Form {
  perTxCapXrp: string;
  dailyBudgetXrp: string;
  allowedMerchants: string;
  allowedNetworks: string;
  allowedAssets: string;
  holdTimeoutSeconds: string;
}

const toForm = (p: Policy): Form => ({
  perTxCapXrp: dropsToXrp(p.perTxCapDrops),
  dailyBudgetXrp: dropsToXrp(p.dailyBudgetDrops),
  allowedMerchants: p.allowedMerchants.join("\n"),
  allowedNetworks: p.allowedNetworks.join(", "),
  allowedAssets: p.allowedAssets.join(", "),
  holdTimeoutSeconds: String(p.holdTimeoutSeconds),
});

const lines = (s: string) => s.split(/[\n,]/).map((x) => x.trim()).filter(Boolean);

function validate(f: Form): { policy?: Policy; errors: Partial<Record<keyof Form, string>> } {
  const errors: Partial<Record<keyof Form, string>> = {};
  const perTxCapDrops = xrpToDrops(f.perTxCapXrp);
  if (perTxCapDrops === null) errors.perTxCapXrp = "Must be a whole number of drops (XRP with at most 6 decimals)";
  const dailyBudgetDrops = xrpToDrops(f.dailyBudgetXrp);
  if (dailyBudgetDrops === null) errors.dailyBudgetXrp = "Must be a whole number of drops (XRP with at most 6 decimals)";
  const allowedMerchants = lines(f.allowedMerchants);
  const bad = allowedMerchants.filter((a) => !/^r[1-9A-HJ-NP-Za-km-z]{24,34}$/.test(a));
  if (bad.length) errors.allowedMerchants = `Not an XRPL address (must start with r): ${bad.join(", ")}`;
  if (!/^\d+$/.test(f.holdTimeoutSeconds.trim())) errors.holdTimeoutSeconds = "Whole seconds only";
  if (Object.keys(errors).length) return { errors };
  return {
    errors,
    policy: {
      perTxCapDrops: perTxCapDrops!,
      dailyBudgetDrops: dailyBudgetDrops!,
      allowedMerchants,
      allowedNetworks: lines(f.allowedNetworks),
      allowedAssets: lines(f.allowedAssets),
      holdTimeoutSeconds: Number(f.holdTimeoutSeconds.trim()),
    },
  };
}

const input = "w-full rounded-lg border border-line bg-ink px-3 py-2 font-mono text-sm focus:border-accent focus:outline-none";

function Field({ label, hint, error, children }: { label: string; hint?: string; error?: string; children: React.ReactNode }) {
  return (
    <label className="block space-y-1">
      <span className="text-xs uppercase tracking-wide text-muted">{label}</span>
      {children}
      {error ? <span className="block text-xs text-bad">{error}</span> : hint && <span className="block text-xs text-muted">{hint}</span>}
    </label>
  );
}

export function PolicyEditor({ policy, onSaved }: { policy: Policy | null; onSaved: (p: Policy) => void }) {
  const [form, setForm] = useState<Form | null>(policy && toForm(policy));
  const [saving, setSaving] = useState(false);
  const [result, setResult] = useState<{ ok: boolean; text: string } | null>(null);

  useEffect(() => {
    if (policy) setForm(toForm(policy));
  }, [policy]);

  if (!form) return <section className="panel text-muted">Loading policy…</section>;

  const { errors, policy: candidate } = validate(form);
  const set = (key: keyof Form) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm({ ...form, [key]: e.target.value });
  const drops = (xrp: string) => {
    const d = xrpToDrops(xrp);
    return d === null ? undefined : `${Number(d).toLocaleString("en-US")} drops`;
  };

  const save = async () => {
    if (!candidate) return;
    setSaving(true);
    setResult(null);
    try {
      // Spread the server copy first so fields the form does not edit (credentialIssuer, credentialType) survive the PUT.
      const saved = await putPolicy({ ...policy, ...candidate });
      onSaved(saved);
      setResult({ ok: true, text: `Saved. Wallet now enforces:\n${JSON.stringify(saved, null, 2)}` });
    } catch (e) {
      setResult({ ok: false, text: e instanceof Error ? e.message : String(e) });
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="panel">
      <h2 className="panel-title">Policy</h2>
      <div className="grid gap-5 md:grid-cols-2">
        <Field label="Per-transaction cap (XRP) — above this, hold for the device" hint={drops(form.perTxCapXrp)} error={errors.perTxCapXrp}>
          <input className={input} value={form.perTxCapXrp} onChange={set("perTxCapXrp")} inputMode="decimal" />
        </Field>
        <Field label="Daily budget (XRP) — above this, refuse" hint={drops(form.dailyBudgetXrp)} error={errors.dailyBudgetXrp}>
          <input className={input} value={form.dailyBudgetXrp} onChange={set("dailyBudgetXrp")} inputMode="decimal" />
        </Field>
        <Field
          label="Static override (bypasses on-ledger check)"
          hint="one address per line; normally empty, vet merchants on-ledger instead"
          error={errors.allowedMerchants}
        >
          <textarea className={`${input} h-24`} value={form.allowedMerchants} onChange={set("allowedMerchants")} spellCheck={false} />
        </Field>
        <div className="space-y-5">
          <Field label="Allowed networks" hint="comma separated, e.g. xrpl:1">
            <input className={input} value={form.allowedNetworks} onChange={set("allowedNetworks")} />
          </Field>
          <Field label="Allowed assets" hint="comma separated, e.g. XRP">
            <input className={input} value={form.allowedAssets} onChange={set("allowedAssets")} />
          </Field>
          <Field label="Hold timeout (seconds)" error={errors.holdTimeoutSeconds}>
            <input className={input} value={form.holdTimeoutSeconds} onChange={set("holdTimeoutSeconds")} inputMode="numeric" />
          </Field>
        </div>
        <Field label="Credential issuer (read-only)">
          <input className={`${input} text-muted`} value={policy?.credentialIssuer ?? "—"} readOnly />
        </Field>
        <Field label="Credential type (read-only)">
          <input className={`${input} text-muted`} value={policy?.credentialType ?? "—"} readOnly />
        </Field>
      </div>
      <div className="mt-5 flex items-center gap-4">
        <button
          className="rounded-lg bg-accent px-5 py-2 font-semibold text-ink hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-50"
          disabled={!candidate || saving}
          onClick={save}
        >
          {saving ? "Saving…" : "Save"}
        </button>
        {policy && (
          <button className="text-sm text-muted hover:text-fg" onClick={() => setForm(toForm(policy))}>
            Reset
          </button>
        )}
      </div>
      {result && (
        <pre className={`mt-4 overflow-x-auto rounded-lg p-3 text-xs ${result.ok ? "bg-ok/10 text-ok" : "bg-bad/10 text-bad"}`}>{result.text}</pre>
      )}
    </section>
  );
}
