import { createHash } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import { PolicySchema, type Decision, type Policy } from "./types.js";

export function loadPolicy(path: string): Policy {
  return PolicySchema.parse(JSON.parse(readFileSync(path, "utf8")));
}

/** sha256 of the policy file's bytes, uppercase hex: `shasum -a 256 data/policy.json` gives the same value. */
export function policyFileHash(path: string): string {
  return createHash("sha256").update(readFileSync(path)).digest("hex").toUpperCase();
}

export function savePolicy(path: string, policy: Policy): void {
  writeFileSync(path, JSON.stringify(policy, null, 2) + "\n");
}

type PayReq = { network: string; asset: string; payTo: string; amount: string };

/** Rule 3 needs the ledger only when rules 1-2 pass and payTo is not in the static override list. */
export function needsCredentialLookup(req: PayReq, policy: Policy): boolean {
  return policy.allowedNetworks.includes(req.network) && policy.allowedAssets.includes(req.asset) && !policy.allowedMerchants.includes(req.payTo);
}

/**
 * The contract rules, in contract order. Runs before any signing. `credentialed` is rule 3's
 * ledger lookup (accepted, unexpired Credential for payTo), done by the caller when needed.
 */
export function decide(req: PayReq, spentTodayDrops: bigint, policy: Policy, credentialed = false, now = new Date()): Decision {
  if (policy.expiresAt && now.getTime() >= Date.parse(policy.expiresAt)) return { kind: "refuse", reason: "policy_expired" };
  if (!policy.allowedNetworks.includes(req.network)) return { kind: "refuse", reason: "network_not_allowed" };
  if (!policy.allowedAssets.includes(req.asset)) return { kind: "refuse", reason: "asset_not_allowed" };
  if (!policy.allowedMerchants.includes(req.payTo) && !credentialed) return { kind: "refuse", reason: "merchant_not_credentialed" };
  const amount = BigInt(req.amount);
  if (amount + spentTodayDrops > BigInt(policy.dailyBudgetDrops)) return { kind: "refuse", reason: "daily_budget_exceeded" };
  if (amount > BigInt(policy.perTxCapDrops)) return { kind: "hold" };
  return { kind: "auto" };
}
