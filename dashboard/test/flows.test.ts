import { describe, expect, it } from "vitest";
import { cacheKey, flowsFromRequests, flowsFromTx, isIncident, latestRun, type Flow, type TxContext } from "../src/tower/flows";

const BORROWER = "rBorrowerXXXXXXXXXXXXXXXXXXXXXXXXX";
const BROKER = "rBrokerXXXXXXXXXXXXXXXXXXXXXXXXXXX";
const ctx: TxContext = {
  network: "devnet",
  roleOf: (a) => (a === BORROWER ? "borrower" : a === BROKER ? "broker" : undefined),
  vaultNode: () => "vault:759B77BB",
};
const payment = (extra: Record<string, unknown>) => ({
  TransactionType: "Payment",
  Account: BORROWER,
  Destination: BROKER,
  Amount: "1000000",
  ...extra,
});

describe("flowsFromTx", () => {
  it("gives no flows for a Batch, even with tesSUCCESS outer and payment legs inside", () => {
    // Shape of the rolled-back devnet drill 43E561E9: the legs never applied.
    const batch = {
      TransactionType: "Batch",
      Account: BORROWER,
      Flags: 0x00010000,
      RawTransactions: [
        { RawTransaction: payment({ Amount: "241666570", Flags: 0x40000000, SigningPubKey: "" }) },
        { RawTransaction: payment({ Flags: 0x40000000, SigningPubKey: "" }) },
      ],
    };
    expect(flowsFromTx(batch, "43E561E9", undefined, ctx)).toEqual([]);
  });

  it("tags an applied inner Batch leg (tfInnerBatchTxn) as batch", () => {
    const [f] = flowsFromTx(payment({ Flags: 0x40000000, SigningPubKey: "" }), "E8617603", undefined, ctx);
    expect(f).toMatchObject({ id: "E8617603", from: BORROWER, to: BROKER, drops: 1000000, note: "batch" });
  });

  it("leaves a plain Payment untagged", () => {
    const [f] = flowsFromTx(payment({ Flags: 0 }), "8B84B5C2", undefined, ctx);
    expect(f.note).toBeUndefined();
  });
});

const flow = (id: string, network: Flow["network"], minutes: number, extra: Partial<Flow> = {}): Flow => ({
  id, network, from: "a", to: "b", drops: 1, amount: "1 drop", kind: "auto", hash: id, ts: minutes * 60_000, ...extra,
});

describe("Latest run", () => {
  it("anchors each network to its own newest flow, not the clock", () => {
    const flows = [flow("t-old", "testnet", 0), flow("t-new", "testnet", 100), flow("t-run", "testnet", 90), flow("d-new", "devnet", 30), flow("d-old", "devnet", 10)];
    expect(latestRun(flows).map((f) => f.id).sort()).toEqual(["d-new", "t-new", "t-run"]);
  });

  it("treats device and RPC failures as incidents, keeps policy refusals and denials", () => {
    const rows = [
      { id: "1", status: "refused", reason: "merchant_not_credentialed", merchant: "m", amountDrops: "1000", ts: "2026-10-24T10:00:00Z" },
      { id: "2", status: "refused", reason: "device_unavailable", merchant: "m", amountDrops: "1", ts: "2026-10-24T10:01:00Z", kind: "lend" },
      { id: "3", status: "refused", reason: "denied_on_device", merchant: "m", amountDrops: "1", ts: "2026-10-24T10:02:00Z", kind: "lend" },
      { id: "4", status: "refused", reason: "rpc_error", merchant: "m", amountDrops: "1", ts: "2026-10-24T10:03:00Z" },
    ] as unknown as Parameters<typeof flowsFromRequests>[0];
    const refusals = flowsFromRequests(rows, "rAgent", "rTreasury");
    expect(refusals.filter(isIncident).map((f) => f.id)).toEqual(["2", "4"]);
    expect(refusals.filter((f) => !isIncident(f)).map((f) => f.id)).toEqual(["1", "3"]);
  });

  it("keys the cache by network and the exact account set, in any order", () => {
    expect(cacheKey("devnet", ["rB", "rA"])).toBe(cacheKey("devnet", ["rA", "rB"]));
    expect(cacheKey("devnet", ["rA", "rB"])).not.toBe(cacheKey("devnet", ["rA", "rC"]));
    expect(cacheKey("testnet", ["rA"])).not.toBe(cacheKey("devnet", ["rA"]));
  });
});

