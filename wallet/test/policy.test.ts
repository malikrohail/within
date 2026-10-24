import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { Audit } from "../src/audit.js";
import { decide, loadPolicy, needsCredentialLookup } from "../src/policy.js";
import type { Policy, RequestRow } from "../src/types.js";

const M = "rMerchantGoodXXXXXXXXXXXXXXXXXXXX";
const policy: Policy = {
  perTxCapDrops: "100000",
  dailyBudgetDrops: "5000000",
  allowedMerchants: [M],
  allowedNetworks: ["xrpl:1"],
  allowedAssets: ["XRP"],
  holdTimeoutSeconds: 90,
  credentialType: "x402-merchant",
};
const req = (over: Partial<{ network: string; asset: string; payTo: string; amount: string }> = {}) => ({
  network: "xrpl:1",
  asset: "XRP",
  payTo: M,
  amount: "1000",
  ...over,
});

describe("decide (contract order)", () => {
  it("1. refuses a network not allowed", () => {
    expect(decide(req({ network: "xrpl:0" }), 0n, policy)).toEqual({ kind: "refuse", reason: "network_not_allowed" });
  });
  it("2. refuses an asset not allowed", () => {
    expect(decide(req({ asset: "RLUSD" }), 0n, policy)).toEqual({ kind: "refuse", reason: "asset_not_allowed" });
  });
  it("3. refuses a merchant neither in the static list nor credentialed", () => {
    expect(decide(req({ payTo: "rRogue" }), 0n, policy)).toEqual({ kind: "refuse", reason: "merchant_not_credentialed" });
    expect(decide(req({ payTo: "rRogue" }), 0n, policy, false)).toEqual({ kind: "refuse", reason: "merchant_not_credentialed" });
  });
  it("3. passes a credentialed merchant, and a static override without a credential", () => {
    expect(decide(req({ payTo: "rVetted" }), 0n, policy, true)).toEqual({ kind: "auto" });
    expect(decide(req(), 0n, policy, false)).toEqual({ kind: "auto" });
  });
  it("3. a credential does not skip rules 1, 2, or 4", () => {
    expect(decide(req({ payTo: "rVetted", network: "xrpl:0" }), 0n, policy, true)).toMatchObject({ reason: "network_not_allowed" });
    expect(decide(req({ payTo: "rVetted", asset: "RLUSD" }), 0n, policy, true)).toMatchObject({ reason: "asset_not_allowed" });
    expect(decide(req({ payTo: "rVetted", amount: "5000001" }), 0n, policy, true)).toMatchObject({ reason: "daily_budget_exceeded" });
  });
  it("needs the ledger lookup only when rules 1-2 pass and payTo is not a static override", () => {
    expect(needsCredentialLookup(req({ payTo: "rVetted" }), policy)).toBe(true);
    expect(needsCredentialLookup(req(), policy)).toBe(false);
    expect(needsCredentialLookup(req({ payTo: "rVetted", network: "xrpl:0" }), policy)).toBe(false);
    expect(needsCredentialLookup(req({ payTo: "rVetted", asset: "RLUSD" }), policy)).toBe(false);
  });
  it("4. refuses when amount + spent-today exceeds the daily budget", () => {
    expect(decide(req({ amount: "1001" }), 4_999_000n, policy)).toEqual({ kind: "refuse", reason: "daily_budget_exceeded" });
    expect(decide(req({ amount: "1000" }), 4_999_000n, policy)).toEqual({ kind: "auto" });
  });
  it("5. holds above the per-tx cap", () => {
    expect(decide(req({ amount: "100001" }), 0n, policy)).toEqual({ kind: "hold" });
  });
  it("6. autos otherwise", () => {
    expect(decide(req(), 0n, policy)).toEqual({ kind: "auto" });
  });
  it("amount == cap is auto, cap+1 is hold", () => {
    expect(decide(req({ amount: "100000" }), 0n, policy)).toEqual({ kind: "auto" });
    expect(decide(req({ amount: "100001" }), 0n, policy)).toEqual({ kind: "hold" });
  });
  it("evaluates rules in order: network before merchant, budget before hold", () => {
    expect(decide(req({ network: "xrpl:0", payTo: "rRogue" }), 0n, policy).kind).toBe("refuse");
    expect(decide(req({ network: "xrpl:0", payTo: "rRogue" }), 0n, policy)).toMatchObject({ reason: "network_not_allowed" });
    expect(decide(req({ amount: "5000001" }), 0n, policy)).toMatchObject({ reason: "daily_budget_exceeded" });
  });
  it("0. an expired policy refuses everything, before any other rule", () => {
    const expiring = { ...policy, expiresAt: "2026-10-25T00:00:00-04:00" };
    const before = new Date("2026-10-24T23:59:59-04:00");
    const after = new Date("2026-10-25T00:00:00-04:00");
    expect(decide(req(), 0n, expiring, false, before)).toEqual({ kind: "auto" });
    expect(decide(req(), 0n, expiring, false, after)).toEqual({ kind: "refuse", reason: "policy_expired" });
    expect(decide(req({ network: "xrpl:0", amount: "100001" }), 0n, expiring, false, after)).toEqual({ kind: "refuse", reason: "policy_expired" });
    // No expiresAt: no lifetime, as before v1.6.
    expect(decide(req(), 0n, policy, false, new Date("2099-01-01T00:00:00Z"))).toEqual({ kind: "auto" });
  });
});

describe("Audit.spentToday", () => {
  const row = (id: string, status: RequestRow["status"], amountDrops: string, ts = new Date().toISOString()): RequestRow => ({
    id, ts, merchant: M, amountDrops, purpose: "", resourceUrl: "", status, reason: null, signer: null, txHash: null,
  });

  it("counts only auto|approved since local midnight", () => {
    const audit = new Audit(join(mkdtempSync(join(tmpdir(), "pw-")), "requests.jsonl"));
    audit.put(row("a", "auto", "1000"));
    audit.put(row("b", "approved", "200000"));
    audit.put(row("c", "refused", "5000"));
    audit.put(row("d", "held", "300000"));
    audit.put(row("e", "expired", "400000"));
    const yesterday = new Date();
    yesterday.setDate(yesterday.getDate() - 1);
    audit.put(row("f", "auto", "7000", yesterday.toISOString()));
    expect(audit.spentToday()).toBe(201_000n);
  });

  it("keeps one row per id, newest first, and survives a restart", () => {
    const path = join(mkdtempSync(join(tmpdir(), "pw-")), "requests.jsonl");
    const audit = new Audit(path);
    audit.put(row("a", "auto", "1000"));
    audit.put(row("b", "held", "200000"));
    audit.update("b", { status: "approved", signer: "device", txHash: "AB" });
    expect(audit.list().map((r) => [r.id, r.status])).toEqual([["b", "approved"], ["a", "auto"]]);
    const reopened = new Audit(path);
    expect(reopened.list().map((r) => r.id)).toEqual(["b", "a"]);
    expect(reopened.spentToday()).toBe(201_000n);
  });

  it("expires held rows orphaned by a restart", () => {
    const path = join(mkdtempSync(join(tmpdir(), "pw-")), "requests.jsonl");
    new Audit(path).put(row("h", "held", "200000"));
    expect(new Audit(path).get("h")).toMatchObject({ status: "expired", reason: "hold_timeout" });
  });
});

describe("policy.json", () => {
  it("ships the contract shape: no static merchants, no issuer (filled with the hot account at runtime)", () => {
    const p = loadPolicy(new URL("../policy.json", import.meta.url).pathname);
    expect(Object.keys(p)).toEqual(["perTxCapDrops", "dailyBudgetDrops", "allowedMerchants", "allowedNetworks", "allowedAssets", "holdTimeoutSeconds", "credentialType"]);
    expect(p.allowedNetworks).toEqual(["xrpl:1"]);
    expect(p.allowedMerchants).toEqual([]);
    expect(p.credentialType).toBe("x402-merchant");
  });
  it("loads a pre-v1.4 policy file without the credential fields", () => {
    const path = join(mkdtempSync(join(tmpdir(), "pw-")), "policy.json");
    const { credentialType: _, ...old } = policy;
    writeFileSync(path, JSON.stringify(old));
    const p = loadPolicy(path);
    expect(p.credentialType).toBe("x402-merchant");
    expect(p.credentialIssuer).toBeUndefined();
  });
  it("expiresAt must be an ISO 8601 time with an offset", () => {
    const path = join(mkdtempSync(join(tmpdir(), "pw-")), "policy.json");
    writeFileSync(path, JSON.stringify({ ...policy, expiresAt: "2026-10-25T00:00:00-04:00" }));
    expect(loadPolicy(path).expiresAt).toBe("2026-10-25T00:00:00-04:00");
    writeFileSync(path, JSON.stringify({ ...policy, expiresAt: "tomorrow" }));
    expect(() => loadPolicy(path)).toThrow();
  });
});
