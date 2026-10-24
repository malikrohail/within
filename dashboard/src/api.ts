// Typed fetchers for the wallet API in docs/CONTRACT.md.
import type { Preview } from "./preview";
import type { Accounts } from "./tower/flows";

export const WALLET_URL: string = (import.meta.env.VITE_WALLET_URL ?? "http://localhost:7402").replace(/\/$/, "");
// Operator routes (policy, merchants, domain, delegate) need X-Wallet-Token = the wallet's WALLET_ADMIN_TOKEN.
const WALLET_TOKEN: string | undefined = import.meta.env.VITE_WALLET_TOKEN;
const operator: RequestInit = { headers: WALLET_TOKEN ? { "X-Wallet-Token": WALLET_TOKEN } : {} };

export type RequestStatus = "auto" | "held" | "approved" | "refused" | "expired";

export interface WalletRequest {
  id: string;
  ts: string;
  merchant: string;
  amountDrops: string;
  purpose: string;
  resourceUrl: string | null;
  status: RequestStatus;
  reason: string | null;
  signer: "hot" | "device" | "hot (delegated)" | null;
  txHash: string | null;
  /** v1.5: plain-English preview of the built transaction. */
  preview?: Preview;
  /** "lend" rows: the loan this device approval stands for. */
  loanPreview?: Preview;
  /** v1.6: sha256 of policy.json when the request was decided. */
  policyHash?: string;
  // Delegate build: absent means "hot" / "pay".
  source?: "hot" | "treasury";
  kind?: "pay" | "delegate";
}

export interface WalletStatus {
  hotAccount: string | null;
  hotBalanceDrops: string | null;
  deviceAccount: string | null;
  deviceBalanceDrops: string | null;
  deviceConnected: boolean;
  deviceApp: string | null;
  spentTodayDrops: string;
  pending: number;
}

export interface Policy {
  perTxCapDrops: string;
  dailyBudgetDrops: string;
  allowedMerchants: string[];
  allowedNetworks: string[];
  allowedAssets: string[];
  holdTimeoutSeconds: number;
  // v1.4: the on-ledger allowlist. Optional so an older wallet without them still renders.
  credentialIssuer?: string;
  credentialType?: string;
  /** v1.6: the policy's lifetime; past it every payment is refused (policy_expired). */
  expiresAt?: string;
}

export interface Merchant {
  address: string;
  accepted: boolean;
  txHash?: string | null;
}

/** The Permissioned Domain whose membership is the vet credential. */
export interface Domain {
  domainId: string;
  owner: string;
  acceptedCredentials: { issuer: string; credentialType: string }[];
  txHash: string;
}

export interface Delegation {
  treasury: string;
  agent: string;
  permissions: string[];
  objects: unknown[];
}

export type DelegateAction = "grant" | "revoke";

export interface DelegateResult {
  action: DelegateAction;
  requestId: string;
  txHash: string;
  engineResult: string;
  permissions: string[];
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${WALLET_URL}${path}`, {
    ...init,
    headers: { ...(init?.body ? { "Content-Type": "application/json" } : {}), ...(init?.headers as Record<string, string> | undefined) },
  });
  const text = await res.text();
  let body: unknown = null;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    body = text;
  }
  if (!res.ok) {
    const reason =
      body && typeof body === "object" && "reason" in body ? String((body as { reason: unknown }).reason) : text;
    throw new ApiError(res.status, `${res.status} ${reason || res.statusText}`);
  }
  return body as T;
}

export const getStatus = () => call<WalletStatus>("/v1/status");
export const getRequests = (limit = 200) => call<WalletRequest[]>(`/v1/requests?limit=${limit}`);
export const getPolicy = () => call<Policy>("/v1/policy");
export const putPolicy = (policy: Policy) => call<Policy>("/v1/policy", { ...operator, method: "PUT", body: JSON.stringify(policy) });
export const deviceTap = (id: string) =>
  call<{ ok: boolean }>(`/v1/requests/${encodeURIComponent(id)}/device-tap`, { method: "POST" });
export const deny = (id: string) => call<unknown>(`/v1/requests/${encodeURIComponent(id)}/deny`, { method: "POST" });
export const getMerchants = () => call<Merchant[]>("/v1/merchants");
export const vetMerchant = (address: string) =>
  call<{ txHash: string }>("/v1/merchants", { ...operator, method: "POST", body: JSON.stringify({ address }) });
export const revokeMerchant = (address: string) =>
  call<{ txHash: string }>(`/v1/merchants/${encodeURIComponent(address)}`, { ...operator, method: "DELETE" });
export const getDomain = () => call<{ domain: Domain | null }>("/v1/domain");
export const setDomain = () => call<{ txHash: string; domain: Domain | null }>("/v1/domain", { ...operator, method: "POST" });
export const getDelegation = () => call<Delegation>("/v1/delegate");
/** Blocks until the DelegateSet is approved (or denied) on the Ledger. */
export const setDelegation = (action: DelegateAction) =>
  call<DelegateResult>("/v1/delegate", { ...operator, method: "POST", body: JSON.stringify({ action }) });
/** Addresses only (names and roles from agent/merchants.json and lending/accounts.json) for the Control tower. */
export const getAccounts = () => call<Accounts>("/v1/accounts");
