import { createHash, randomUUID, timingSafeEqual } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import cors from "@fastify/cors";
import Fastify, { type FastifyInstance, type FastifyReply, type FastifyRequest } from "fastify";
import { decode, isValidClassicAddress } from "xrpl";
import { Audit } from "./audit.js";
import { clientCredentialRpc, Credentials, type Submitted } from "./credentials.js";
import { LedgerDevice, type DeviceSigner } from "./device.js";
import { HoldQueue, type HoldOutcome } from "./hold.js";
import { HotKey } from "./hot.js";
import { buildPayment, clientLedger, PaymentError, type Ledger } from "./payment.js";
import { decide, loadPolicy, needsCredentialLookup, policyFileHash, savePolicy } from "./policy.js";
import { drainSpeculosResponses, Speculos } from "./speculos.js";
import { clientTreasury, delegateSet, permissionsFor, type DirectResult, type TreasuryLedger } from "./treasury.js";
import { PayBodySchema, PolicySchema, type Policy, type RequestRow, type SignedTx, type Signer } from "./types.js";
import { XrplConnection } from "./xrpl.js";
import { describe, type Tx } from "../../preview/src/index.js";

export type Deps = {
  policyPath: string;
  audit: Audit;
  hot: HotKey;
  ledger: Ledger;
  /** XRP balance in drops, or null if the account does not exist / RPC failed. */
  balanceDrops: (address: string) => Promise<string | null>;
  device: DeviceSigner;
  holds: HoldQueue;
  /** Rule 3's ledger lookup and the vet/revoke transactions, issued by the hot account. */
  credentials: Credentials;
  /** Direct submits and Delegate lookups for the treasury (the Ledger account). */
  treasury: TreasuryLedger;
  log?: (msg: string) => void;
  /** Control tower: agent/merchants.json and lending/accounts.json. Read for addresses only. */
  accountFiles?: { merchants?: string; lending?: string };
  /** WALLET_ADMIN_TOKEN: operator routes need it in X-Wallet-Token. Unset = those routes answer 503. */
  adminToken?: string;
};

export type Config = {
  hotSeed: string;
  speculosUrl: string;
  xrplWss: string;
  policyPath: string;
  auditPath: string;
  log?: (msg: string) => void;
};

/** Wires the real testnet client, hot key, Ledger device, and Speculos driver. */
export function createDeps(config: Config): Deps & { xrpl: XrplConnection } {
  const log = config.log ?? console.log;
  const xrpl = new XrplConnection(config.xrplWss, log);
  xrpl.watchdog();
  const ledger: Ledger = {
    validatedLedgerIndex: () => xrpl.read((c) => clientLedger(c).validatedLedgerIndex()),
    networkId: () => xrpl.read((c) => clientLedger(c).networkId()),
    autofill: (tx) => xrpl.read((c) => clientLedger(c).autofill(tx)),
  };
  const balanceDrops = async (address: string) => {
    try {
      const r = await xrpl.read((c) => c.request({ command: "account_info", account: address, ledger_index: "validated" }));
      return r.result.account_data.Balance;
    } catch {
      return null;
    }
  };
  drainSpeculosResponses(config.speculosUrl);
  const speculos = new Speculos(config.speculosUrl);
  const device = new LedgerDevice(config.speculosUrl, log);
  // A review left on screen by a previous process answers every APDU with 6901 and confuses the
  // DMK session, so reject it before the DMK connects.
  void (async () => {
    try {
      if (await speculos.waitForReview(500)) {
        log("stale review on the device at boot: rejecting it before connecting");
        await speculos.reject((msg) => log(`boot cleanup: ${msg}`));
        await new Promise((r) => setTimeout(r, 1500));
      }
    } catch {
      // Speculos down: the device retry loop handles it.
    }
    device.start();
  })();
  // Keep the Speculos event history (polled every few seconds by the DMK) small.
  setInterval(() => void speculos.clearEvents().catch(() => {}), 30_000).unref();
  const hot = new HotKey(config.hotSeed);
  return {
    xrpl,
    policyPath: config.policyPath,
    audit: new Audit(config.auditPath),
    hot,
    ledger,
    balanceDrops,
    device,
    holds: new HoldQueue(device, speculos, log),
    credentials: new Credentials(clientCredentialRpc(xrpl), hot.wallet),
    treasury: clientTreasury(xrpl),
    log,
  };
}

// Dashboard (:5174), workshop app (:5173), lending UI (:5175, calls POST /v1/lend/approve).
const ALLOWED_ORIGINS = ["http://localhost:5174", "http://localhost:5173", "http://localhost:5175", "http://127.0.0.1:5175"];

// Engine results with a more specific status than 500.
/** MemoType of the held-loan approval Payment; MemoData is the LoanSet hash. */
export const LOAN_APPROVAL_MEMO = "loan-approval";
export const LOAN_TERMS_MEMO = "loan-terms";

/** An STNumber as decoded JSON ("60000000", "1e11", "15e10", "1.5") in whole drops; null when it is not a whole number. */
function wholeDrops(value: unknown): bigint | null {
  const m = /^(\d+)(?:\.(\d+))?(?:e(-?\d+))?$/.exec(String(value));
  if (!m) return null;
  const n = BigInt(m[1] + (m[2] ?? ""));
  const exp = Number(m[3] ?? 0) - (m[2]?.length ?? 0);
  if (exp >= 0) return n * 10n ** BigInt(exp);
  const div = 10n ** BigInt(-exp);
  return n % div === 0n ? n / div : null;
}

/**
 * Contract v1.7: the loan-terms Memo text, from the decoded LoanSet only. ASCII, so the XRP app shows
 * it as text on the review screen. The borrower is the LoanSet's Account (it signs first in the desk's
 * flow); PrincipalRequested is in drops because the desk's vault holds XRP. Null when the terms are not
 * well defined (a fractional principal, or no PaymentTotal).
 */
export function loanTermsText(loanSet: Record<string, unknown>): string | null {
  const drops = wholeDrops(loanSet.PrincipalRequested);
  if (drops === null || typeof loanSet.PaymentTotal !== "number") return null;
  const xrp = `${drops / 1_000_000n}${drops % 1_000_000n ? `.${String(drops % 1_000_000n).padStart(6, "0").replace(/0+$/, "")}` : ""}`;
  return `approve loan ${xrp} XRP to ${loanSet.Account} ${loanSet.PaymentTotal} payments`;
}
const ENGINE_STATUS: Record<string, number> = { tecDUPLICATE: 409, tecNO_ENTRY: 404, tecNO_TARGET: 404 };

export async function buildApp(deps: Deps): Promise<FastifyInstance> {
  const { audit, hot, ledger, device, holds, credentials } = deps;
  const log = deps.log ?? console.log;
  // Operator routes change the policy, the allowlist or the agent's authority: they need X-Wallet-Token.
  const digest = (t: string) => createHash("sha256").update(t).digest();
  const operator = async (request: FastifyRequest, reply: FastifyReply) => {
    if (!deps.adminToken) return reply.code(503).send({ reason: "operator_token_unset" });
    const given = request.headers["x-wallet-token"];
    if (typeof given !== "string" || !timingSafeEqual(digest(given), digest(deps.adminToken))) {
      return reply.code(401).send({ reason: "bad_operator_token" });
    }
  };
  // The credential issuer defaults to the hot account, so it is filled at runtime, not in policy.json.
  const withIssuer = (p: Policy) => ({ ...p, credentialIssuer: p.credentialIssuer ?? hot.address });
  let policy = withIssuer(loadPolicy(deps.policyPath));
  // v1.6: every audit row records the hash of the policy file it was decided under.
  let policyHash = policyFileHash(deps.policyPath);
  // Contract v1.5: every built transaction gets a plain-English preview on its audit row.
  const previewOf = (tx: object) => {
    const names: Record<string, string> = { [hot.address]: "agent (hot key)" };
    const treasury = device.status().address;
    if (treasury) names[treasury] = "treasury (Ledger)";
    return describe(tx as Tx, { names, network: "xrpl:1" });
  };
  // Amounts of auto requests decided but not yet written to the audit log (concurrent /v1/pay).
  let inFlightDrops = 0n;

  const app = Fastify({ logger: false });
  await app.register(cors, { origin: ALLOWED_ORIGINS, methods: ["GET", "PUT", "POST", "DELETE", "OPTIONS"] });
  // device-tap and deny take no body; accept an empty one even when sent as application/json.
  app.addContentTypeParser("application/json", { parseAs: "string" }, (_req, body, done) => {
    if (body === "") return done(null, {});
    try {
      done(null, JSON.parse(body as string));
    } catch {
      done(Object.assign(new Error("invalid JSON body"), { statusCode: 400 }), undefined);
    }
  });

  app.get("/health", async () => ({ ok: true }));

  app.post("/v1/pay", async (request, reply) => {
    const parsed = PayBodySchema.safeParse(request.body);
    if (!parsed.success) return reply.code(400).send({ reason: "bad_request", issues: parsed.error.issues });
    const { requirements: req, purpose = "", resource, source = "hot" } = parsed.data;
    if (typeof req.extra?.invoiceId !== "string" || !req.extra.invoiceId) {
      return reply.code(400).send({ reason: "invoice_id_required" });
    }

    const id = randomUUID();
    const amount = BigInt(req.amount);
    const row: RequestRow = {
      id, ts: new Date().toISOString(), merchant: req.payTo, amountDrops: amount.toString(), purpose,
      resourceUrl: resource?.url ?? "", status: "refused", reason: null, signer: null, txHash: null,
      ...(source === "treasury" ? { source } : {}), policyHash,
    };
    // Treasury payments carry `source` in every response; hot (x402) responses stay as they were.
    const src = source === "treasury" ? { source } : {};
    // Rule 3's ledger lookup. Fail closed: an RPC error counts as not credentialed (and is not cached).
    const p = policy;
    let credentialed = false;
    if (needsCredentialLookup(req, p)) {
      try {
        credentialed = await credentials.check(req.payTo, p.credentialIssuer, p.credentialType);
      } catch (e) {
        log(`credential lookup failed merchant=${req.payTo} id=${id}: ${(e as Error).message}`);
      }
    }
    // spent-today is read after the lookup's await so the in-flight reservation below stays exact.
    const decision = decide(req, audit.spentToday() + inFlightDrops, p, credentialed);
    const word = { auto: "auto", hold: "held", refuse: "refused" }[decision.kind];
    log(`decision=${word}${decision.kind === "refuse" ? ` reason=${decision.reason}` : ""} amount=${row.amountDrops} merchant=${req.payTo} id=${id}${source === "treasury" ? " source=treasury" : ""}`);

    if (decision.kind === "refuse") {
      audit.put({ ...row, status: "refused", reason: decision.reason });
      return reply.code(403).send({ decision: "refused", requestId: id, reason: decision.reason, ...src });
    }

    // Treasury payments are submitted here (the T54 facilitator refuses delegated blobs) and the
    // ledger's verdict is final: a ter/tec result is a refusal with the engine result verbatim.
    const settleTreasury = async (
      decided: "auto" | "approved", signer: Signer, account: string, signed: SignedTx, lastLedger: number,
      write: (patch: Partial<RequestRow>) => void,
    ) => {
      let r: DirectResult;
      try {
        r = await deps.treasury.submit(signed.blob, signed.hash, lastLedger);
      } catch (e) {
        log(`treasury submit failed id=${id}: ${(e as Error).message}`);
        write({ status: "refused", reason: "rpc_error", signer, txHash: signed.hash });
        return reply.code(502).send({ requestId: id, reason: "rpc_error", txHash: signed.hash, ...src });
      }
      log(`treasury submit result=${r.engineResult} id=${id} txHash=${r.txHash}`);
      if (r.engineResult === "tesSUCCESS") {
        write({ status: decided, signer, txHash: r.txHash });
        return reply.send({ decision: decided, requestId: id, ...src, signer, account, txHash: r.txHash, engineResult: r.engineResult });
      }
      write({ status: "refused", reason: r.engineResult, signer, txHash: r.txHash });
      return reply.code(403).send({ decision: "refused", requestId: id, ...src, reason: r.engineResult, engineResult: r.engineResult, txHash: r.txHash });
    };

    const buildError = (e: unknown) => {
      if (e instanceof PaymentError) return reply.code(400).send({ requestId: id, reason: e.message });
      log(`build failed id=${id}: ${(e as Error).message}`);
      return reply.code(502).send({ requestId: id, reason: "rpc_error" });
    };

    if (decision.kind === "auto") {
      inFlightDrops += amount;
      try {
        if (source === "treasury") {
          const treasury = device.status().address;
          if (!treasury) {
            audit.put({ ...row, status: "refused", reason: "device_unavailable" });
            return reply.code(503).send({ decision: "refused", requestId: id, reason: "device_unavailable", ...src });
          }
          const tx = await buildPayment(ledger, req, treasury, undefined, hot.address);
          row.preview = previewOf(tx);
          return await settleTreasury("auto", "hot (delegated)", treasury, hot.sign(tx), tx.LastLedgerSequence!, (patch) =>
            audit.put({ ...row, ...patch }),
          );
        }
        const tx = await buildPayment(ledger, req, hot.address);
        row.preview = previewOf(tx);
        const signed = hot.sign(tx);
        audit.put({ ...row, status: "auto", signer: "hot", txHash: signed.hash });
        return reply.send({ decision: "auto", requestId: id, signer: "hot", account: hot.address, signedTxBlob: signed.blob, txHash: signed.hash });
      } catch (e) {
        return buildError(e);
      } finally {
        inFlightDrops -= amount;
      }
    }

    // hold → device path
    const dev = device.status();
    if (!dev.connected || !dev.address || !dev.publicKey) {
      audit.put({ ...row, status: "refused", reason: "device_unavailable" });
      log(`decision=refused reason=device_unavailable amount=${row.amountDrops} merchant=${req.payTo} id=${id}`);
      return reply.code(503).send({ decision: "refused", requestId: id, reason: "device_unavailable", ...src });
    }
    let tx;
    try {
      tx = await buildPayment(ledger, req, dev.address, dev.publicKey);
    } catch (e) {
      return buildError(e);
    }
    row.preview = previewOf(tx);
    audit.put({ ...row, status: "held" });
    log(`hold id=${id} preview: ${row.preview.summary}`);
    const outcome: HoldOutcome = await holds.create(id, tx, policy.holdTimeoutSeconds * 1000);
    const resolved = { approved: "approved", denied: "refused", expired: "expired", unavailable: "refused" }[outcome.kind];
    log(`decision=${resolved}${outcome.kind === "approved" ? "" : ` reason=${{ denied: "denied_on_device", expired: "hold_timeout", unavailable: "device_unavailable" }[outcome.kind]}`} amount=${row.amountDrops} merchant=${req.payTo} id=${id}`);
    switch (outcome.kind) {
      case "approved":
        if (source === "treasury") {
          return settleTreasury("approved", "device", dev.address, outcome.signed, tx.LastLedgerSequence!, (patch) => audit.update(id, patch));
        }
        audit.update(id, { status: "approved", signer: "device", txHash: outcome.signed.hash });
        return reply.send({
          decision: "approved", requestId: id, signer: "device", account: dev.address,
          signedTxBlob: outcome.signed.blob, txHash: outcome.signed.hash,
        });
      case "denied":
        audit.update(id, { status: "refused", reason: "denied_on_device" });
        return reply.code(403).send({ decision: "refused", requestId: id, reason: "denied_on_device", ...src });
      case "expired":
        audit.update(id, { status: "expired", reason: "hold_timeout" });
        return reply.code(408).send({ decision: "expired", requestId: id, reason: "hold_timeout", ...src });
      case "unavailable":
        log(`device error id=${id}: ${outcome.detail}`);
        audit.update(id, { status: "refused", reason: "device_unavailable" });
        return reply.code(503).send({ decision: "refused", requestId: id, reason: "device_unavailable", ...src });
    }
  });

  app.get<{ Querystring: { limit?: string } }>("/v1/requests", async (request) => {
    const n = Number.parseInt(request.query.limit ?? "200", 10);
    return audit.list(Number.isFinite(n) && n > 0 ? Math.min(n, 1000) : 200);
  });

  const pendingOr = (id: string, reply: import("fastify").FastifyReply) =>
    audit.get(id) ? reply.code(409).send({ reason: "not_pending" }) : reply.code(404).send({ reason: "not_found" });

  app.post<{ Params: { id: string } }>("/v1/requests/:id/device-tap", async (request, reply) => {
    if (!holds.tap(request.params.id)) return pendingOr(request.params.id, reply);
    return reply.code(202).send({ ok: true });
  });

  app.post<{ Params: { id: string } }>("/v1/requests/:id/deny", async (request, reply) => {
    if (!holds.deny(request.params.id)) return pendingOr(request.params.id, reply);
    return reply.send({ ok: true });
  });

  app.get("/v1/policy", async () => policy);

  app.put("/v1/policy", { preHandler: operator }, async (request, reply) => {
    const parsed = PolicySchema.safeParse(request.body);
    if (!parsed.success) return reply.code(400).send({ reason: "bad_policy", issues: parsed.error.issues });
    policy = withIssuer(parsed.data);
    // The hot-account issuer default stays in memory only, even when a client echoes GET's filled value back.
    const { credentialIssuer, ...rest } = parsed.data;
    savePolicy(deps.policyPath, credentialIssuer === hot.address ? rest : parsed.data);
    policyHash = policyFileHash(deps.policyPath);
    log(`policy updated ${JSON.stringify(policy)}`);
    return policy;
  });

  // On-ledger allowlist. The hot key signs; nothing goes to the device.
  const submitted = async (reply: import("fastify").FastifyReply, verb: string, address: string, run: () => Promise<Submitted>) => {
    let r: Submitted;
    try {
      r = await run();
    } catch (e) {
      log(`merchant ${verb} failed address=${address}: ${(e as Error).message}`);
      return reply.code(502).send({ reason: "rpc_error" });
    }
    log(`merchant ${verb} result=${r.engineResult} address=${address} txHash=${r.txHash}`);
    if (r.engineResult === "tesSUCCESS") return reply.send({ txHash: r.txHash });
    const code = ENGINE_STATUS[r.engineResult] ?? (r.engineResult.startsWith("tem") ? 400 : 500);
    return reply.code(code).send({ reason: r.engineResult, ...(r.txHash ? { txHash: r.txHash } : {}) });
  };
  const merchantGuard = (address: unknown, reply: import("fastify").FastifyReply) => {
    if (typeof address !== "string" || !isValidClassicAddress(address)) return reply.code(400).send({ reason: "bad_address" });
    if (policy.credentialIssuer !== hot.address) return reply.code(400).send({ reason: "issuer_not_hot_account" });
    return null;
  };

  app.post("/v1/merchants", { preHandler: operator }, async (request, reply) => {
    const address = (request.body as { address?: unknown } | null)?.address;
    const refused = merchantGuard(address, reply);
    if (refused) return refused;
    return submitted(reply, "vet", address as string, () => credentials.create(address as string, policy.credentialType));
  });

  app.delete<{ Params: { address: string } }>("/v1/merchants/:address", { preHandler: operator }, async (request, reply) => {
    const { address } = request.params;
    const refused = merchantGuard(address, reply);
    if (refused) return refused;
    return submitted(reply, "revoke", address, () => credentials.remove(address, policy.credentialType));
  });

  app.get("/v1/merchants", async (_request, reply) => {
    try {
      return await credentials.list(policy.credentialIssuer, policy.credentialType);
    } catch (e) {
      log(`merchant list failed: ${(e as Error).message}`);
      return reply.code(502).send({ reason: "rpc_error" });
    }
  });

  // Permissioned Domain: membership = the vet credential. The hot key (the credential issuer) signs.
  app.post("/v1/domain", { preHandler: operator }, async (_request, reply) => {
    if (policy.credentialIssuer !== hot.address) return reply.code(400).send({ reason: "issuer_not_hot_account" });
    let r: Submitted;
    try {
      r = await credentials.setDomain(policy.credentialType);
    } catch (e) {
      log(`domain set failed: ${(e as Error).message}`);
      return reply.code(502).send({ reason: "rpc_error" });
    }
    log(`domain set result=${r.engineResult} txHash=${r.txHash}`);
    if (r.engineResult !== "tesSUCCESS") {
      const code = ENGINE_STATUS[r.engineResult] ?? (r.engineResult.startsWith("tem") ? 400 : 500);
      return reply.code(code).send({ reason: r.engineResult, ...(r.txHash ? { txHash: r.txHash } : {}) });
    }
    try {
      return { txHash: r.txHash, domain: await credentials.domain(policy.credentialType) };
    } catch {
      return { txHash: r.txHash, domain: null };
    }
  });

  app.get("/v1/domain", async (_request, reply) => {
    try {
      return { domain: await credentials.domain(policy.credentialType) };
    } catch (e) {
      log(`domain lookup failed: ${(e as Error).message}`);
      return reply.code(502).send({ reason: "rpc_error" });
    }
  });

  // PermissionDelegation: the treasury grants or revokes the hot key's Payment permission. The
  // DelegateSet is device-signed through the hold queue (dashboard Approve = device tap). The XRP app
  // cannot clear-sign it, so the device shows a blind-signing warning first (demo-only setting).
  app.post("/v1/delegate", { preHandler: operator }, async (request, reply) => {
    const action = (request.body as { action?: unknown } | null)?.action;
    if (action !== "grant" && action !== "revoke") return reply.code(400).send({ reason: "bad_action" });
    const dev = device.status();
    if (!dev.connected || !dev.address || !dev.publicKey) return reply.code(503).send({ reason: "device_unavailable" });
    const id = randomUUID();
    let tx;
    try {
      // The hold can last holdTimeoutSeconds, so the blob must outlive it (≈3.5 s per ledger).
      const lastLedger = (await deps.treasury.validatedLedgerIndex()) + Math.ceil(policy.holdTimeoutSeconds / 3) + 10;
      tx = await deps.treasury.autofill({
        ...delegateSet(dev.address, hot.address, action === "grant" ? ["Payment"] : [], lastLedger),
        SigningPubKey: dev.publicKey,
      });
    } catch (e) {
      log(`delegate ${action} build failed: ${(e as Error).message}`);
      return reply.code(502).send({ reason: "rpc_error" });
    }
    const preview = previewOf(tx);
    audit.put({
      preview,
      id, ts: new Date().toISOString(), merchant: hot.address, amountDrops: "0",
      purpose: action === "grant" ? "grant agent permission: Payment" : "revoke agent permissions",
      resourceUrl: `delegate://${action}`, status: "held", reason: null, signer: null, txHash: null,
      source: "treasury", kind: "delegate", policyHash,
    });
    log(`delegate ${action} held id=${id} preview: ${preview.summary}`);
    const outcome = await holds.create(id, tx, policy.holdTimeoutSeconds * 1000);
    log(`delegate ${action} outcome=${outcome.kind} id=${id}`);
    switch (outcome.kind) {
      case "approved": {
        let r: DirectResult;
        try {
          r = await deps.treasury.submit(outcome.signed.blob, outcome.signed.hash, tx.LastLedgerSequence!);
        } catch (e) {
          log(`delegate ${action} submit failed id=${id}: ${(e as Error).message}`);
          audit.update(id, { status: "refused", reason: "rpc_error", signer: "device", txHash: outcome.signed.hash });
          return reply.code(502).send({ requestId: id, reason: "rpc_error", txHash: outcome.signed.hash });
        }
        log(`delegate ${action} result=${r.engineResult} id=${id} txHash=${r.txHash}`);
        if (r.engineResult !== "tesSUCCESS") {
          audit.update(id, { status: "refused", reason: r.engineResult, signer: "device", txHash: r.txHash });
          return reply.code(500).send({ requestId: id, reason: r.engineResult, ...(r.txHash ? { txHash: r.txHash } : {}) });
        }
        audit.update(id, { status: "approved", signer: "device", txHash: r.txHash });
        let permissions: string[] | null = null;
        try {
          permissions = permissionsFor(await deps.treasury.delegates(dev.address), hot.address);
        } catch (e) {
          log(`delegate lookup failed: ${(e as Error).message}`);
        }
        return reply.send({ action, requestId: id, txHash: r.txHash, engineResult: r.engineResult, permissions });
      }
      case "denied":
        audit.update(id, { status: "refused", reason: "denied_on_device" });
        return reply.code(403).send({ requestId: id, reason: "denied_on_device" });
      case "expired":
        audit.update(id, { status: "expired", reason: "hold_timeout" });
        return reply.code(408).send({ requestId: id, reason: "hold_timeout" });
      case "unavailable":
        log(`device error id=${id}: ${outcome.detail}`);
        audit.update(id, { status: "refused", reason: "device_unavailable" });
        return reply.code(503).send({ requestId: id, reason: "device_unavailable" });
    }
  });

  // Held-loan approval (DX finding 12: the XRP app cannot sign a LoanSet). The device signs a 1-drop
  // approval Payment from the treasury carrying the LoanSet hash in a Memo; the lending desk co-signs
  // the LoanSet with its broker key only after this Payment validates.
  app.post("/v1/lend/approve", async (request, reply) => {
    const { loanSetHash, loanSetBlob } = (request.body ?? {}) as { loanSetHash?: unknown; loanSetBlob?: unknown };
    if (typeof loanSetHash !== "string" || !/^[0-9A-Fa-f]{64}$/.test(loanSetHash)) return reply.code(400).send({ reason: "bad_loan_set_hash" });
    // Optional: the signed LoanSet itself, so the human reads the loan terms before the device tap.
    let loanPreview;
    let terms: string | undefined;
    if (loanSetBlob !== undefined) {
      if (typeof loanSetBlob !== "string" || !/^([0-9A-Fa-f]{2})+$/.test(loanSetBlob)) return reply.code(400).send({ reason: "bad_loan_set_blob" });
      if (createHash("sha256").update(Buffer.from(loanSetBlob, "hex")).digest("hex").toUpperCase() !== loanSetHash.toUpperCase()) {
        return reply.code(400).send({ reason: "loan_set_hash_mismatch" });
      }
      let loanSet;
      try {
        loanSet = decode(loanSetBlob);
      } catch {
        return reply.code(400).send({ reason: "bad_loan_set_blob" });
      }
      if (loanSet.TransactionType !== "LoanSet") return reply.code(400).send({ reason: "not_a_loan_set" });
      terms = loanTermsText(loanSet) ?? undefined;
      if (!terms) return reply.code(400).send({ reason: "bad_loan_terms" });
      loanPreview = previewOf(loanSet);
    }
    const dev = device.status();
    if (!dev.connected || !dev.address || !dev.publicKey) return reply.code(503).send({ reason: "device_unavailable" });
    const id = randomUUID();
    let tx;
    try {
      const lastLedger = (await ledger.validatedLedgerIndex()) + Math.ceil(policy.holdTimeoutSeconds / 3) + 10;
      tx = await ledger.autofill({
        TransactionType: "Payment", Account: dev.address, Destination: hot.address, Amount: "1",
        Memos: [
          { Memo: { MemoType: Buffer.from(LOAN_APPROVAL_MEMO).toString("hex").toUpperCase(), MemoData: loanSetHash.toUpperCase() } },
          ...(terms ? [{ Memo: { MemoType: Buffer.from(LOAN_TERMS_MEMO).toString("hex").toUpperCase(), MemoData: Buffer.from(terms, "ascii").toString("hex").toUpperCase() } }] : []),
        ],
        SigningPubKey: dev.publicKey, LastLedgerSequence: lastLedger,
      });
    } catch (e) {
      log(`lend approve build failed: ${(e as Error).message}`);
      return reply.code(502).send({ reason: "rpc_error" });
    }
    const preview = previewOf(tx);
    audit.put({
      preview,
      id, ts: new Date().toISOString(), merchant: hot.address, amountDrops: "1",
      purpose: `approve held loan ${loanSetHash.slice(0, 8).toUpperCase()}…`,
      resourceUrl: `lend://approve/${loanSetHash.toUpperCase()}`, status: "held", reason: null, signer: null, txHash: null,
      source: "treasury", kind: "lend", ...(loanPreview ? { loanPreview } : {}), policyHash,
    });
    log(`lend approve held id=${id} loanSetHash=${loanSetHash} preview: ${preview.summary}`);
    const outcome = await holds.create(id, tx, policy.holdTimeoutSeconds * 1000);
    log(`lend approve outcome=${outcome.kind} id=${id}`);
    switch (outcome.kind) {
      case "approved": {
        let r: DirectResult;
        try {
          r = await deps.treasury.submit(outcome.signed.blob, outcome.signed.hash, tx.LastLedgerSequence!);
        } catch (e) {
          log(`lend approve submit failed id=${id}: ${(e as Error).message}`);
          audit.update(id, { status: "refused", reason: "rpc_error", signer: "device", txHash: outcome.signed.hash });
          return reply.code(502).send({ requestId: id, reason: "rpc_error", txHash: outcome.signed.hash });
        }
        log(`lend approve result=${r.engineResult} id=${id} txHash=${r.txHash}`);
        if (r.engineResult !== "tesSUCCESS") {
          audit.update(id, { status: "refused", reason: r.engineResult, signer: "device", txHash: r.txHash });
          return reply.code(500).send({ requestId: id, reason: r.engineResult, ...(r.txHash ? { txHash: r.txHash } : {}) });
        }
        audit.update(id, { status: "approved", signer: "device", txHash: r.txHash });
        return reply.send({ requestId: id, loanSetHash: loanSetHash.toUpperCase(), txHash: r.txHash, engineResult: r.engineResult, account: dev.address });
      }
      case "denied":
        audit.update(id, { status: "refused", reason: "denied_on_device" });
        return reply.code(403).send({ requestId: id, reason: "denied_on_device" });
      case "expired":
        audit.update(id, { status: "expired", reason: "hold_timeout" });
        return reply.code(408).send({ requestId: id, reason: "hold_timeout" });
      case "unavailable":
        log(`device error id=${id}: ${outcome.detail}`);
        audit.update(id, { status: "refused", reason: "device_unavailable" });
        return reply.code(503).send({ requestId: id, reason: "device_unavailable" });
    }
  });

  app.get("/v1/delegate", async (_request, reply) => {
    const treasury = device.status().address;
    if (!treasury) return reply.code(503).send({ reason: "device_unavailable" });
    try {
      const objects = await deps.treasury.delegates(treasury);
      return { treasury, agent: hot.address, permissions: permissionsFor(objects, hot.address), objects };
    } catch (e) {
      log(`delegate lookup failed: ${(e as Error).message}`);
      return reply.code(502).send({ reason: "rpc_error" });
    }
  });

  // Control tower: every known account, addresses and roles only (never seeds or other fields).
  const readJson = (path: string | undefined): unknown => {
    try {
      return path && existsSync(path) ? JSON.parse(readFileSync(path, "utf8")) : null;
    } catch {
      return null;
    }
  };
  type Known = { address: string; name: string; role: string };
  app.get("/v1/accounts", async () => {
    const testnet: Known[] = [{ address: hot.address, name: "agent (hot key)", role: "agent" }];
    const treasury = device.status().address;
    if (treasury) testnet.push({ address: treasury, name: "treasury (Ledger)", role: "treasury" });
    const merchants = readJson(deps.accountFiles?.merchants) as Record<string, { address?: unknown }> | null;
    for (const [name, m] of Object.entries(merchants ?? {})) {
      if (typeof m?.address === "string" && isValidClassicAddress(m.address)) testnet.push({ address: m.address, name: `${name} merchant`, role: "merchant" });
    }
    const lending = readJson(deps.accountFiles?.lending) as {
      accounts?: Record<string, unknown>; history?: { customers?: unknown[] }; vaultId?: unknown; loanBrokerId?: unknown;
    } | null;
    const devnet: Known[] = [];
    const roleOf = (k: string) => (k === "broker" ? "broker" : k === "borrower" ? "borrower" : k.startsWith("depositor") || k.startsWith("supplier") ? "supplier" : "lending");
    for (const [k, a] of Object.entries(lending?.accounts ?? {})) {
      if (typeof a === "string" && isValidClassicAddress(a)) devnet.push({ address: a, name: k, role: roleOf(k) });
    }
    for (const [i, a] of (lending?.history?.customers ?? []).entries()) {
      if (typeof a === "string" && isValidClassicAddress(a)) devnet.push({ address: a, name: `customer ${i + 1}`, role: "customer" });
    }
    const hex64 = (v: unknown) => (typeof v === "string" && /^[0-9A-F]{64}$/i.test(v) ? v : null);
    return { testnet, devnet, devnetObjects: { vaultId: hex64(lending?.vaultId), loanBrokerId: hex64(lending?.loanBrokerId) } };
  });

  // Balances are cached for 5 s: the dashboard polls status every second.
  let balanceCache: { at: number; hot: string | null; device: string | null; deviceAccount: string | null } | null = null;
  app.get("/v1/status", async () => {
    const dev = device.status();
    if (!balanceCache || Date.now() - balanceCache.at > 5000 || balanceCache.deviceAccount !== dev.address) {
      const [hotBal, devBal] = await Promise.all([
        deps.balanceDrops(hot.address),
        dev.address ? deps.balanceDrops(dev.address) : Promise.resolve(null),
      ]);
      balanceCache = { at: Date.now(), hot: hotBal, device: devBal, deviceAccount: dev.address };
    }
    return {
      hotAccount: hot.address,
      hotBalanceDrops: balanceCache.hot,
      deviceAccount: dev.address,
      deviceBalanceDrops: balanceCache.device,
      deviceConnected: dev.connected,
      deviceApp: dev.app,
      spentTodayDrops: audit.spentToday().toString(),
      pending: holds.pendingCount(),
    };
  });

  return app;
}
