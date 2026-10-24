// Gate 3: one auto payment (hot key) and one held payment (Ledger, tapped via /device-tap),
// both submitted to testnet with submitAndWait, both must be tesSUCCESS.
// Uses the wallet already running on WALLET_URL (default http://localhost:7402) when it answers
// /health, because only one DMK client may hold Speculos; otherwise boots one in-process.
import { copyFileSync, mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { config as loadEnv } from "dotenv";
import { Client, Wallet } from "xrpl";
import { buildApp, createDeps } from "../src/server.js";
import type { Policy } from "../src/types.js";

const root = fileURLToPath(new URL("..", import.meta.url));
loadEnv({ path: `${root}.env`, quiet: true });
const XRPL_WSS = process.env.XRPL_WSS ?? "wss://s.altnet.rippletest.net:51233";
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
const explorer = (hash: string) => `https://testnet.xrpl.org/transactions/${hash}`;

async function json<T>(url: string, init?: RequestInit): Promise<{ status: number; body: T }> {
  const res = await fetch(url, { ...init, headers: { "Content-Type": "application/json", ...init?.headers } });
  return { status: res.status, body: (await res.json()) as T };
}

let wallet = process.env.WALLET_URL ?? "http://localhost:7402";
// PUT /v1/policy is an operator route (contract v1.7).
const operator = { "X-Wallet-Token": process.env.WALLET_ADMIN_TOKEN ?? "" };
let close = async () => {};
const running = await fetch(`${wallet}/health`).then((r) => r.ok, () => false);
if (running) {
  console.log(`using running wallet at ${wallet}`);
} else {
  if (!process.env.HOT_WALLET_SEED) throw new Error("HOT_WALLET_SEED unset: run `npm run setup`");
  const dir = mkdtempSync(join(tmpdir(), "pw-smoke-"));
  copyFileSync(`${root}policy.json`, join(dir, "policy.json"));
  const deps = createDeps({
    hotSeed: process.env.HOT_WALLET_SEED,
    speculosUrl: process.env.SPECULOS_URL ?? "http://127.0.0.1:5000",
    xrplWss: XRPL_WSS,
    policyPath: join(dir, "policy.json"),
    auditPath: join(dir, "requests.jsonl"),
  });
  deps.adminToken = process.env.WALLET_ADMIN_TOKEN || undefined;
  const app = await buildApp(deps);
  wallet = await app.listen({ port: 0, host: "127.0.0.1" });
  close = async () => {
    await app.close();
    await deps.xrpl.close();
  };
  console.log(`booted wallet in-process at ${wallet}`);
  for (let i = 0; i < 60 && !deps.device.status().connected; i++) await sleep(500);
}

const client = new Client(XRPL_WSS);
await client.connect();
const { body: original } = await json<Policy>(`${wallet}/v1/policy`);
let failed = false;
try {
  const { body: status } = await json<{ deviceConnected: boolean; hotAccount: string; deviceAccount: string }>(`${wallet}/v1/status`);
  if (!status.deviceConnected) throw new Error("device not connected (is Speculos on :5000?)");
  console.log(`hot=${status.hotAccount} device=${status.deviceAccount}`);

  const { wallet: dest } = await client.fundWallet(Wallet.generate());
  console.log(`throwaway merchant ${dest.classicAddress} funded from faucet`);
  const allow = await json(`${wallet}/v1/policy`, {
    method: "PUT",
    headers: operator,
    body: JSON.stringify({ ...original, allowedMerchants: [...original.allowedMerchants, dest.classicAddress] }),
  });
  if (allow.status !== 200) throw new Error(`PUT /v1/policy answered ${allow.status}: set WALLET_ADMIN_TOKEN in wallet/.env`);

  const tag = Math.random().toString(36).slice(2, 10);
  const pay = (amount: string, kind: string) =>
    json<{ decision: string; requestId: string; signedTxBlob: string; txHash: string; reason?: string }>(`${wallet}/v1/pay`, {
      method: "POST",
      body: JSON.stringify({
        requirements: {
          scheme: "exact", network: "xrpl:1", amount, asset: "XRP", payTo: dest.classicAddress, maxTimeoutSeconds: 600,
          extra: { invoiceId: `smoke-${kind}-${tag}`, sourceTag: 20260601, facilitator: { id: "smoke", name: "Policy Wallet smoke" } },
        },
        purpose: `smoke ${kind}`,
        resource: { url: `smoke://${kind}/${tag}`, description: "smoke test" },
      }),
    });

  const auto = await pay("1000", "auto");
  console.log(`auto  → ${auto.status} ${auto.body.decision} ${auto.body.txHash ?? auto.body.reason}`);
  if (auto.body.decision !== "auto") throw new Error("expected auto");

  const holdAmount = (BigInt(original.perTxCapDrops) + 100_000n).toString();
  const heldPay = pay(holdAmount, "hold");
  await sleep(1000);
  const { body: rows } = await json<{ id: string; status: string; resourceUrl: string }[]>(`${wallet}/v1/requests?limit=20`);
  const held = rows.find((r) => r.resourceUrl === `smoke://hold/${tag}`);
  if (held?.status !== "held") throw new Error(`expected a held row, got ${held?.status}`);
  const tap = await json(`${wallet}/v1/requests/${held.id}/device-tap`, { method: "POST" });
  console.log(`held  → ${held.id} device-tap ${tap.status}`);
  const approved = await heldPay;
  console.log(`held  → ${approved.status} ${approved.body.decision} ${approved.body.txHash ?? approved.body.reason}`);
  if (approved.body.decision !== "approved") throw new Error("expected approved");

  for (const [label, r] of [["auto", auto.body], ["approved", approved.body]] as const) {
    const res = await client.submitAndWait(r.signedTxBlob);
    const meta = res.result.meta;
    const result = typeof meta === "object" && meta ? meta.TransactionResult : "unknown";
    const hashOk = res.result.hash === r.txHash;
    console.log(`${label.padEnd(8)} ${result} hash ${hashOk ? "matches" : "MISMATCH"} ${explorer(res.result.hash)}`);
    if (result !== "tesSUCCESS" || !hashOk) failed = true;
  }
} catch (e) {
  failed = true;
  console.error(`smoke failed: ${(e as Error).message}`);
} finally {
  await json(`${wallet}/v1/policy`, { method: "PUT", headers: operator, body: JSON.stringify(original) }).catch(() => {});
  await client.disconnect();
  await close();
}
console.log(failed ? "SMOKE FAIL" : "SMOKE OK");
process.exit(failed ? 1 : 0);
