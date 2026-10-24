import type { CoverTopUp, Health, Loan, LoanRequest, Policy, Vault } from "./types";

export const DESK_URL: string = import.meta.env.VITE_DESK_URL ?? "http://localhost:7500";
export const DESK_HOST = DESK_URL.replace(/^https?:\/\//, "").replace(/\/$/, "");
export const WALLET_URL: string = import.meta.env.VITE_WALLET_URL ?? "http://127.0.0.1:7402";
// Operator routes (approve, deny, cover, PUT policy, signed-loan-set) need X-Desk-Token (desk env DESK_TOKEN).
const DESK_TOKEN: string | undefined = import.meta.env.VITE_DESK_TOKEN;
const op = (init: RequestInit = {}): RequestInit => ({
  ...init,
  headers: { ...(init.headers ?? {}), ...(DESK_TOKEN ? { "X-Desk-Token": DESK_TOKEN } : {}) },
});

export class DeskError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${DESK_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body);
    } catch {
      /* non-JSON error body */
    }
    throw new DeskError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

export const getVault = () => call<Vault>("/v1/vault");
export const getPolicy = () => call<Policy>("/v1/policy");
export const putPolicy = (p: Policy) => call<Policy>("/v1/policy", op({ method: "PUT", body: JSON.stringify(p) }));
export const getHealth = () => call<Health>("/health");
export const getRequests = () => call<{ requests: LoanRequest[] }>("/v1/loan-requests").then((r) => r.requests);
export const getLoans = () => call<{ loans: Loan[]; ledgerIndex: number }>("/v1/loans");
export const approve = (id: string, approvalTxHash?: string) =>
  call<LoanRequest>(
    `/v1/loan-requests/${id}/approve`,
    op({ method: "POST", body: JSON.stringify(approvalTxHash ? { approvalTxHash } : {}) }),
  );
export const topUpCover = (amountDrops: string) =>
  call<CoverTopUp>("/v1/broker/cover", op({ method: "POST", body: JSON.stringify({ amountDrops }) }));
export const deny = (id: string) =>
  call<LoanRequest>(`/v1/loan-requests/${id}/deny`, op({ method: "POST", body: "{}" }));
export const getSignedLoanSet = (id: string) =>
  call<{ id: string; loanSetHash: string; signedLoanSet: string }>(`/v1/loan-requests/${id}/signed-loan-set`, op());

/** The wallet (wallet/) refused or failed the device approval; `reason` is its own word (denied_on_device, ...). */
export class WalletError extends Error {
  constructor(
    public status: number,
    public reason: string,
  ) {
    super(reason);
  }
}

/** Ask the Ledger to sign the 1-drop testnet approval Payment whose memo is loanSetHash (wallet POST /v1/lend/approve).
 *  The wallet re-hashes loanSetBlob and refuses a mismatch. Resolves to the approval Payment's tx hash. */
export async function walletApprove(loanSetBlob: string, loanSetHash: string): Promise<string> {
  let res: Response;
  try {
    res = await fetch(`${WALLET_URL}/v1/lend/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ loanSetBlob, loanSetHash }),
    });
  } catch (e) {
    throw new WalletError(0, `wallet_unreachable: ${String(e)}`);
  }
  let body: { txHash?: string; reason?: string } = {};
  try {
    body = await res.json();
  } catch {
    /* non-JSON body */
  }
  if (!res.ok || !body.txHash) throw new WalletError(res.status, body.reason ?? res.statusText ?? "no_tx_hash");
  return body.txHash;
}

/** Approve a held request. With an approver account on the desk: blob -> Ledger approval Payment -> approve with
 *  its hash. Without one: token-only approve (scripted demo, API stand-in). */
export async function approveHeld(id: string): Promise<LoanRequest> {
  const health = await getHealth();
  if (!health.approverAccount) return approve(id);
  const { signedLoanSet, loanSetHash } = await getSignedLoanSet(id);
  const txHash = await walletApprove(signedLoanSet, loanSetHash);
  return approve(id, txHash);
}
