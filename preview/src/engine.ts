// The data-driven parser: a descriptor (format/<Type>.json) says which fields to show, how to format
// them, and which conditions raise a risk line. describe() is the reference implementation.
import { FORMATS } from "./formats.js";
import type { Ctx, Descriptor, Line, Preview, Risk, Tx } from "./types.js";

const RANK: Record<Risk, number> = { info: 0, warn: 1, danger: 2 };

export function get(tx: Tx, path: string): unknown {
  let cur: unknown = tx;
  for (const key of path.split(".")) {
    if (cur === null || typeof cur !== "object") return undefined;
    cur = (cur as Record<string, unknown>)[key];
  }
  return cur;
}

const present = (v: unknown) => v !== undefined && v !== null && v !== "" && !(Array.isArray(v) && v.length === 0);

function literal(raw: string): unknown {
  const s = raw.trim();
  if (/^".*"$/.test(s)) return s.slice(1, -1);
  if (s === "true" || s === "false") return s === "true";
  return Number(s);
}

/** Evaluates a risk rule's `when` (grammar in types.ts). An unparseable rule is treated as true: fail loud. */
export function when(expr: string, tx: Tx): boolean {
  const e = expr.trim();
  let m = /^len\((\S+)\)\s*(==|!=|>|<)\s*(\d+)$/.exec(e);
  if (m) {
    const v = get(tx, m[1]);
    const n = Array.isArray(v) ? v.length : 0;
    const k = Number(m[3]);
    return m[2] === "==" ? n === k : m[2] === "!=" ? n !== k : m[2] === ">" ? n > k : n < k;
  }
  m = /^(\S+)\s*&\s*(0x[0-9a-fA-F]+|\d+)$/.exec(e);
  if (m) return (Number(get(tx, m[1]) ?? 0) & Number(m[2])) !== 0;
  m = /^(\S+)\s*(==|!=)\s*(.+)$/.exec(e);
  if (m) {
    const v = get(tx, m[1]);
    const lit = literal(m[3]);
    const eq = typeof lit === "number" ? Number(v) === lit : v === lit;
    return m[2] === "==" ? eq : !eq;
  }
  m = /^!(\S+)$/.exec(e);
  if (m) return !present(get(tx, m[1]));
  if (/^\S+$/.test(e)) return present(get(tx, e));
  return true;
}

function formatOne(name: string, v: unknown, tx: Tx, ctx: Ctx): { value: string; full?: string; risk?: Risk } | Line[] {
  const f = FORMATS[name];
  if (!f) return { value: `${String(v)} (unknown format "${name}")`, risk: "warn" };
  const out = f(v, tx, ctx, describe);
  return typeof out === "string" ? { value: out } : out;
}

/** Replaces "{Path}" / "{Path|format}" with formatted values; a missing path renders as "?". */
export function template(t: string, tx: Tx, ctx: Ctx): string {
  return t.replace(/\{([^}|]+)(?:\|([^}]+))?\}/g, (_m, path: string, fmt?: string) => {
    const v = get(tx, path.trim());
    if (!present(v)) return "?";
    const out = formatOne(fmt?.trim() ?? "raw", v, tx, ctx);
    return Array.isArray(out) ? out.map((l) => l.value).join(", ") : out.value;
  });
}

const DESCRIPTORS = new Map<string, Descriptor>();

export function register(d: Descriptor): void {
  DESCRIPTORS.set(d.type, d);
}

export function descriptorFor(type: string): Descriptor | undefined {
  return DESCRIPTORS.get(type);
}

function unknownType(tx: Tx, ctx: Ctx): Preview {
  const type = typeof tx.TransactionType === "string" ? tx.TransactionType : "(none)";
  const lines: Line[] = [{ label: "Type", value: type, risk: "danger" }];
  if (typeof tx.Account === "string") lines.push({ label: "Account", ...(formatOne("account", tx.Account, tx, ctx) as { value: string }) });
  lines.push({ label: "Risk", value: "No descriptor for this type: the wallet cannot say what it does. Read the raw fields before signing.", risk: "danger" });
  return { title: "Unrecognised transaction type", lines, summary: `Unrecognised transaction type ${type}: review the raw transaction before signing.` };
}

export function describe(tx: Tx, ctx: Ctx = {}): Preview {
  const d = typeof tx.TransactionType === "string" ? DESCRIPTORS.get(tx.TransactionType) : undefined;
  if (!d) return unknownType(tx, ctx);
  const lines: Line[] = [];
  for (const f of d.fields) {
    const v = get(tx, f.path);
    if (!present(v)) {
      if (f.required) lines.push({ label: f.label, value: "missing", risk: "warn" });
      continue;
    }
    const out = formatOne(f.format ?? "raw", v, tx, ctx);
    if (Array.isArray(out)) lines.push(...out);
    else {
      const risk = f.risk && (!out.risk || RANK[f.risk] > RANK[out.risk]) ? f.risk : out.risk;
      lines.push({ label: f.label, value: out.value, ...(out.full ? { full: out.full } : {}), ...(risk ? { risk } : {}) });
    }
  }
  const hits = (d.risk ?? []).filter((r) => when(r.when, tx));
  for (const r of hits) lines.push({ label: "Risk", value: r.text, risk: r.level });
  const v = d.variants?.find((x) => when(x.when, tx));
  const title = template(v?.title ?? d.title, tx, ctx);
  let summary = template(v ? (v.summary ?? v.title) : (d.summary ?? d.title), tx, ctx);
  const worst = hits.filter((r) => r.level !== "info").sort((a, b) => RANK[b.level] - RANK[a.level])[0];
  if (worst) summary += ` (${worst.level}: ${worst.text})`;
  return { title, lines, summary };
}

/** Highest risk on a card, for badges. */
export function worstRisk(p: Preview): Risk | null {
  let worst: Risk | null = null;
  for (const l of p.lines) if (l.risk && (!worst || RANK[l.risk] > RANK[worst])) worst = l.risk;
  return worst;
}
