import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync } from "node:fs";
import { homedir } from "node:os";
import { describe, expect, it } from "vitest";
import { decode, ECDSA, Wallet, type Payment } from "xrpl";
import { HotKey } from "../src/hot.js";
import { basePayment, buildPayment, FACILITATOR_MEMO_TYPE, type Ledger } from "../src/payment.js";
import type { Requirements } from "../src/types.js";

const hex = (s: string) => Buffer.from(s, "utf8").toString("hex").toUpperCase();
const unhex = (h: string) => Buffer.from(h, "hex").toString("utf8");
const ACCOUNT = "rUGeRsKjpnDVAi1uJYhAxWXbETC917VQ6B";
const MERCHANT = "rPT1Sjq2YGrBMTttX4GZHjKu9dyfzbpAYe";
const LEDGER = 1_000_000;

const req = (extra: Record<string, unknown> = {}, over: Partial<Requirements> = {}): Requirements => ({
  scheme: "exact",
  network: "xrpl:1",
  amount: "1000",
  asset: "XRP",
  payTo: MERCHANT,
  maxTimeoutSeconds: 600,
  extra: { invoiceId: "4CDF07BC-inv-1", sourceTag: 20260601, ...extra },
  ...over,
});

const fakeLedger = (over: Partial<{ networkId: number; fee: string }> = {}): Ledger => ({
  validatedLedgerIndex: async () => LEDGER,
  networkId: async () => over.networkId ?? 1,
  autofill: async (tx: Payment) => ({ ...tx, Fee: over.fee ?? "12", Sequence: 42 }),
});

describe("basePayment", () => {
  it("builds the exact field set", () => {
    const tx = basePayment(req(), ACCOUNT, LEDGER);
    expect(tx).toEqual({
      TransactionType: "Payment",
      Account: ACCOUNT,
      Destination: MERCHANT,
      Amount: "1000",
      Memos: [{ Memo: { MemoData: hex("4CDF07BC-inv-1") } }],
      InvoiceID: createHash("sha256").update("4CDF07BC-inv-1").digest("hex").toUpperCase(),
      LastLedgerSequence: LEDGER + 122,
      SourceTag: 20260601,
    });
  });

  it("LastLedgerSequence = ledger + ceil(maxTimeoutSeconds/5) + 2", () => {
    expect(basePayment(req({}, { maxTimeoutSeconds: 600 }), ACCOUNT, LEDGER).LastLedgerSequence).toBe(LEDGER + 122);
    expect(basePayment(req({}, { maxTimeoutSeconds: 61 }), ACCOUNT, LEDGER).LastLedgerSequence).toBe(LEDGER + 13 + 2);
  });

  it("carries SourceTag and DestinationTag as ints, Amount as a drops string", () => {
    const tx = basePayment(req({ sourceTag: "7", destinationTag: "99" }, { amount: "0050000" }), ACCOUNT, LEDGER);
    expect(tx.SourceTag).toBe(7);
    expect(tx.DestinationTag).toBe(99);
    expect(tx.Amount).toBe("50000");
    expect(() => basePayment(req({ sourceTag: "x" }), ACCOUNT, LEDGER)).toThrow(/sourceTag/);
  });

  it("omits DestinationTag and SourceTag when absent", () => {
    const tx = basePayment(req({ sourceTag: undefined }), ACCOUNT, LEDGER);
    expect("SourceTag" in tx).toBe(false);
    expect("DestinationTag" in tx).toBe(false);
  });

  it("requires extra.invoiceId", () => {
    expect(() => basePayment(req({ invoiceId: undefined }), ACCOUNT, LEDGER)).toThrow("invoice_id_required");
    expect(() => basePayment({ ...req(), extra: undefined }, ACCOUNT, LEDGER)).toThrow("invoice_id_required");
  });

  it("adds the facilitator memo only for a non-empty id, keys id,name,sourceTag", () => {
    expect(basePayment(req({ facilitator: { id: "  " } }), ACCOUNT, LEDGER).Memos).toHaveLength(1);
    expect(basePayment(req({ facilitator: { name: "t54" } }), ACCOUNT, LEDGER).Memos).toHaveLength(1);

    const tx = basePayment(req({ facilitator: { sourceTag: 1, name: " T54 ", id: " t54-testnet ", evil: 1 } }), ACCOUNT, LEDGER);
    expect(tx.Memos).toHaveLength(2);
    const m = tx.Memos![1].Memo;
    expect(m.MemoType).toBe(hex(FACILITATOR_MEMO_TYPE));
    expect(unhex(m.MemoType!)).toBe("urn:x402:facilitator");
    expect(unhex(m.MemoFormat!)).toBe("application/json");
    expect(unhex(m.MemoData!)).toBe('{"id":"t54-testnet","name":"T54","sourceTag":20260601}');

    const noName = basePayment(req({ facilitator: { id: "f", name: "" }, sourceTag: undefined }), ACCOUNT, LEDGER);
    expect(unhex(noName.Memos![1].Memo.MemoData!)).toBe('{"id":"f"}');
  });
});

describe("buildPayment", () => {
  it("autofills and keeps LastLedgerSequence from the validated ledger", async () => {
    const tx = await buildPayment(fakeLedger(), req(), ACCOUNT);
    expect(tx).toMatchObject({ Fee: "12", Sequence: 42, LastLedgerSequence: LEDGER + 122 });
  });
  it("sets SigningPubKey in uppercase for the device path", async () => {
    const tx = await buildPayment(fakeLedger(), req(), ACCOUNT, "02abcdef");
    expect(tx.SigningPubKey).toBe("02ABCDEF");
  });
  it("rejects a fee above 10000 drops", async () => {
    await expect(buildPayment(fakeLedger({ fee: "10001" }), req(), ACCOUNT)).rejects.toThrow("fee_exceeds_payer_policy");
    await expect(buildPayment(fakeLedger({ fee: "10000" }), req(), ACCOUNT)).resolves.toBeTruthy();
  });
  it("rejects an RPC on the wrong network", async () => {
    await expect(buildPayment(fakeLedger({ networkId: 0 }), req(), ACCOUNT)).rejects.toThrow("rpc_network_mismatch");
  });
});

// Byte-for-byte parity with the real Python payer, when its venv is on this machine.
// Throwaway test keys derived from fixed entropy, so no seed literal lives in the repo.
const testSeed = (n: number, algorithm = ECDSA.secp256k1) => Wallet.fromEntropy(new Uint8Array(16).fill(n), { algorithm }).seed!;
const PY = `${homedir()}/xrp/x402-lab/.venv/bin/python`;
describe.skipIf(!existsSync(PY))("parity with x402_xrpl prepare_payment", () => {
  const cases: Record<string, Record<string, unknown>> = {
    "plain invoice + sourceTag": {},
    "facilitator memo + destinationTag": { facilitator: { id: "t54", name: "T54 Facilitator" }, destinationTag: 12345 },
    "non-ASCII facilitator name": { facilitator: { id: "f", name: "Café ✓" } },
  };
  for (const seed of [testSeed(1), testSeed(3, ECDSA.ed25519)]) {
    for (const [name, extra] of Object.entries(cases)) {
      it(`${name} (${seed.startsWith("sEd") ? "ed25519" : "secp256k1"})`, async () => {
        const r = req(extra);
        const hot = new HotKey(seed);
        const ours = hot.sign(await buildPayment(fakeLedger(), r, hot.address)).blob;
        const theirs = execFileSync(PY, [new URL("./fixtures/py_prepare.py", import.meta.url).pathname,
          JSON.stringify({ seed, req: r, ledger: LEDGER, fee: "12", sequence: 42 })], { encoding: "utf8" }).trim();
        expect(decode(ours)).toEqual(decode(theirs));
        expect(ours).toBe(theirs);
      });
    }
  }
});
