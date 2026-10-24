import { appendFileSync, copyFileSync, existsSync, mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { config as loadEnv } from "dotenv";
import { buildApp, createDeps } from "./server.js";

const root = fileURLToPath(new URL("..", import.meta.url));
loadEnv({ path: `${root}.env`, quiet: true });

const seed = process.env.HOT_WALLET_SEED;
if (!seed) {
  console.error("HOT_WALLET_SEED is not set in wallet/.env. Run `npm run setup` first.");
  process.exit(1);
}

// Crash loudly: log to data/crash.log and exit 1. scripts/run.sh restarts the wallet, and the
// boot-time stale-review reject makes a restart safe.
const crash = (kind: string) => (err: unknown) => {
  mkdirSync(`${root}data`, { recursive: true });
  appendFileSync(`${root}data/crash.log`, `${new Date().toISOString()} ${kind}: ${(err as Error)?.stack ?? String(err)}\n`);
  console.error(`${kind}:`, err);
  process.exit(1);
};
process.on("uncaughtException", crash("uncaughtException"));
process.on("unhandledRejection", crash("unhandledRejection"));

// The tracked policy.json is only the default: runtime edits (PUT /v1/policy) go to data/policy.json.
const policyPath = `${root}data/policy.json`;
if (!existsSync(policyPath)) {
  mkdirSync(`${root}data`, { recursive: true });
  copyFileSync(`${root}policy.json`, policyPath);
}

const deps = createDeps({
  hotSeed: seed,
  speculosUrl: process.env.SPECULOS_URL ?? "http://127.0.0.1:5000",
  xrplWss: process.env.XRPL_WSS ?? "wss://s.altnet.rippletest.net:51233",
  policyPath,
  auditPath: `${root}data/requests.jsonl`,
});
deps.accountFiles = { merchants: `${root}../agent/merchants.json`, lending: `${root}../lending/accounts.json` };
deps.adminToken = process.env.WALLET_ADMIN_TOKEN || undefined;
const app = await buildApp(deps);
const port = Number(process.env.PORT ?? 7402);
await app.listen({ port, host: "localhost" });
console.log(`wallet listening on http://localhost:${port} hot=${deps.hot.address}`);
