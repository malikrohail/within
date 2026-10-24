// Delegate spike: the treasury (Ledger account) sends DelegateSet,
// signed on Speculos. Needs Speculos to itself: stop scripts/run.sh first (one DMK client only).
//   npx tsx scripts/spike-delegate.ts grant | revoke | state
// grant: Permissions [Payment] for the hot account; revoke: empty Permissions. Testnet only.
import { config as loadEnv } from "dotenv";
import { fileURLToPath } from "node:url";
import { Client, Wallet, encode, hashes, type DelegateSet } from "xrpl";
import { LedgerDevice } from "../src/device.js";
import { Speculos, drainSpeculosResponses } from "../src/speculos.js";

const root = fileURLToPath(new URL("..", import.meta.url));
loadEnv({ path: `${root}.env`, quiet: true });
const mode = process.argv[2];
if (!["grant", "revoke", "state"].includes(mode)) throw new Error("usage: spike-delegate.ts grant|revoke|state");
const WSS = process.env.XRPL_WSS ?? "wss://s.altnet.rippletest.net:51233";
if (!/altnet|testnet/.test(WSS)) throw new Error("testnet only");
const SPECULOS = process.env.SPECULOS_URL ?? "http://127.0.0.1:5000";
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
const hot = Wallet.fromSeed(process.env.HOT_WALLET_SEED!).classicAddress;

const client = new Client(WSS);
await client.connect();
const delegateObjects = async (treasury: string) =>
  ((await client.request({ command: "account_objects", account: treasury, type: "delegate", ledger_index: "validated" } as never)) as {
    result: { account_objects: unknown[] };
  }).result;

drainSpeculosResponses(SPECULOS);
const device = new LedgerDevice(SPECULOS, (m) => console.log(`[device] ${m}`));
device.start();
for (let i = 0; i < 40 && !device.status().connected; i++) await sleep(500);
const { address: treasury, publicKey } = device.status();
if (!treasury || !publicKey) throw new Error("device not connected");
console.log(`treasury=${treasury} hot=${hot}`);

if (mode !== "state") {
  const tx = await client.autofill({
    TransactionType: "DelegateSet",
    Account: treasury,
    Authorize: hot,
    Permissions: mode === "grant" ? [{ Permission: { PermissionValue: "Payment" } }] : [],
    SigningPubKey: publicKey,
  } as DelegateSet);
  const speculos = new Speculos(SPECULOS);
  const action = device.sign(encode(tx));
  let done = false;
  action.result.then(() => (done = true), () => (done = true));
  // Blind signing (DelegateSet is not clear-signable on XRP app 2.8.1) adds warning pages.
  // Record every page; tap a "continue"/"accept" control by its own coordinates, else "next";
  // never tap on a page offering "Back to safety" except the continue control itself.
  type Ev = { text: string; x: number; y: number; w: number; h: number };
  const events = async () =>
    ((await (await fetch(`${SPECULOS}/events?currentscreenonly=true`)).json()) as { events: Ev[] }).events;
  const home = (evs: Ev[]) => evs.some((e) => /this app enables signing/i.test(e.text));
  for (let i = 0; i < 60 && home(await events()); i++) await sleep(250);
  let last = "";
  for (let page = 1; page <= 15 && !done; page++) {
    const evs = await events();
    const text = evs.map((e) => e.text.trim()).join(" | ");
    if (text === last) await sleep(700); // screen text lags; give it a moment before acting again
    if (text !== last) console.log(`[stax] page ${page}: ${text}`);
    last = text;
    if (/hold to sign|accept risk and sign/i.test(text)) {
      await speculos.finger("press", 336, 515);
      await sleep(3000);
      await speculos.finger("release", 336, 515);
      console.log("[tap] hold 3 s");
      for (let i = 0; i < 12 && !done; i++) await sleep(250); // the screen text lags the signature
      continue;
    }
    const go = evs.find((e) => /continue|accept|i understand/i.test(e.text) && !/reject|safety/i.test(e.text));
    if (go) {
      console.log(`[tap] "${go.text.trim()}"`);
      await speculos.finger("press-and-release", Math.round(go.x + Math.min(go.w, 200) / 2), go.y + Math.round(go.h / 2));
    } else if (/back to safety/i.test(text)) {
      console.log("[stax] warning page without a continue control; stopping taps");
      break;
    } else {
      await speculos.finger("press-and-release", 350, 620);
    }
    await sleep(900);
  }
  try {
    const der = await action.result;
    const blob = encode({ ...tx, TxnSignature: Buffer.from(der).toString("hex").toUpperCase() });
    console.log(`signed hash=${hashes.hashSignedTx(blob)}`);
    const res = await client.submitAndWait(blob);
    const meta = res.result.meta as { TransactionResult?: string };
    console.log(`DelegateSet ${mode} result=${meta.TransactionResult} https://testnet.xrpl.org/transactions/${res.result.hash}`);
  } catch (e) {
    console.log(`DelegateSet ${mode} failed: ${(e as Error).message}`);
  }
}
console.log(`account_objects type=delegate: ${JSON.stringify((await delegateObjects(treasury)).account_objects)}`);
await client.disconnect();
process.exit(0);
