// Creates and funds the hot wallet from the testnet faucet if HOT_WALLET_SEED is unset, writes .env,
// then prints both accounts and balances. Never funds the device account.
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { config as loadEnv } from "dotenv";
import { Client, Wallet, dropsToXrp } from "xrpl";
import { LedgerDevice } from "../src/device.js";

const FAUCET_URL = "https://faucet.altnet.rippletest.net/accounts";
const MIN_DROPS = 20_000_000n;
const root = fileURLToPath(new URL("..", import.meta.url));
const envPath = `${root}.env`;
loadEnv({ path: envPath, quiet: true });

const client = new Client(process.env.XRPL_WSS ?? "wss://s.altnet.rippletest.net:51233");
await client.connect();

let seed = process.env.HOT_WALLET_SEED;
if (!seed) {
  console.log("HOT_WALLET_SEED unset: creating a hot wallet and funding it from the testnet faucet...");
  const { wallet } = await client.fundWallet(Wallet.generate());
  seed = wallet.seed!;
  const base = existsSync(envPath) ? readFileSync(envPath, "utf8") : readFileSync(`${root}.env.example`, "utf8");
  const next = /^HOT_WALLET_SEED=.*$/m.test(base) ? base.replace(/^HOT_WALLET_SEED=.*$/m, `HOT_WALLET_SEED=${seed}`) : `${base.trimEnd()}\nHOT_WALLET_SEED=${seed}\n`;
  writeFileSync(envPath, next);
  console.log(`wrote HOT_WALLET_SEED to ${envPath}`);
}
const hot = Wallet.fromSeed(seed);

async function balance(address: string): Promise<bigint | null> {
  try {
    const r = await client.request({ command: "account_info", account: address, ledger_index: "validated" });
    return BigInt(r.result.account_data.Balance);
  } catch {
    return null;
  }
}

function report(label: string, address: string | null, drops: bigint | null): void {
  const xrp = drops === null ? "not found" : `${dropsToXrp(drops.toString())} XRP`;
  console.log(`${label.padEnd(7)} ${address ?? "(unavailable)"}  ${xrp}`);
  if (address && (drops === null || drops < MIN_DROPS)) {
    console.log(`  WARNING: ${label} account is below 20 XRP. Fund it: POST ${FAUCET_URL} {"destination":"${address}"}`);
  }
}

report("hot", hot.classicAddress, await balance(hot.classicAddress));

const device = new LedgerDevice(process.env.SPECULOS_URL ?? "http://127.0.0.1:5000", () => {});
device.start();
const deadline = Date.now() + 15_000;
while (!device.status().connected && Date.now() < deadline) await new Promise((r) => setTimeout(r, 250));
const dev = device.status();
if (!dev.connected) console.log("device  (not connected: is Speculos running on SPECULOS_URL?)");
else report("device", dev.address, await balance(dev.address!));

await client.disconnect();
process.exit(0);
