// Field formatters, named in descriptors as "format". No runtime dependencies: tx_json is plain
// JSON, so drops, hex, ripple time and currency codes are string and number work.
import { LENDING_FORMATS } from "./formats-lending.js";
import { sha256Hex } from "./sha256.js";
import type { Ctx, Formatter, Line, Preview, Risk, Tx } from "./types.js";

export const RIPPLE_EPOCH_OFFSET = 946684800;
const X402_FACILITATOR_MEMO = "urn:x402:facilitator";

export const short = (s: string, head = 6, tail = 4) => (s.length > head + tail + 1 ? `${s.slice(0, head)}…${s.slice(-tail)}` : s);

export function account(v: unknown, ctx: Ctx): { value: string; full?: string } {
  const a = String(v);
  const name = ctx.names?.[a];
  return { value: name ? `${name} (${short(a)})` : short(a), full: a };
}

/** "5000000" → "5 XRP"; keeps up to 6 decimals, no float rounding. */
export function dropsToXrp(drops: string): string {
  if (!/^\d+$/.test(drops)) return `${drops} drops`;
  const d = drops.padStart(7, "0");
  const whole = d.slice(0, -6).replace(/^0+(?=\d)/, "");
  const frac = d.slice(-6).replace(/0+$/, "");
  return `${whole}${frac ? `.${frac}` : ""} XRP`;
}

/** 3-letter code as is; 40-hex code decoded to text when printable. */
export function currencyName(code: string): string {
  if (/^[0-9A-F]{40}$/i.test(code)) {
    const text = hexText(code.replace(/(00)+$/, ""));
    return text ?? short(code, 8, 4);
  }
  return code;
}

/** Hex → UTF-8 if every char is printable, else null. */
export function hexText(hex: string): string | null {
  if (!/^([0-9a-fA-F]{2})*$/.test(hex) || hex.length === 0) return null;
  const bytes = new Uint8Array(hex.match(/../g)!.map((b) => parseInt(b, 16)));
  let text: string;
  try {
    text = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  } catch {
    return null;
  }
  return /^[\P{C}\n\t]*$/u.test(text) ? text : null;
}

export function amount(v: unknown, ctx: Ctx): { value: string; full?: string } {
  if (typeof v === "string") return { value: dropsToXrp(v) };
  if (v && typeof v === "object") {
    const o = v as Record<string, unknown>;
    if (typeof o.mpt_issuance_id === "string") return { value: `${o.value} MPT ${short(o.mpt_issuance_id, 8, 4)}`, full: o.mpt_issuance_id };
    if (typeof o.currency === "string") {
      const issuer = typeof o.issuer === "string" ? account(o.issuer, ctx).value : "?";
      return { value: `${o.value} ${currencyName(o.currency)} (issuer ${issuer})`, full: typeof o.issuer === "string" ? o.issuer : undefined };
    }
  }
  return { value: JSON.stringify(v) };
}

/** Ripple-epoch seconds → ISO date plus "in 2 minutes" / "3 hours ago". */
export function rippleTime(v: unknown, ctx: Ctx): string {
  const ms = (Number(v) + RIPPLE_EPOCH_OFFSET) * 1000;
  const iso = new Date(ms).toISOString().replace(".000Z", "Z");
  return `${iso} (${relative(ms - (ctx.now ?? Date.now()))})`;
}

export function duration(seconds: number): string {
  const units: [number, string][] = [[86400, "day"], [3600, "hour"], [60, "minute"], [1, "second"]];
  for (const [n, name] of units) {
    if (seconds >= n && seconds % n === 0) {
      const k = seconds / n;
      return `${k} ${name}${k === 1 ? "" : "s"}`;
    }
  }
  return `${seconds} seconds`;
}

function relative(deltaMs: number): string {
  const s = Math.round(Math.abs(deltaMs) / 1000);
  const units: [number, string][] = [[86400, "day"], [3600, "hour"], [60, "minute"], [1, "second"]];
  const [n, name] = units.find(([n]) => s >= n) ?? [1, "second"];
  const k = Math.round(s / n);
  const text = `${k} ${name}${k === 1 ? "" : "s"}`;
  return deltaMs >= 0 ? `in ${text}` : `${text} ago`;
}

type Memo = { Memo?: { MemoType?: string; MemoData?: string; MemoFormat?: string } };

/** Each memo on its own line. x402: the facilitator memo and the invoice memo (sha256(text) == InvoiceID). */
const memos: Formatter = (v, tx) => {
  const list = Array.isArray(v) ? (v as Memo[]) : [];
  return list.map((m, i): Line => {
    const type = m.Memo?.MemoType ? hexText(m.Memo.MemoType) : null;
    const data = m.Memo?.MemoData ?? "";
    const text = hexText(data);
    if (type === X402_FACILITATOR_MEMO) return { label: "x402 facilitator", value: text ?? short(data, 10, 6), full: text ?? data };
    if (!type && text && typeof tx.InvoiceID === "string" && sha256Hex(text) === tx.InvoiceID.toUpperCase()) {
      return { label: "x402 invoice", value: `${text} (matches InvoiceID)`, full: text };
    }
    const label = `Memo ${list.length > 1 ? i + 1 : ""}`.trim() + (type ? ` (${type})` : "");
    return text ? { label, value: text } : { label, value: short(data, 10, 6), full: data, risk: "info" };
  });
};

/** Batch inner transactions: one summary line each, then that card's lines, prefixed "#n". */
const innerTransactions: Formatter = (v, _tx, ctx, describe) => {
  const list = Array.isArray(v) ? v : [];
  return list.flatMap((item, i): Line[] => {
    const inner = ((item as { RawTransaction?: Tx }).RawTransaction ?? item) as Tx;
    const p: Preview = describe(inner, ctx);
    const worst = p.lines.reduce<Risk | undefined>((w, l) => (l.risk === "danger" || (l.risk === "warn" && w !== "danger") ? l.risk : w), undefined);
    return [
      { label: `#${i + 1}`, value: p.summary, ...(worst ? { risk: worst } : {}) },
      ...p.lines.map((l) => ({ ...l, label: `#${i + 1} ${l.label}` })),
    ];
  });
};

const BATCH_MODES: [number, string][] = [
  [0x00010000, "All or nothing: every inner transaction applies, or none does"],
  [0x00020000, "Only one: the first inner transaction that succeeds applies, the rest are skipped"],
  [0x00040000, "Until failure: applies in order and stops at the first failure"],
  [0x00080000, "Independent: each inner transaction applies or fails on its own"],
];

// AccountSet SetFlag/ClearFlag values (xrpl.js 5.3 AccountSetAsfFlags).
const ASF: Record<number, string> = {
  1: "require destination tag", 2: "require authorization for trust lines", 3: "disallow XRP", 4: "DISABLE MASTER KEY",
  5: "track account transaction ID", 6: "no freeze (permanent)", 7: "global freeze", 8: "default ripple", 9: "deposit authorization",
  10: "authorized NFT minter", 12: "block incoming NFT offers", 13: "block incoming checks", 14: "block incoming payment channels",
  15: "block incoming trust lines", 16: "allow trust line clawback (permanent)", 17: "allow trust line locking",
};

export const CORE_FORMATS: Record<string, Formatter> = {
  raw: (v) => (typeof v === "object" ? JSON.stringify(v) : String(v)),
  count: (v) => String(Array.isArray(v) ? v.length : 0),
  asf_flag: (v) => {
    const n = Number(v);
    const name = ASF[n] ?? `unknown flag ${n}`;
    return n === 4 || n === 16 || n === 6 ? { value: name, risk: "danger" } : ASF[n] ? name : { value: name, risk: "warn" };
  },
  /** SignerListSet entries: account (weight n). */
  signer_entries: (v, _tx, ctx) =>
    (Array.isArray(v) ? v : [])
      .map((e) => {
        const se = ((e as { SignerEntry?: Record<string, unknown> }).SignerEntry ?? {}) as Record<string, unknown>;
        return `${account(se.Account, ctx).value} (weight ${se.SignerWeight})`;
      })
      .join(", "),
  int: (v) => String(v),
  account: (v, _tx, ctx) => account(v, ctx),
  accounts: (v, _tx, ctx) => (Array.isArray(v) ? v.map((a) => account(a, ctx).value).join(", ") : String(v)),
  amount: (v, _tx, ctx) => amount(v, ctx),
  drops: (v) => dropsToXrp(String(v)),
  hash: (v) => ({ value: short(String(v), 8, 6), full: String(v) }),
  hex_text: (v) => {
    const t = hexText(String(v));
    return t ?? { value: short(String(v), 10, 6), full: String(v) };
  },
  ripple_time: (v, _tx, ctx) => rippleTime(v, ctx),
  duration: (v) => duration(Number(v)),
  flags: (v) => `0x${Number(v).toString(16).toUpperCase().padStart(8, "0")}`,
  memos,
  inner_transactions: innerTransactions,
  batch_mode: (v) => BATCH_MODES.find(([bit]) => (Number(v) & bit) !== 0)?.[1] ?? { value: "no mode flag set", risk: "danger" },
  /** DelegateSet: granted permissions by name. An empty list deletes the delegation. */
  permissions: (v) => {
    const names = (Array.isArray(v) ? v : []).map((p) => String((p as { Permission?: { PermissionValue?: unknown } }).Permission?.PermissionValue));
    return names.length ? names.join(", ") : { value: "none: revokes every permission", risk: "warn" };
  },
  /** Batch / multisig: who has signed so far. */
  signers: (v, _tx, ctx) => {
    const list = Array.isArray(v) ? v : [];
    const accts = list.map((s) => {
      const o = s as Record<string, Record<string, unknown>>;
      const inner = o.BatchSigner ?? o.Signer ?? o;
      return account(inner.Account, ctx).value;
    });
    return accts.length ? accts.join(", ") : "nobody yet";
  },
};

export const FORMATS: Record<string, Formatter> = { ...CORE_FORMATS, ...LENDING_FORMATS };
