export const EXPLORER = "https://devnet.xrpl.org";
export const txUrl = (hash: string) => `${EXPLORER}/transactions/${hash}`;
export const accountUrl = (addr: string) => `${EXPLORER}/accounts/${addr}`;

const DROPS = 1_000_000n;

function toBig(drops: string | number | null | undefined): bigint | null {
  if (drops == null || drops === "") return null;
  try {
    return BigInt(String(drops).split(".")[0]);
  } catch {
    return null;
  }
}

const group = (s: string) => s.replace(/\B(?=(\d{3})+(?!\d))/g, ",");

/** Drops -> XRP rounded to 2 dp, as [whole, frac2]; exact integer math. */
function parts2(d: bigint): [string, string, boolean] {
  const neg = d < 0n;
  const a = neg ? -d : d;
  const cents = (a * 100n + DROPS / 2n) / DROPS; // round half up to 0.01 XRP
  return [group(String(cents / 100n)), String(cents % 100n).padStart(2, "0"), neg];
}

/** Hero style: "243.00" (always 2 dp). */
export function xrpFixed(drops: string | null | undefined): string {
  const d = toBig(drops);
  if (d == null) return "-";
  const [w, f, neg] = parts2(d);
  return `${neg ? "-" : ""}${w}.${f}`;
}

/** Sentence style: "60", "6.67", "0.000004" (no trailing zeros; full precision when 2 dp would hide it). */
export function xrpNum(drops: string | number | null | undefined): string {
  const d = toBig(drops);
  if (d == null) return "-";
  const [w, f, neg] = parts2(d);
  if (d !== 0n && w === "0" && f === "00") {
    const a = d < 0n ? -d : d;
    const frac = String(a % DROPS).padStart(6, "0").replace(/0+$/, "");
    return `${neg ? "-" : ""}0.${frac}`;
  }
  const ff = f.replace(/0+$/, "");
  return `${neg ? "-" : ""}${w}${ff ? "." + ff : ""}`;
}

export const xrp = (drops: string | number | null | undefined) => `${xrpNum(drops)} XRP`;

export const sumDrops = (...ds: (string | null | undefined)[]) =>
  String(ds.reduce<bigint>((s, d) => s + (toBig(d) ?? 0n), 0n));

export const dropsNum = (drops: string | null | undefined) => Number(toBig(drops) ?? 0n);

export const short = (s: string | null | undefined, n = 6) =>
  !s ? "-" : s.length <= n + 5 ? s : `${s.slice(0, n)}…${s.slice(-4)}`;

/** Seconds -> m:ss (h:mm:ss over an hour). */
export function clock(sec: number): string {
  const t = Math.max(0, Math.floor(sec));
  const h = Math.floor(t / 3600);
  const m = Math.floor((t % 3600) / 60);
  const s = String(t % 60).padStart(2, "0");
  return h > 0 ? `${h}:${String(m).padStart(2, "0")}:${s}` : `${m}:${s}`;
}

/** 16.5, 43, 41.2 (1 dp, trailing zero dropped). */
export const pct1 = (n: number) => `${Number(n.toFixed(1))}`;

export const groupInt = (n: number) => n.toLocaleString("en-US");

const plural = (n: number, w: string) => `${n} ${w}${n === 1 ? "" : "s"}`;

/** 270 -> "4.5 minutes", 7776000 -> "90 days". */
export function duration(sec: number): string {
  const r = (x: number) => Number(x.toFixed(1));
  if (sec < 120) return plural(sec, "second");
  if (sec < 7200) return `${r(sec / 60)} minutes`;
  if (sec < 172800) return `${r(sec / 3600)} hours`;
  return `${r(sec / 86400)} days`;
}

export function ago(unix: number, now: number): string {
  const s = Math.max(0, now - unix);
  if (s < 45) return "just now";
  if (s < 3600) return `${Math.max(1, Math.round(s / 60))} min ago`;
  if (s < 86400) return `${Math.round(s / 3600)} h ago`;
  return `${Math.round(s / 86400)} d ago`;
}

export const paymentsWord = (n: number) => plural(n, "payment");
