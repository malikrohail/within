// DO NOT RUN against the shared Speculos: on XRP app 2.8.1 the LoanSet APDU returns 0x680b and the
// emulator exits (code 255), taking the demo device down (docs/LEDGER_DX_FEEDBACK.md finding 12). Kept as the reproducer.
// Counterparty spike: can the Ledger (XRP app on Speculos, via device-signer-kit-xrp) produce the
// CounterpartySignature of an XLS-66 LoanSet? Devnet only. Needs Speculos to itself: stop scripts/run.sh first.
//   npx tsx scripts/spike-counterparty.ts
// The borrower (first party) is a throwaway key that is never funded, so neither submission can apply;
// the point is which signature check each one fails. A control copy is counterparty-signed by a software
// key with xrpl.js signLoanSetByCounterparty, so the two rippled verdicts can be compared.
import { Client, Wallet, decode, encode, encodeForSigning, signLoanSetByCounterparty, type LoanSet } from "xrpl";
import { encodeForSigningCounterparty } from "ripple-binary-codec";
import { verify } from "ripple-keypairs";
import { LedgerDevice } from "../src/device.js";
import { Speculos, drainSpeculosResponses } from "../src/speculos.js";

const WSS = "wss://s.devnet.rippletest.net:51233";
const SPECULOS = process.env.SPECULOS_URL ?? "http://127.0.0.1:5000";
// The lending desk's devnet loan broker (lending/accounts.json loanBrokerId); read only.
const LOAN_BROKER_ID = "B4AC8086C7D4197BEBCE2C0B692B2EE0501E0F5D53E85F7076B069D8CB632810";
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
const hex = (b: Uint8Array) => Buffer.from(b).toString("hex").toUpperCase();

const client = new Client(WSS);
await client.connect();
const { result: info } = await client.request({ command: "ledger_current" } as never) as { result: { ledger_current_index: number } };

/** A LoanSet from a throwaway borrower, first-party signed, with `counterparty` named as the broker side. */
const loanSet = (borrower: Wallet, counterparty: string): LoanSet => {
  const tx = {
    TransactionType: "LoanSet",
    Account: borrower.classicAddress,
    Counterparty: counterparty,
    LoanBrokerID: LOAN_BROKER_ID,
    PrincipalRequested: "1000000",
    InterestRate: 8000,
    PaymentTotal: 3,
    PaymentInterval: 90,
    GracePeriod: 60,
    Fee: "30",
    Sequence: 1,
    LastLedgerSequence: info.ledger_current_index + 20,
  } as LoanSet;
  return decode(borrower.sign(tx).tx_blob) as unknown as LoanSet;
};

const submit = async (label: string, blob: string) => {
  try {
    const r = (await client.request({ command: "submit", tx_blob: blob } as never)) as { result: Record<string, unknown> };
    console.log(`${label}: engine_result=${r.result.engine_result} message=${JSON.stringify(r.result.engine_result_message)}`);
  } catch (e) {
    const d = (e as { data?: Record<string, unknown> }).data;
    console.log(`${label}: error=${d?.error} message=${JSON.stringify(d?.error_exception ?? d?.error_message ?? (e as Error).message)}`);
  }
};

// Control: a software counterparty signs with xrpl.js (CPT\0 prefix under fixCleanup3_4_0).
const ctrlBorrower = Wallet.generate();
const ctrlCounterparty = Wallet.generate();
const ctrl = signLoanSetByCounterparty(ctrlCounterparty, loanSet(ctrlBorrower, ctrlCounterparty.classicAddress));
await submit("control (xrpl.js counterparty)", ctrl.tx_blob);

// Device: the Ledger signs the same signing fields; the XRP app adds its own prefix.
drainSpeculosResponses(SPECULOS);
const device = new LedgerDevice(SPECULOS, (m) => console.log(`[device] ${m}`));
device.start();
for (let i = 0; i < 40 && !device.status().connected; i++) await sleep(500);
const { address: deviceAddress, publicKey } = device.status();
if (!deviceAddress || !publicKey) throw new Error("device not connected");
console.log(`device=${deviceAddress} pub=${publicKey}`);

const tx = loanSet(Wallet.generate(), deviceAddress);
// The counterparty signs the signing fields: everything but the first party's TxnSignature.
const { TxnSignature: _first, ...unsigned } = tx as LoanSet & { TxnSignature?: string };
const appInput = encode(unsigned); // the XRP app expects encode(), it adds the prefix itself
const speculos = new Speculos(SPECULOS);
const action = device.sign(appInput);
let done = false;
action.result.then(() => (done = true), () => (done = true));
await speculos.approve((m) => console.log(`[tap] ${m}`), () => done);
let der: string;
try {
  der = hex(await action.result);
} catch (e) {
  console.log(`device sign failed: ${(e as Error).message}`);
  await client.disconnect();
  process.exit(0);
}
console.log(`device DER signature ${der.slice(0, 16)}… (${der.length / 2} bytes)`);
const stx = encodeForSigning(unsigned);
const cpt = encodeForSigningCounterparty(unsigned as never);
console.log(`signing data prefixes: STX=${stx.slice(0, 8)} CPT=${cpt.slice(0, 8)} (rest identical: ${stx.slice(8) === cpt.slice(8)})`);
console.log(`verify(device sig, STX\\0 data) = ${verify(stx, der, publicKey)}`);
console.log(`verify(device sig, CPT\\0 data) = ${verify(cpt, der, publicKey)}`);
const withDevice = encode({ ...tx, CounterpartySignature: { SigningPubKey: publicKey, TxnSignature: der } } as LoanSet);
await submit("device counterparty", withDevice);
await client.disconnect();
process.exit(0);
