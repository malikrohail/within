const DROPS_PER_XRP = 1_000_000n;

/** "5000000" -> "5", "1000" -> "0.001", "1234567" -> "1.234567". Null or garbage -> "—". */
export function dropsToXrp(drops: string | number | null | undefined): string {
  if (drops === null || drops === undefined || !/^\d+$/.test(String(drops))) return "—";
  const n = BigInt(drops);
  const whole = n / DROPS_PER_XRP;
  const frac = (n % DROPS_PER_XRP).toString().padStart(6, "0").replace(/0+$/, "");
  return frac ? `${whole}.${frac}` : whole.toString();
}

/** "0.05" -> "50000"; null if not a non-negative amount with at most 6 decimals. */
export function xrpToDrops(xrp: string): string | null {
  const m = /^(\d+)(?:\.(\d{0,6}))?$/.exec(xrp.trim());
  if (!m) return null;
  return (BigInt(m[1]) * DROPS_PER_XRP + BigInt((m[2] ?? "").padEnd(6, "0") || "0")).toString();
}

export function shortHash(hash: string): string {
  return hash.slice(0, 8);
}

export function shortAccount(account: string | null | undefined): string {
  if (!account) return "—";
  return account.length > 14 ? `${account.slice(0, 6)}…${account.slice(-4)}` : account;
}

export function relativeTime(iso: string, now: number = Date.now()): string {
  const secs = Math.max(0, Math.round((now - Date.parse(iso)) / 1000));
  if (Number.isNaN(secs)) return "";
  if (secs < 60) return `${secs}s ago`;
  if (secs < 3600) return `${Math.floor(secs / 60)}m ago`;
  return `${Math.floor(secs / 3600)}h ago`;
}

export const explorerTx = (hash: string) => `https://testnet.xrpl.org/transactions/${hash}`;
export const explorerAccount = (account: string) => `https://testnet.xrpl.org/accounts/${account}`;

const REASON_TEXT: Record<string, string> = {
  merchant_not_credentialed: "Merchant not vetted on-ledger",
  merchant_not_allowed: "Merchant not on allowlist",
  daily_budget_exceeded: "Over daily budget",
  network_not_allowed: "Network not allowed",
  asset_not_allowed: "Asset not allowed",
  denied_on_device: "Denied on the Ledger",
  device_unavailable: "Ledger not connected",
  hold_timeout: "No approval in time",
  policy_expired: "Policy expired: renew it to pay again",
};

/** Refusal/expiry reason code in plain words; unknown codes come back raw. */
export const reasonText = (reason: string) => REASON_TEXT[reason] ?? reason;
