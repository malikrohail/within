import { createHash } from "node:crypto";
import { copyFileSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import type { FastifyInstance } from "fastify";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { decode, ECDSA, encode, hashes, verifySignature, Wallet, type CredentialCreate, type CredentialDelete, type DelegateSet, type Payment, type PermissionedDomainSet } from "xrpl";
import { Audit } from "../src/audit.js";
import { credentialTypeHex, Credentials, LSF_ACCEPTED, RIPPLE_EPOCH_OFFSET, type CredentialEntry, type CredentialRpc, type DomainEntry, type Submitted } from "../src/credentials.js";
import { DeviceError, type DeviceSignAction, type DeviceSigner, type DeviceStatusInfo } from "../src/device.js";
import { HoldQueue, type Tapper } from "../src/hold.js";
import { HotKey } from "../src/hot.js";
import type { Ledger } from "../src/payment.js";
import { buildApp, loanTermsText } from "../src/server.js";
import type { DelegateEntry, DirectResult, TreasuryLedger } from "../src/treasury.js";
import type { Policy } from "../src/types.js";

const MERCHANT = "rPT1Sjq2YGrBMTttX4GZHjKu9dyfzbpAYe";
const TOKEN = "test-operator-token";
const AUTH = { "x-wallet-token": TOKEN };
// Throwaway test keys derived from fixed entropy, so no seed literal lives in the repo.
const testSeed = (n: number, algorithm = ECDSA.secp256k1) => Wallet.fromEntropy(new Uint8Array(16).fill(n), { algorithm }).seed!;
const DEVICE_ADDR = "rUGeRsKjpnDVAi1uJYhAxWXbETC917VQ6B";
const DEVICE_PUB = "0250B6474EA8B26A489AB33E256EA546B94FF951C107CCF6C4E7BB31397BF93FF3";
const FAKE_DER = "3044022004E953BB951BFE4DA8D313F443211F7EB054DDE979DA55F3345539DE2B02153902203E9EBCFC27AB16B9C37FD8AE654457FD9DEF9DB216CEFCFFAC1E7508C61D11B2";

/** Fake Ledger: a sign action waits for the fake tapper's approve/reject. */
class FakeDevice implements DeviceSigner, Tapper {
  connected = true;
  maxConcurrent = 0;
  private active: { approve: () => void; reject: (e: DeviceError) => void } | null = null;
  private running = 0;
  signed: string[] = [];

  status(): DeviceStatusInfo {
    return { connected: this.connected, address: DEVICE_ADDR, publicKey: DEVICE_PUB, app: "XRP 2.8.1" };
  }
  sign(hex: string): DeviceSignAction {
    this.signed.push(hex);
    this.running++;
    this.maxConcurrent = Math.max(this.maxConcurrent, this.running);
    const result = new Promise<Uint8Array>((resolve, reject) => {
      this.active = { approve: () => resolve(Buffer.from(FAKE_DER, "hex")), reject };
    }).finally(() => {
      this.running--;
      this.active = null;
    });
    return { result, onScreen: Promise.resolve(), cancel: () => this.active?.reject(new DeviceError("stopped")) };
  }
  async waitForReview(): Promise<boolean> {
    return this.active !== null;
  }
  async approve(): Promise<void> {
    this.active?.approve();
  }
  async reject(): Promise<boolean> {
    this.active?.reject(new DeviceError("rejected_on_device"));
    return true;
  }
}

/** Fake ledger for Credential objects. Create adds an unaccepted entry, delete removes it. Pages hold one entry. */
class FakeCredentialRpc implements CredentialRpc {
  entries: CredentialEntry[] = [];
  lookups = 0;
  fail = false;
  result: string | null = null; // force an engine result
  submits: (CredentialCreate | CredentialDelete | PermissionedDomainSet)[] = [];
  domainList: DomainEntry[] = [];

  async credential(subject: string, issuer: string, typeHex: string) {
    this.lookups++;
    if (this.fail) throw new Error("rpc down");
    return this.entries.find((e) => e.Subject === subject && e.Issuer === issuer && e.CredentialType === typeHex) ?? null;
  }
  async credentialPage(account: string, marker?: unknown) {
    const mine = this.entries.filter((e) => e.Issuer === account || e.Subject === account);
    const i = (marker as number | undefined) ?? 0;
    return { entries: mine.slice(i, i + 1), marker: i + 1 < mine.length ? i + 1 : undefined };
  }
  async domains(owner: string) {
    if (this.fail) throw new Error("rpc down");
    return this.domainList.filter((d) => d.Owner === owner);
  }
  async submit(tx: CredentialCreate | CredentialDelete | PermissionedDomainSet): Promise<Submitted> {
    this.submits.push(tx);
    if (this.fail) throw new Error("rpc down");
    if (this.result) return { engineResult: this.result, txHash: this.result.startsWith("tem") ? null : "C".repeat(64) };
    if (tx.TransactionType === "PermissionedDomainSet") {
      const d = this.domainList.find((e) => e.index === tx.DomainID);
      if (tx.DomainID && !d) return { engineResult: "tecNO_ENTRY", txHash: "E".repeat(64) };
      if (d) d.AcceptedCredentials = tx.AcceptedCredentials as DomainEntry["AcceptedCredentials"];
      else this.domainList.push({ index: "0".repeat(63) + String(this.domainList.length + 1), Owner: tx.Account, AcceptedCredentials: tx.AcceptedCredentials as DomainEntry["AcceptedCredentials"], PreviousTxnID: "B".repeat(64) });
      return { engineResult: "tesSUCCESS", txHash: "B".repeat(64) };
    }
    const i = this.entries.findIndex((e) => e.Subject === tx.Subject && e.Issuer === tx.Account && e.CredentialType === tx.CredentialType);
    if (tx.TransactionType === "CredentialCreate") {
      if (i >= 0) return { engineResult: "tecDUPLICATE", txHash: "D".repeat(64) };
      this.entries.push({ Subject: tx.Subject, Issuer: tx.Account, CredentialType: tx.CredentialType, Flags: 0, PreviousTxnID: "A".repeat(64) });
    } else {
      if (i < 0) return { engineResult: "tecNO_ENTRY", txHash: "E".repeat(64) };
      this.entries.splice(i, 1);
    }
    return { engineResult: "tesSUCCESS", txHash: "B".repeat(64) };
  }
  /** An accepted credential from `issuer` with the default type. */
  vet(subject: string, issuer: string, over: Partial<CredentialEntry> = {}) {
    this.entries.push({ Subject: subject, Issuer: issuer, CredentialType: credentialTypeHex("x402-merchant"), Flags: LSF_ACCEPTED, PreviousTxnID: "F".repeat(64), ...over });
  }
}

/** Fake treasury ledger: DelegateSet blobs grant/revoke; a delegated Payment needs the grant. */
class FakeTreasury implements TreasuryLedger {
  entries: DelegateEntry[] = [];
  submitted: Record<string, unknown>[] = [];
  fail = false;
  async autofill(tx: DelegateSet) {
    return { ...tx, Fee: "12", Sequence: 9 };
  }
  async validatedLedgerIndex() {
    return 1000;
  }
  async submit(blob: string, hash: string): Promise<DirectResult> {
    if (this.fail) throw new Error("rpc down");
    const tx = decode(blob) as Record<string, unknown>;
    this.submitted.push(tx);
    if (tx.TransactionType === "DelegateSet") {
      const perms = tx.Permissions as DelegateEntry["Permissions"];
      this.entries = this.entries.filter((e) => !(e.Account === tx.Account && e.Authorize === tx.Authorize));
      if (perms.length) this.entries.push({ Account: tx.Account as string, Authorize: tx.Authorize as string, Permissions: perms });
      return { engineResult: "tesSUCCESS", txHash: hash };
    }
    const granted = this.entries.some((e) => e.Account === tx.Account && e.Authorize === tx.Delegate && e.Permissions.some((p) => p.Permission.PermissionValue === tx.TransactionType));
    if (tx.Delegate && !granted) return { engineResult: "terNO_DELEGATE_PERMISSION", txHash: null };
    return { engineResult: "tesSUCCESS", txHash: hash };
  }
  async delegates(account: string) {
    if (this.fail) throw new Error("rpc down");
    return this.entries.filter((e) => e.Account === account);
  }
}

const ledger: Ledger = {
  validatedLedgerIndex: async () => 1000,
  networkId: async () => 1,
  autofill: async (tx: Payment) => ({ ...tx, Fee: "12", Sequence: 7 }),
};

const body = (amount: string, payTo = MERCHANT, extra: Record<string, unknown> = {}) => ({
  requirements: {
    scheme: "exact", network: "xrpl:1", amount, asset: "XRP", payTo, maxTimeoutSeconds: 600,
    extra: { invoiceId: `inv-${amount}-${Math.round(performance.now() * 1000)}`, sourceTag: 20260601, ...extra },
  },
  purpose: "test purchase",
  resource: { url: "http://localhost:8001/lookup", description: "x" },
});

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

let app: FastifyInstance;
let dev: FakeDevice;
let dir: string;
let hot: HotKey;
let rpc: FakeCredentialRpc;
let treasury: FakeTreasury;

beforeEach(async () => {
  dir = mkdtempSync(join(tmpdir(), "pw-api-"));
  copyFileSync(new URL("../policy.json", import.meta.url), join(dir, "policy.json"));
  dev = new FakeDevice();
  hot = new HotKey(testSeed(1));
  rpc = new FakeCredentialRpc();
  treasury = new FakeTreasury();
  app = await buildApp({
    policyPath: join(dir, "policy.json"),
    audit: new Audit(join(dir, "requests.jsonl")),
    hot, ledger, device: dev, holds: new HoldQueue(dev, dev, () => {}),
    balanceDrops: async () => "98000000",
    credentials: new Credentials(rpc, hot.wallet),
    treasury,
    log: () => {},
    adminToken: TOKEN,
  });
  const policy = (await app.inject({ method: "GET", url: "/v1/policy" })).json<Policy>();
  await app.inject({ method: "PUT", url: "/v1/policy", headers: AUTH, payload: { ...policy, allowedMerchants: [MERCHANT] } });
});
afterEach(() => app.close());

const pay = (payload: unknown) => app.inject({ method: "POST", url: "/v1/pay", payload: payload as object });
const requests = async () => (await app.inject({ method: "GET", url: "/v1/requests" })).json<{ id: string; status: string; reason: string | null; signer: string | null; txHash: string | null }[]>();
const waitForHeld = async () => {
  for (let i = 0; i < 100; i++) {
    const held = (await requests()).find((r) => r.status === "held");
    if (held) return held;
    await sleep(10);
  }
  throw new Error("no held request");
};

describe("wallet API", () => {
  it("GET /health", async () => {
    expect((await app.inject({ method: "GET", url: "/health" })).json()).toEqual({ ok: true });
  });

  it("400 on a malformed body or a missing invoiceId", async () => {
    expect((await pay({ requirements: { amount: "x" } })).statusCode).toBe(400);
    const b = body("1000");
    delete (b.requirements.extra as Record<string, unknown>).invoiceId;
    const r = await pay(b);
    expect(r.statusCode).toBe(400);
    expect(r.json().reason).toBe("invoice_id_required");
  });

  it("auto: signs with the hot key and writes an audit row", async () => {
    const r = await pay(body("1000"));
    expect(r.statusCode).toBe(200);
    const j = r.json();
    expect(j).toMatchObject({ decision: "auto", signer: "hot", account: hot.address });
    expect(j.txHash).toBe(hashes.hashSignedTx(j.signedTxBlob));
    expect(decode(j.signedTxBlob)).toMatchObject({ Account: hot.address, Destination: MERCHANT, Amount: "1000", LastLedgerSequence: 1122 });
    expect(await requests()).toMatchObject([{ id: j.requestId, status: "auto", signer: "hot", txHash: j.txHash }]);
  });

  it("refused: merchant not on the allowlist → 403 and an audit row", async () => {
    const r = await pay(body("1000", "rRogueMerchantXXXXXXXXXXXXXXXXXXX"));
    expect(r.statusCode).toBe(403);
    expect(r.json()).toMatchObject({ decision: "refused", reason: "merchant_not_credentialed" });
    expect(await requests()).toMatchObject([{ status: "refused", reason: "merchant_not_credentialed", signer: null, txHash: null }]);
  });

  it("hold → device-tap → approved, row shows held then approved (one row per id)", async () => {
    const pending = pay(body("5000000"));
    const held = await waitForHeld();
    expect((await app.inject({ method: "GET", url: "/v1/status" })).json()).toMatchObject({ pending: 1, deviceConnected: true });
    // Clients often send Content-Type: application/json with no body on these POSTs.
    const tap = await app.inject({ method: "POST", url: `/v1/requests/${held.id}/device-tap`, headers: { "content-type": "application/json" }, payload: "" });
    expect(tap.statusCode).toBe(202);
    const r = await pending;
    expect(r.statusCode).toBe(200);
    const j = r.json();
    expect(j).toMatchObject({ decision: "approved", signer: "device", account: DEVICE_ADDR, requestId: held.id });
    const tx = decode(j.signedTxBlob) as Record<string, unknown>;
    expect(tx).toMatchObject({ Account: DEVICE_ADDR, SigningPubKey: DEVICE_PUB, TxnSignature: FAKE_DER, Amount: "5000000" });
    expect(j.txHash).toBe(hashes.hashSignedTx(j.signedTxBlob));
    // The device received encode(tx) without a signature.
    expect(decode(dev.signed[0])).not.toHaveProperty("TxnSignature");
    const rows = await requests();
    expect(rows).toHaveLength(1);
    expect(rows[0]).toMatchObject({ status: "approved", signer: "device", txHash: j.txHash });
    expect((await app.inject({ method: "GET", url: "/v1/status" })).json()).toMatchObject({ pending: 0, spentTodayDrops: "5000000" });
  });

  it("hold → deny → 403 denied_on_device", async () => {
    const pending = pay(body("200000"));
    const held = await waitForHeld();
    expect((await app.inject({ method: "POST", url: `/v1/requests/${held.id}/deny` })).statusCode).toBe(200);
    const r = await pending;
    expect(r.statusCode).toBe(403);
    expect(r.json()).toMatchObject({ decision: "refused", reason: "denied_on_device" });
    expect(await requests()).toMatchObject([{ status: "refused", reason: "denied_on_device" }]);
    expect((await app.inject({ method: "POST", url: `/v1/requests/${held.id}/deny` })).statusCode).toBe(409);
    expect((await app.inject({ method: "POST", url: `/v1/requests/nope/device-tap` })).statusCode).toBe(404);
  });

  it("hold → timeout → 408 hold_timeout", async () => {
    const policy = (await app.inject({ method: "GET", url: "/v1/policy" })).json<Policy>();
    await app.inject({ method: "PUT", url: "/v1/policy", headers: AUTH, payload: { ...policy, holdTimeoutSeconds: 1 } });
    const r = await pay(body("200000"));
    expect(r.statusCode).toBe(408);
    expect(r.json()).toMatchObject({ decision: "expired", reason: "hold_timeout" });
    expect(await requests()).toMatchObject([{ status: "expired", reason: "hold_timeout" }]);
  });

  it("hold with no device → 503 device_unavailable and a refused row", async () => {
    dev.connected = false;
    const r = await pay(body("200000"));
    expect(r.statusCode).toBe(503);
    expect(r.json()).toMatchObject({ reason: "device_unavailable" });
    expect(await requests()).toMatchObject([{ status: "refused", reason: "device_unavailable" }]);
  });

  it("a second hold queues behind the first: one device action at a time", async () => {
    const first = pay(body("200000"));
    const second = pay(body("300000"));
    await sleep(100);
    expect(dev.signed).toHaveLength(1);
    const rows = await requests();
    expect(rows.filter((r) => r.status === "held")).toHaveLength(2);
    const [b, a] = rows; // newest first
    await app.inject({ method: "POST", url: `/v1/requests/${b.id}/device-tap` }); // tap queued one first: waits its turn
    await app.inject({ method: "POST", url: `/v1/requests/${a.id}/device-tap` });
    expect((await first).statusCode).toBe(200);
    expect((await second).statusCode).toBe(200);
    expect(dev.maxConcurrent).toBe(1);
    expect(dev.signed).toHaveLength(2);
  });

  it("refuses over the daily budget, counting approved and auto", async () => {
    const policy = (await app.inject({ method: "GET", url: "/v1/policy" })).json<Policy>();
    await app.inject({ method: "PUT", url: "/v1/policy", headers: AUTH, payload: { ...policy, dailyBudgetDrops: "51000" } });
    expect((await pay(body("50000"))).statusCode).toBe(200);
    expect((await pay(body("1000"))).statusCode).toBe(200);
    const r = await pay(body("1"));
    expect(r.statusCode).toBe(403);
    expect(r.json().reason).toBe("daily_budget_exceeded");
  });

  it("PUT /v1/policy validates, persists, and applies immediately", async () => {
    expect((await app.inject({ method: "PUT", url: "/v1/policy", headers: AUTH, payload: { perTxCapDrops: 5 } })).statusCode).toBe(400);
    const policy = (await app.inject({ method: "GET", url: "/v1/policy" })).json<Policy>();
    const next = { ...policy, perTxCapDrops: "500" };
    expect((await app.inject({ method: "PUT", url: "/v1/policy", headers: AUTH, payload: next })).json()).toEqual(next);
    // GET's runtime-filled hot issuer is echoed back but not pinned into the file.
    const { credentialIssuer: _issuer, ...saved } = next;
    expect(JSON.parse(readFileSync(join(dir, "policy.json"), "utf8"))).toEqual(saved);
    dev.connected = false;
    expect((await pay(body("1000"))).statusCode).toBe(503); // 1000 > 500 now holds
  });

  it("GET /v1/status", async () => {
    expect((await app.inject({ method: "GET", url: "/v1/status" })).json()).toEqual({
      hotAccount: hot.address, hotBalanceDrops: "98000000", deviceAccount: DEVICE_ADDR, deviceBalanceDrops: "98000000",
      deviceConnected: true, deviceApp: "XRP 2.8.1", spentTodayDrops: "0", pending: 0,
    });
  });

  it("CORS allows the dashboard origins only", async () => {
    const ok = await app.inject({ method: "GET", url: "/health", headers: { origin: "http://localhost:5174" } });
    expect(ok.headers["access-control-allow-origin"]).toBe("http://localhost:5174");
    const other = await app.inject({ method: "GET", url: "/health", headers: { origin: "http://evil.test" } });
    expect(other.headers["access-control-allow-origin"]).toBeUndefined();
  });

  it("CORS lets the lending UI (:5175) preflight POST /v1/lend/approve", async () => {
    const preflight = (origin: string) =>
      app.inject({ method: "OPTIONS", url: "/v1/lend/approve", headers: { origin, "access-control-request-method": "POST" } });
    for (const origin of ["http://localhost:5175", "http://127.0.0.1:5175"]) {
      expect((await preflight(origin)).headers["access-control-allow-origin"]).toBe(origin);
    }
    expect((await preflight("http://localhost:9999")).headers["access-control-allow-origin"]).toBeUndefined();
  });
});

describe("on-ledger allowlist (rule 3)", () => {
  const VETTED = Wallet.fromSeed(testSeed(2, ECDSA.ed25519)).classicAddress;
  const nowRipple = () => Math.floor(Date.now() / 1000) - RIPPLE_EPOCH_OFFSET;

  afterEach(() => vi.useRealTimers());

  it("a static override passes without a ledger lookup", async () => {
    expect((await pay(body("1000"))).statusCode).toBe(200);
    expect(rpc.lookups).toBe(0);
  });

  it("no lookup when an earlier rule refuses", async () => {
    const r = await pay({ ...body("1000", VETTED), requirements: { ...body("1000", VETTED).requirements, network: "xrpl:0" } });
    expect(r.json().reason).toBe("network_not_allowed");
    expect(rpc.lookups).toBe(0);
  });

  it("an accepted credential from the hot account passes", async () => {
    rpc.vet(VETTED, hot.address);
    const r = await pay(body("1000", VETTED));
    expect(r.statusCode).toBe(200);
    expect(r.json()).toMatchObject({ decision: "auto" });
    expect(rpc.lookups).toBe(1);
  });

  it("refuses a credential not yet accepted, one from another issuer, or of another type", async () => {
    rpc.vet(VETTED, hot.address, { Flags: 0 });
    expect((await pay(body("1000", VETTED))).json()).toMatchObject({ decision: "refused", reason: "merchant_not_credentialed" });
    const other = Wallet.generate();
    rpc.entries = [];
    rpc.vet(other.classicAddress, MERCHANT);
    rpc.vet(other.classicAddress, hot.address, { CredentialType: credentialTypeHex("something-else") });
    expect((await pay(body("1000", other.classicAddress))).json()).toMatchObject({ reason: "merchant_not_credentialed" });
  });

  it("refuses an expired credential, passes one expiring later", async () => {
    rpc.vet(VETTED, hot.address, { Expiration: nowRipple() - 10 });
    expect((await pay(body("1000", VETTED))).json()).toMatchObject({ reason: "merchant_not_credentialed" });
    const later = Wallet.generate().classicAddress;
    rpc.vet(later, hot.address, { Expiration: nowRipple() + 3600 });
    expect((await pay(body("1000", later))).statusCode).toBe(200);
  });

  it("fails closed on an RPC error and does not cache it", async () => {
    rpc.vet(VETTED, hot.address);
    rpc.fail = true;
    const r = await pay(body("1000", VETTED));
    expect(r.statusCode).toBe(403);
    expect(r.json().reason).toBe("merchant_not_credentialed");
    rpc.fail = false;
    expect((await pay(body("1000", VETTED))).statusCode).toBe(200);
    expect(rpc.lookups).toBe(2);
  });

  it("caches the lookup per merchant for 30 s", async () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    rpc.vet(VETTED, hot.address);
    expect((await pay(body("1000", VETTED))).statusCode).toBe(200);
    rpc.entries = []; // revoked behind the wallet's back
    vi.setSystemTime(Date.now() + 29_000);
    expect((await pay(body("1000", VETTED))).statusCode).toBe(200);
    expect(rpc.lookups).toBe(1);
    vi.setSystemTime(Date.now() + 1_001);
    expect((await pay(body("1000", VETTED))).json().reason).toBe("merchant_not_credentialed");
    expect(rpc.lookups).toBe(2);
  });

  it("the cache is keyed by issuer and type too", async () => {
    rpc.vet(VETTED, hot.address);
    expect((await pay(body("1000", VETTED))).statusCode).toBe(200);
    const policy = (await app.inject({ method: "GET", url: "/v1/policy" })).json<Policy>();
    await app.inject({ method: "PUT", url: "/v1/policy", headers: AUTH, payload: { ...policy, credentialType: "other" } });
    expect((await pay(body("1000", VETTED))).json().reason).toBe("merchant_not_credentialed");
    expect(rpc.lookups).toBe(2);
  });

  it("DELETE /v1/merchants/:address revokes and clears that merchant's cache entry", async () => {
    rpc.vet(VETTED, hot.address);
    expect((await pay(body("1000", VETTED))).statusCode).toBe(200);
    const r = await app.inject({ method: "DELETE", url: `/v1/merchants/${VETTED}`, headers: AUTH });
    expect(r.statusCode).toBe(200);
    expect(r.json()).toEqual({ txHash: "B".repeat(64) });
    expect(rpc.submits.at(-1)).toEqual({ TransactionType: "CredentialDelete", Account: hot.address, Subject: VETTED, CredentialType: credentialTypeHex("x402-merchant") });
    expect((await pay(body("1000", VETTED))).json().reason).toBe("merchant_not_credentialed");
    expect(rpc.lookups).toBe(2);
  });
});

describe("merchant routes", () => {
  const SUBJECT = Wallet.fromSeed(testSeed(2, ECDSA.ed25519)).classicAddress;
  const vet = (address: unknown) => app.inject({ method: "POST", url: "/v1/merchants", headers: AUTH, payload: { address } as object });

  it("GET /v1/policy fills credentialIssuer with the hot account and the default type", async () => {
    expect((await app.inject({ method: "GET", url: "/v1/policy" })).json()).toMatchObject({ credentialIssuer: hot.address, credentialType: "x402-merchant" });
  });

  it("PUT /v1/policy accepts a policy without the credential fields", async () => {
    const { credentialIssuer: _i, credentialType: _t, ...old } = (await app.inject({ method: "GET", url: "/v1/policy" })).json<Policy>();
    const r = await app.inject({ method: "PUT", url: "/v1/policy", headers: AUTH, payload: old });
    expect(r.statusCode).toBe(200);
    expect(r.json()).toMatchObject({ credentialIssuer: hot.address, credentialType: "x402-merchant" });
    expect(JSON.parse(readFileSync(join(dir, "policy.json"), "utf8")).credentialIssuer).toBeUndefined();
    expect((await app.inject({ method: "PUT", url: "/v1/policy", headers: AUTH, payload: { ...old, credentialIssuer: "nope" } })).statusCode).toBe(400);
  });

  it("POST /v1/merchants issues a CredentialCreate from the hot account", async () => {
    const r = await vet(SUBJECT);
    expect(r.statusCode).toBe(200);
    expect(r.json()).toEqual({ txHash: "B".repeat(64) });
    expect(rpc.submits).toEqual([{ TransactionType: "CredentialCreate", Account: hot.address, Subject: SUBJECT, CredentialType: credentialTypeHex("x402-merchant") }]);
    expect(credentialTypeHex("x402-merchant")).toBe("783430322D6D65726368616E74");
  });

  it("POST /v1/domain creates the Permissioned Domain from the vet credential, then updates it in place", async () => {
    expect((await app.inject({ method: "GET", url: "/v1/domain" })).json()).toEqual({ domain: null });
    const accepted = [{ Credential: { Issuer: hot.address, CredentialType: credentialTypeHex("x402-merchant") } }];
    const created = await app.inject({ method: "POST", url: "/v1/domain", headers: AUTH });
    expect(created.statusCode).toBe(200);
    const domain = { domainId: "0".repeat(63) + "1", owner: hot.address, acceptedCredentials: [{ issuer: hot.address, credentialType: "x402-merchant" }], txHash: "B".repeat(64) };
    expect(created.json()).toEqual({ txHash: "B".repeat(64), domain });
    expect(rpc.submits).toEqual([{ TransactionType: "PermissionedDomainSet", Account: hot.address, AcceptedCredentials: accepted }]);
    expect((await app.inject({ method: "GET", url: "/v1/domain" })).json()).toEqual({ domain });
    // A second POST updates the same domain rather than creating another.
    expect((await app.inject({ method: "POST", url: "/v1/domain", headers: AUTH })).statusCode).toBe(200);
    expect(rpc.submits[1]).toEqual({ TransactionType: "PermissionedDomainSet", Account: hot.address, DomainID: domain.domainId, AcceptedCredentials: accepted });
    expect(rpc.domainList).toHaveLength(1);
  });

  it("domain routes: engine failure, rpc failure", async () => {
    rpc.result = "tecINSUFFICIENT_RESERVE";
    expect((await app.inject({ method: "POST", url: "/v1/domain", headers: AUTH })).json()).toEqual({ reason: "tecINSUFFICIENT_RESERVE", txHash: "C".repeat(64) });
    rpc.result = null;
    rpc.fail = true;
    expect((await app.inject({ method: "POST", url: "/v1/domain", headers: AUTH })).statusCode).toBe(502);
    expect((await app.inject({ method: "GET", url: "/v1/domain" })).statusCode).toBe(502);
  });

  it("POST /v1/merchants error paths", async () => {
    expect((await vet("rNotAnAddress")).json()).toEqual({ reason: "bad_address" });
    expect((await vet(undefined)).statusCode).toBe(400);
    await vet(SUBJECT);
    const dup = await vet(SUBJECT);
    expect(dup.statusCode).toBe(409);
    expect(dup.json()).toMatchObject({ reason: "tecDUPLICATE" });
    rpc.result = "temMALFORMED";
    expect((await vet(SUBJECT)).statusCode).toBe(400);
    rpc.result = "tecINSUFFICIENT_RESERVE";
    expect((await vet(SUBJECT)).statusCode).toBe(500);
    rpc.result = null;
    rpc.fail = true;
    const down = await vet(SUBJECT);
    expect(down.statusCode).toBe(502);
    expect(down.json()).toEqual({ reason: "rpc_error" });
  });

  it("POST/DELETE refuse when the issuer is not the hot account", async () => {
    const policy = (await app.inject({ method: "GET", url: "/v1/policy" })).json<Policy>();
    await app.inject({ method: "PUT", url: "/v1/policy", headers: AUTH, payload: { ...policy, credentialIssuer: MERCHANT } });
    expect((await vet(SUBJECT)).json()).toEqual({ reason: "issuer_not_hot_account" });
    const del = await app.inject({ method: "DELETE", url: `/v1/merchants/${SUBJECT}`, headers: AUTH });
    expect(del.statusCode).toBe(400);
    expect(del.json()).toEqual({ reason: "issuer_not_hot_account" });
    expect(rpc.submits).toHaveLength(0);
  });

  it("DELETE /v1/merchants/:address error paths", async () => {
    const missing = await app.inject({ method: "DELETE", url: `/v1/merchants/${SUBJECT}`, headers: AUTH });
    expect(missing.statusCode).toBe(404);
    expect(missing.json()).toMatchObject({ reason: "tecNO_ENTRY" });
    expect((await app.inject({ method: "DELETE", headers: AUTH, url: "/v1/merchants/rNope" })).statusCode).toBe(400);
  });

  it("GET /v1/merchants lists the issuer's credentials of the policy type, across pages", async () => {
    const other = Wallet.generate().classicAddress;
    rpc.vet(SUBJECT, hot.address);
    rpc.vet(other, hot.address, { Flags: 0, PreviousTxnID: "9".repeat(64) });
    rpc.vet(Wallet.generate().classicAddress, hot.address, { CredentialType: credentialTypeHex("other") });
    rpc.vet(hot.address, MERCHANT); // received by the hot account, not issued
    const r = await app.inject({ method: "GET", url: "/v1/merchants" });
    expect(r.statusCode).toBe(200);
    expect(r.json()).toEqual([
      { address: SUBJECT, accepted: true, txHash: "F".repeat(64) },
      { address: other, accepted: false, txHash: "9".repeat(64) },
    ]);
  });

  it("CORS allows DELETE from the dashboard", async () => {
    const r = await app.inject({
      method: "OPTIONS", url: `/v1/merchants/${SUBJECT}`,
      headers: { origin: "http://localhost:5174", "access-control-request-method": "DELETE" },
    });
    expect(r.headers["access-control-allow-origin"]).toBe("http://localhost:5174");
    expect(String(r.headers["access-control-allow-methods"])).toContain("DELETE");
  });
});

describe("pre-v1.4 runtime policy file", () => {
  it("boots and fills the credential defaults", async () => {
    const d = mkdtempSync(join(tmpdir(), "pw-old-"));
    const old = { perTxCapDrops: "100000", dailyBudgetDrops: "100000000", allowedMerchants: [MERCHANT], allowedNetworks: ["xrpl:1"], allowedAssets: ["XRP"], holdTimeoutSeconds: 90 };
    writeFileSync(join(d, "policy.json"), JSON.stringify(old));
    const a = await buildApp({
      policyPath: join(d, "policy.json"), audit: new Audit(join(d, "requests.jsonl")), hot, ledger, device: dev,
      holds: new HoldQueue(dev, dev, () => {}), balanceDrops: async () => null, credentials: new Credentials(rpc, hot.wallet), treasury, log: () => {}, adminToken: TOKEN,
    });
    expect((await a.inject({ method: "GET", url: "/v1/policy" })).json()).toEqual({ ...old, credentialType: "x402-merchant", credentialIssuer: hot.address });
    await a.close();
  });
});

describe("request parsing", () => {
  it("400 on invalid JSON", async () => {
    const r = await app.inject({ method: "POST", url: "/v1/pay", headers: { "content-type": "application/json" }, payload: "{nope" });
    expect(r.statusCode).toBe(400);
  });
});

describe("delegation (amended)", () => {
  const delegate = (action: unknown) => app.inject({ method: "POST", url: "/v1/delegate", headers: AUTH, payload: { action } as object });
  const tapHeld = async () => {
    const held = await waitForHeld();
    await app.inject({ method: "POST", url: `/v1/requests/${held.id}/device-tap` });
    return held;
  };
  const treasuryPay = (amount: string) => pay({ ...body(amount), source: "treasury", requirements: { ...body(amount).requirements, maxTimeoutSeconds: 10 } });

  it("grant: a held device-signed DelegateSet, then GET shows Payment", async () => {
    const pending = delegate("grant");
    const held = await tapHeld();
    expect(held).toMatchObject({ status: "held" });
    const r = await pending;
    expect(r.statusCode).toBe(200);
    expect(r.json()).toMatchObject({ action: "grant", engineResult: "tesSUCCESS", permissions: ["Payment"] });
    const tx = decode(dev.signed[0]) as Record<string, unknown>;
    expect(tx).toMatchObject({ TransactionType: "DelegateSet", Account: DEVICE_ADDR, Authorize: hot.address, SigningPubKey: DEVICE_PUB });
    expect(tx.LastLedgerSequence).toBe(1000 + 30 + 10); // outlives a 90 s hold
    expect((await requests())[0]).toMatchObject({ status: "approved", signer: "device", kind: "delegate", source: "treasury", resourceUrl: "delegate://grant", amountDrops: "0" });
    const g = (await app.inject({ method: "GET", url: "/v1/delegate" })).json();
    expect(g).toMatchObject({ treasury: DEVICE_ADDR, agent: hot.address, permissions: ["Payment"] });
  });

  it("treasury auto payment: Account=treasury, Delegate=hot, hot-signed, submitted; LastLedgerSequence validated+4", async () => {
    treasury.entries.push({ Account: DEVICE_ADDR, Authorize: hot.address, Permissions: [{ Permission: { PermissionValue: "Payment" } }] });
    const r = await treasuryPay("1000");
    expect(r.statusCode).toBe(200);
    const j = r.json();
    expect(j).toMatchObject({ decision: "auto", source: "treasury", signer: "hot (delegated)", account: DEVICE_ADDR, engineResult: "tesSUCCESS" });
    expect(treasury.submitted[0]).toMatchObject({ Account: DEVICE_ADDR, Delegate: hot.address, SigningPubKey: hot.wallet.publicKey, LastLedgerSequence: 1004 });
    expect(verifySignature(encode(treasury.submitted[0] as unknown as Payment), hot.wallet.publicKey)).toBe(true);
    expect(j.txHash).toBe(hashes.hashSignedTx(encode(treasury.submitted[0] as unknown as Payment)));
    expect((await requests())[0]).toMatchObject({ status: "auto", signer: "hot (delegated)", source: "treasury", txHash: j.txHash });
    expect((await app.inject({ method: "GET", url: "/v1/status" })).json().spentTodayDrops).toBe("1000");
  });

  it("after a revoke the treasury payment is refused with terNO_DELEGATE_PERMISSION verbatim, no hash, no spend", async () => {
    treasury.entries.push({ Account: DEVICE_ADDR, Authorize: hot.address, Permissions: [{ Permission: { PermissionValue: "Payment" } }] });
    const pending = delegate("revoke");
    await tapHeld();
    expect((await pending).json()).toMatchObject({ action: "revoke", engineResult: "tesSUCCESS", permissions: [] });
    expect((await app.inject({ method: "GET", url: "/v1/delegate" })).json()).toMatchObject({ permissions: [], objects: [] });
    const r = await treasuryPay("1000");
    expect(r.statusCode).toBe(403);
    expect(r.json()).toMatchObject({ decision: "refused", source: "treasury", reason: "terNO_DELEGATE_PERMISSION", engineResult: "terNO_DELEGATE_PERMISSION", txHash: null });
    expect((await requests())[0]).toMatchObject({ status: "refused", reason: "terNO_DELEGATE_PERMISSION", txHash: null, source: "treasury" });
    expect((await app.inject({ method: "GET", url: "/v1/status" })).json().spentTodayDrops).toBe("0");
  });

  it("treasury payments go through the same policy rules (refused before any submit)", async () => {
    const r = await pay({ ...body("1000", "rRogueMerchantXXXXXXXXXXXXXXXXXXX"), source: "treasury" });
    expect(r.statusCode).toBe(403);
    expect(r.json()).toMatchObject({ reason: "merchant_not_credentialed", source: "treasury" });
    expect(treasury.submitted).toHaveLength(0);
  });

  it("a treasury payment over the cap holds for the device, then the wallet submits it", async () => {
    const pending = pay({ ...body("5000000"), source: "treasury" });
    await tapHeld();
    const r = await pending;
    expect(r.json()).toMatchObject({ decision: "approved", source: "treasury", signer: "device", account: DEVICE_ADDR, engineResult: "tesSUCCESS" });
    expect(treasury.submitted[0]).toMatchObject({ Account: DEVICE_ADDR, TxnSignature: FAKE_DER });
    expect(treasury.submitted[0]).not.toHaveProperty("Delegate");
  });

  it("deny on a delegate hold → 403, bad action → 400, RPC down → 502 on GET", async () => {
    const pending = delegate("revoke");
    const held = await waitForHeld();
    await app.inject({ method: "POST", url: `/v1/requests/${held.id}/deny` });
    expect((await pending).statusCode).toBe(403);
    expect(treasury.submitted).toHaveLength(0);
    expect((await delegate("nuke")).statusCode).toBe(400);
    treasury.fail = true;
    expect((await app.inject({ method: "GET", url: "/v1/delegate" })).statusCode).toBe(502);
  });

  it("hot (x402) responses carry no source field", async () => {
    const j = (await pay(body("1000"))).json();
    expect(j).not.toHaveProperty("source");
    expect((await requests())[0]).not.toHaveProperty("source");
  });
});

describe("operator token (X-Wallet-Token)", () => {
  const OPERATOR = [
    { method: "PUT", url: "/v1/policy" },
    { method: "POST", url: "/v1/merchants" },
    { method: "DELETE", url: `/v1/merchants/${MERCHANT}` },
    { method: "POST", url: "/v1/domain" },
    { method: "POST", url: "/v1/delegate" },
  ] as const;

  it("401 on every operator route without the header or with a wrong one; nothing changes", async () => {
    const before = (await app.inject({ method: "GET", url: "/v1/policy" })).json();
    for (const r of OPERATOR) {
      for (const headers of [{}, { "x-wallet-token": "wrong" }]) {
        const res = await app.inject({ ...r, headers, payload: { action: "grant", address: MERCHANT } });
        expect(res.statusCode, `${r.method} ${r.url}`).toBe(401);
        expect(res.json()).toEqual({ reason: "bad_operator_token" });
      }
    }
    expect((await app.inject({ method: "GET", url: "/v1/policy" })).json()).toEqual(before);
    expect(treasury.submitted).toHaveLength(0);
    expect(rpc.submits).toHaveLength(0);
  });

  it("200 with the right header", async () => {
    const policy = (await app.inject({ method: "GET", url: "/v1/policy" })).json<Policy>();
    const r = await app.inject({ method: "PUT", url: "/v1/policy", headers: AUTH, payload: { ...policy, perTxCapDrops: "500" } });
    expect(r.statusCode).toBe(200);
    expect(r.json().perTxCapDrops).toBe("500");
  });

  it("503 operator_token_unset on operator routes when WALLET_ADMIN_TOKEN is not set; reads and payments still work", async () => {
    const d = mkdtempSync(join(tmpdir(), "pw-api-"));
    copyFileSync(new URL("../policy.json", import.meta.url), join(d, "policy.json"));
    const a = await buildApp({
      policyPath: join(d, "policy.json"), audit: new Audit(join(d, "requests.jsonl")), hot, ledger, device: dev,
      holds: new HoldQueue(dev, dev, () => {}), balanceDrops: async () => null, credentials: new Credentials(rpc, hot.wallet), treasury, log: () => {},
    });
    for (const r of OPERATOR) {
      const res = await a.inject({ ...r, headers: AUTH, payload: { action: "grant", address: MERCHANT } });
      expect(res.statusCode, `${r.method} ${r.url}`).toBe(503);
      expect(res.json()).toEqual({ reason: "operator_token_unset" });
    }
    expect((await a.inject({ method: "GET", url: "/v1/policy" })).statusCode).toBe(200);
    expect((await a.inject({ method: "POST", url: "/v1/pay", payload: body("1000", "rRogueMerchantXXXXXXXXXXXXXXXXXXX") })).statusCode).toBe(403);
    await a.close();
  });

  it("CORS preflight from the dashboard allows the X-Wallet-Token header", async () => {
    const r = await app.inject({
      method: "OPTIONS", url: "/v1/policy",
      headers: { origin: "http://localhost:5174", "access-control-request-method": "PUT", "access-control-request-headers": "content-type,x-wallet-token" },
    });
    expect(r.headers["access-control-allow-origin"]).toBe("http://localhost:5174");
    expect(String(r.headers["access-control-allow-headers"]).toLowerCase()).toContain("x-wallet-token");
  });
});

describe("policy hash and expiry (contract v1.6)", () => {
  const fileHash = () => createHash("sha256").update(readFileSync(join(dir, "policy.json"))).digest("hex").toUpperCase();
  const rows = async () => (await app.inject({ method: "GET", url: "/v1/requests" })).json<{ id: string; status: string; reason: string | null; policyHash?: string }[]>();

  it("every request row records the sha256 of policy.json it was decided under", async () => {
    const first = fileHash();
    const auto = (await pay(body("1000"))).json().requestId;
    const refused = (await pay(body("1000", "rRogueMerchantXXXXXXXXXXXXXXXXXXX"))).json().requestId;
    const pending = pay(body("5000000"));
    const held = await waitForHeld();
    await app.inject({ method: "POST", url: `/v1/requests/${held.id}/device-tap` });
    await pending;
    for (const id of [auto, refused, held.id]) expect((await rows()).find((r) => r.id === id)?.policyHash).toBe(first);

    const policy = (await app.inject({ method: "GET", url: "/v1/policy" })).json<Policy>();
    await app.inject({ method: "PUT", url: "/v1/policy", headers: AUTH, payload: { ...policy, perTxCapDrops: "500" } });
    const second = fileHash();
    expect(second).not.toBe(first);
    const later = (await pay(body("100"))).json().requestId;
    expect((await rows()).find((r) => r.id === later)?.policyHash).toBe(second);
    expect((await rows()).find((r) => r.id === auto)?.policyHash).toBe(first);
  });

  it("a policy past expiresAt refuses every payment with policy_expired; a renewed one pays again", async () => {
    const policy = (await app.inject({ method: "GET", url: "/v1/policy" })).json<Policy>();
    expect((await app.inject({ method: "PUT", url: "/v1/policy", headers: AUTH, payload: { ...policy, expiresAt: "soon" } })).statusCode).toBe(400);
    await app.inject({ method: "PUT", url: "/v1/policy", headers: AUTH, payload: { ...policy, expiresAt: "2026-01-01T00:00:00Z" } });
    for (const amount of ["1000", "5000000"]) {
      const r = await pay(body(amount));
      expect(r.statusCode).toBe(403);
      expect(r.json()).toMatchObject({ decision: "refused", reason: "policy_expired" });
    }
    expect((await rows()).slice(0, 2).map((r) => r.reason)).toEqual(["policy_expired", "policy_expired"]);
    await app.inject({ method: "PUT", url: "/v1/policy", headers: AUTH, payload: { ...policy, expiresAt: "2099-01-01T00:00:00Z" } });
    expect((await pay(body("1000"))).json()).toMatchObject({ decision: "auto" });
  });
});

describe("preview on audit rows (contract v1.5)", () => {
  it("auto and held rows carry the describe() card; the treasury is named", async () => {
    await pay(body("1000"));
    const pending = pay(body("5000000"));
    const held = await waitForHeld();
    const rows = (await app.inject({ method: "GET", url: "/v1/requests" })).json<{ id: string; preview?: { title: string; summary: string; lines: { label: string; value: string }[] } }[]>();
    expect(rows.find((r) => r.id === held.id)?.preview?.title).toBe("Pay 5 XRP to rPT1Sj…pAYe");
    expect(rows.find((r) => r.id === held.id)?.preview?.lines.find((l) => l.label === "From")?.value).toBe("treasury (Ledger) (rUGeRs…VQ6B)");
    expect(rows.find((r) => r.id !== held.id)?.preview?.summary).toMatch(/^Send 0\.001 XRP from agent \(hot key\)/);
    await app.inject({ method: "POST", url: `/v1/requests/${held.id}/device-tap` });
    await pending;
  });
});

describe("GET /v1/accounts (control tower)", () => {
  it("returns addresses and roles only, never other fields from the files", async () => {
    const d = mkdtempSync(join(tmpdir(), "pw-acct-"));
    writeFileSync(join(d, "merchants.json"), JSON.stringify({ good: { address: MERCHANT, port: 8001, seed: "sSECRETSEED" } }));
    writeFileSync(join(d, "accounts.json"), JSON.stringify({
      network: "devnet", accounts: { broker: "rEH59tesggzmgg42PeHvByQQ3kmUNhegVw", borrower: "rBU5c38YumSZQAkxtPNwbgq6W6TzLM6Wbe", supplier: "r3ojz3wRg78u5mEhsaWHZxHVPgMV6SiYai", brokerSeed: "sSECRETSEED" },
      vaultId: "A".repeat(64), loanBrokerId: "nothex", history: { customers: ["rj8T8oCRnwzFhTcPxd9dA9JAyaXV6kjWH"] },
    }));
    const a = await buildApp({
      policyPath: join(dir, "policy.json"), audit: new Audit(join(d, "requests.jsonl")), hot, ledger, device: dev,
      holds: new HoldQueue(dev, dev, () => {}), balanceDrops: async () => null, credentials: new Credentials(rpc, hot.wallet), treasury, log: () => {}, adminToken: TOKEN,
      accountFiles: { merchants: join(d, "merchants.json"), lending: join(d, "accounts.json") },
    });
    const r = await a.inject({ method: "GET", url: "/v1/accounts" });
    expect(r.body).not.toContain("SECRET");
    expect(r.json()).toEqual({
      testnet: [
        { address: hot.address, name: "agent (hot key)", role: "agent" },
        { address: DEVICE_ADDR, name: "treasury (Ledger)", role: "treasury" },
        { address: MERCHANT, name: "good merchant", role: "merchant" },
      ],
      devnet: [
        { address: "rEH59tesggzmgg42PeHvByQQ3kmUNhegVw", name: "broker", role: "broker" },
        { address: "rBU5c38YumSZQAkxtPNwbgq6W6TzLM6Wbe", name: "borrower", role: "borrower" },
        { address: "r3ojz3wRg78u5mEhsaWHZxHVPgMV6SiYai", name: "supplier", role: "supplier" },
        { address: "rj8T8oCRnwzFhTcPxd9dA9JAyaXV6kjWH", name: "customer 1", role: "customer" },
      ],
      devnetObjects: { vaultId: "A".repeat(64), loanBrokerId: null },
    });
    await a.close();
  });
});

describe("held-loan approval (DX finding 12: the device signs an approval Payment, never the LoanSet)", () => {
  const LOAN_SET_HASH = "ab".repeat(32);
  const approve = (loanSetHash: unknown) => app.inject({ method: "POST", url: "/v1/lend/approve", payload: { loanSetHash } as object });

  it("holds for the device tap, then submits a 1-drop treasury Payment whose Memo carries the LoanSet hash", async () => {
    const pending = approve(LOAN_SET_HASH);
    const held = await waitForHeld();
    expect(held).toMatchObject({ status: "held", kind: "lend", source: "treasury", amountDrops: "1" });
    await app.inject({ method: "POST", url: `/v1/requests/${held.id}/device-tap` });
    const r = await pending;
    expect(r.statusCode).toBe(200);
    const signed = decode(dev.signed[0]) as Record<string, unknown>;
    expect(signed).toMatchObject({
      TransactionType: "Payment", Account: DEVICE_ADDR, Destination: hot.address, Amount: "1", SigningPubKey: DEVICE_PUB,
      Memos: [{ Memo: { MemoType: Buffer.from("loan-approval").toString("hex").toUpperCase(), MemoData: LOAN_SET_HASH.toUpperCase() } }],
    });
    expect(r.json()).toMatchObject({ requestId: held.id, loanSetHash: LOAN_SET_HASH.toUpperCase(), engineResult: "tesSUCCESS", account: DEVICE_ADDR });
    expect(r.json().txHash).toMatch(/^[0-9A-F]{64}$/);
    expect(treasury.submitted).toHaveLength(1);
    expect((await requests())[0]).toMatchObject({ status: "approved", signer: "device", txHash: r.json().txHash });
  });

  it("with the LoanSet blob: checks sha256(blob) == loanSetHash and puts the loan card on the held row", async () => {
    const { tx_json } = JSON.parse(readFileSync(new URL("../../preview/test/fixtures/devnet/LoanSet-135D0B68.json", import.meta.url), "utf8"));
    const blob = encode(tx_json);
    const hash = createHash("sha256").update(Buffer.from(blob, "hex")).digest("hex").toUpperCase();
    const mismatch = await app.inject({ method: "POST", url: "/v1/lend/approve", payload: { loanSetHash: LOAN_SET_HASH, loanSetBlob: blob } });
    expect(mismatch.json()).toEqual({ reason: "loan_set_hash_mismatch" });
    const pending = app.inject({ method: "POST", url: "/v1/lend/approve", payload: { loanSetHash: hash, loanSetBlob: blob } });
    const held = await waitForHeld();
    const row = (await app.inject({ method: "GET", url: "/v1/requests" })).json<{ id: string; loanPreview?: { summary: string } }[]>().find((r) => r.id === held.id);
    expect(row?.loanPreview?.summary).toBe("Loan of 60000000 (60 XRP if the vault holds XRP): 3 payments every 90 seconds at 8% interest");
    await app.inject({ method: "POST", url: `/v1/requests/${held.id}/deny` });
    expect((await pending).statusCode).toBe(403);
  });

  it("loan-terms text comes from the decoded LoanSet only (contract v1.7)", () => {
    const { tx_json } = JSON.parse(readFileSync(new URL("../../preview/test/fixtures/devnet/LoanSet-135D0B68.json", import.meta.url), "utf8"));
    expect(loanTermsText(decode(encode(tx_json)))).toBe("approve loan 60 XRP to rBU5c38YumSZQAkxtPNwbgq6W6TzLM6Wbe 3 payments");
    // Large principals decode in exponent form; fractional drops or a missing PaymentTotal have no defined text.
    for (const [PrincipalRequested, xrp] of [["100000000000", "100000"], ["150000000000", "150000"], ["123456789012", "123456.789012"], ["1500000", "1.5"]]) {
      expect(loanTermsText(decode(encode({ ...tx_json, PrincipalRequested })))).toBe(`approve loan ${xrp} XRP to rBU5c38YumSZQAkxtPNwbgq6W6TzLM6Wbe 3 payments`);
    }
    expect(loanTermsText({ ...tx_json, PrincipalRequested: "1.5" })).toBeNull();
    const { PaymentTotal: _pt, ...noTotal } = tx_json;
    expect(loanTermsText(decode(encode(noTotal)))).toBeNull();
  });

  it("400 bad_loan_terms for a LoanSet blob without PaymentTotal; nothing is held", async () => {
    const { tx_json } = JSON.parse(readFileSync(new URL("../../preview/test/fixtures/devnet/LoanSet-135D0B68.json", import.meta.url), "utf8"));
    const { PaymentTotal: _pt, ...noTotal } = tx_json;
    const blob = encode(noTotal);
    const hash = createHash("sha256").update(Buffer.from(blob, "hex")).digest("hex").toUpperCase();
    const r = await app.inject({ method: "POST", url: "/v1/lend/approve", payload: { loanSetHash: hash, loanSetBlob: blob } });
    expect(r.statusCode).toBe(400);
    expect(r.json()).toEqual({ reason: "bad_loan_terms" });
    expect(await requests()).toHaveLength(0);
  });

  it("with the LoanSet blob: the device signs a second, ASCII loan-terms Memo after the loan-approval hash Memo", async () => {
    const { tx_json } = JSON.parse(readFileSync(new URL("../../preview/test/fixtures/devnet/LoanSet-135D0B68.json", import.meta.url), "utf8"));
    const blob = encode(tx_json);
    const hash = createHash("sha256").update(Buffer.from(blob, "hex")).digest("hex").toUpperCase();
    // Request fields other than the blob cannot change the text.
    const pending = app.inject({ method: "POST", url: "/v1/lend/approve", payload: { loanSetHash: hash, loanSetBlob: blob, terms: "approve loan 1 XRP" } });
    const held = await waitForHeld();
    await app.inject({ method: "POST", url: `/v1/requests/${held.id}/device-tap` });
    expect((await pending).statusCode).toBe(200);
    const hex = (t: string) => Buffer.from(t, "ascii").toString("hex").toUpperCase();
    expect((decode(dev.signed[0]) as { Memos: unknown }).Memos).toEqual([
      { Memo: { MemoType: hex("loan-approval"), MemoData: hash } },
      { Memo: { MemoType: hex("loan-terms"), MemoData: hex("approve loan 60 XRP to rBU5c38YumSZQAkxtPNwbgq6W6TzLM6Wbe 3 payments") } },
    ]);
  });

  it("rejects a malformed hash and reports a device denial", async () => {
    expect((await approve("nothex")).json()).toEqual({ reason: "bad_loan_set_hash" });
    const pending = approve(LOAN_SET_HASH);
    const held = await waitForHeld();
    await app.inject({ method: "POST", url: `/v1/requests/${held.id}/deny` });
    const r = await pending;
    expect(r.statusCode).toBe(403);
    expect(r.json()).toMatchObject({ reason: "denied_on_device" });
    expect(treasury.submitted).toHaveLength(0);
  });
});
