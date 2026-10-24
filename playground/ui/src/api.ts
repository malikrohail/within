export const API = (import.meta.env.VITE_API_URL as string | undefined) ?? "http://localhost:7510";
export const EXPLORER = "https://devnet.xrpl.org";

export type Rule = { rule: string; value: unknown; points: number };
export type Breakdown = {
  total: number;
  weights: Record<string, number>;
  ledger: { score: number; rules: Rule[] };
  declared: { score: number; rules: Rule[] };
  bank: { score: number; rules: Rule[] } | null;
  capped: string | null;
};
export type Payment = { hash: string; drops: string; payer: string; invoice: string; ledgerIndex: number | null };
export type Sweep = { incomeHash: string; loanPayHash: string; drops: string; engineResult: string; loanId: string };
export type Loan = {
  status: "deciding" | "auto" | "held" | "approved" | "denied" | "refused" | "expired" | "failed" | "defaulted";
  principalDrops: string;
  requestId: string | null;
  reason: string | null;
  loanId: string | null;
  txHash: string | null;
  score?: number;
  decidedBy?: string;
  memo?: string | null;
  deskTs?: number;
  askedAt: number;
  activeAt?: number;
};
export type Credential = { createHash: string | null; acceptHash: string; acceptResult: string; issuer: string } | null;
export type Default = {
  hash: string;
  engineResult: string;
  coverAbsorbedDrops: string | null;
  vaultLossDrops: string | null;
  defaultAmountDrops: string | null;
} | null;
export type Session = {
  id: string;
  address: string;
  createdAt: number;
  balanceDrops: string;
  payments: Payment[];
  customerCount: number;
  credential: Credential;
  loan: Loan | null;
  sweeps: Sweep[];
  default: Default;
  score: number;
  breakdown: Breakdown;
  ledger: Record<string, unknown>;
  level: number;
};
export type Facts = {
  minScoreAuto: number;
  minScore: number;
  holdTimeoutSeconds: number;
  maxAskDrops: string;
  minAskDrops: string;
  incomeDrops: string;
  paymentInterval: number;
  gracePeriod: number;
  termSeconds: number;
  ceiling: { noCredential: number; withCredential: number };
  broker: string;
  policyHash: string;
};

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(API + path, { headers: { "content-type": "application/json" }, ...init });
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(typeof body.detail === "string" ? body.detail : `${r.status}`);
  return body as T;
}

export const api = {
  facts: () => call<Facts>("/v1/facts"),
  create: () => call<Session>("/v1/sessions", { method: "POST" }),
  get: (id: string) => call<Session>(`/v1/sessions/${id}`),
  reset: (id: string) => call<{ ok: boolean }>(`/v1/sessions/${id}/reset`, { method: "POST" }),
  income: (id: string) => call<{ payment: Payment; sweeps: Sweep[]; session: Session }>(`/v1/sessions/${id}/income`, { method: "POST" }),
  credential: (id: string) =>
    call<{ away?: boolean; credential?: Credential; session: Session }>(`/v1/sessions/${id}/credential`, { method: "POST" }),
  borrow: (id: string, amountXrp: number) =>
    call<Session>(`/v1/sessions/${id}/borrow`, { method: "POST", body: JSON.stringify({ amountXrp }) }),
  default: (id: string) => call<{ default: Default; session: Session }>(`/v1/sessions/${id}/default`, { method: "POST" }),
};

export const xrp = (drops: string | number | null | undefined) =>
  drops == null ? "?" : `${(Number(drops) / 1e6).toLocaleString(undefined, { maximumFractionDigits: 6 })} XRP`;
export const short = (s: string) => `${s.slice(0, 6)}…${s.slice(-4)}`;
