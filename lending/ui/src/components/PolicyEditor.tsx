import { useEffect, useRef, useState } from "react";
import { DeskError, putPolicy } from "../api";
import { xrpNum } from "../format";
import type { Policy } from "../types";

type Field = { key: keyof Policy; label: string; drops?: boolean; unit: string };

const FIELDS: Field[] = [
  { key: "maxAutoPrincipalDrops", label: "Approve on its own up to", drops: true, unit: "XRP" },
  { key: "minScoreAuto", label: "Score needed to approve on its own", unit: "of 100" },
  { key: "minScore", label: "Lowest score the desk lends to", unit: "of 100" },
  { key: "maxPrincipalDrops", label: "Largest loan", drops: true, unit: "XRP" },
  { key: "maxUtilizationPct", label: "Most of the vault out on loan", unit: "%" },
  { key: "minCoverRatioPct", label: "Lowest broker cover", unit: "% of debt" },
  { key: "holdTimeoutSeconds", label: "Held requests expire after", unit: "seconds" },
  { key: "interestRateBps", label: "Interest rate", unit: "basis points a year" },
  { key: "termSecondsMin", label: "Shortest term", unit: "seconds" },
  { key: "termSecondsMax", label: "Longest term", unit: "seconds" },
];

const toDrops = (x: string) => {
  const [w, f = ""] = x.trim().split(".");
  return String(BigInt(w || "0") * 1_000_000n + BigInt((f + "000000").slice(0, 6)));
};

export function PolicyEditor({ policy, onClose, onSaved }: { policy: Policy; onClose: () => void; onSaved: () => void }) {
  const [vals, setVals] = useState<Record<string, string>>(() =>
    Object.fromEntries(FIELDS.map((f) => [f.key, f.drops ? xrpNum(String(policy[f.key])) : String(policy[f.key])])),
  );
  const [err, setErr] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const first = useRef<HTMLInputElement>(null);
  useEffect(() => first.current?.focus(), []);

  async function save() {
    setErr(null);
    try {
      const next = { ...policy };
      for (const f of FIELDS) {
        const v = vals[f.key].trim();
        if (!/^\d+(\.\d+)?$/.test(v) || (!f.drops && v.includes("."))) throw new Error(`${f.label}: enter a whole number${f.drops ? " or XRP amount" : ""}.`);
        (next as Record<string, unknown>)[f.key] = f.drops ? toDrops(v) : Number(v);
      }
      setSaving(true);
      await putPolicy(next);
      onSaved();
      onClose();
    } catch (e) {
      setErr(e instanceof DeskError ? `The desk refused it (${e.status}): ${e.message}` : String((e as Error).message ?? e));
    } finally {
      setSaving(false);
    }
  }

  return (
    <section
      className="policy"
      aria-label="Policy editor"
      onKeyDown={(e) => {
        if (e.key === "Escape") onClose();
      }}
    >
      <h3>Policy</h3>
      <div className="muted" style={{ fontSize: 14 }}>
        The rules the desk applies to every request. Saved to the desk; the next request uses them.
      </div>
      <div className="grid">
        {FIELDS.map((f, i) => (
          <label key={f.key}>
            <span>
              {f.label} <span className="dim">({f.unit})</span>
            </span>
            <input
              ref={i === 0 ? first : undefined}
              inputMode="decimal"
              value={vals[f.key]}
              onChange={(e) => setVals((v) => ({ ...v, [f.key]: e.target.value }))}
              onKeyDown={(e) => {
                if (e.key === "Enter") void save();
              }}
            />
          </label>
        ))}
      </div>
      {err && (
        <div className="bad-t" role="alert" style={{ fontSize: 14, marginBottom: 12 }}>
          {err}
        </div>
      )}
      <div className="acts">
        <button type="button" className="btn-ok" disabled={saving} onClick={() => void save()}>
          {saving ? "Saving…" : "Save policy"}
        </button>
        <button type="button" className="btn-ghost" onClick={onClose}>
          Cancel
        </button>
      </div>
    </section>
  );
}
