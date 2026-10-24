import { describe as suite, expect, it } from "vitest";
import { card, fixture, line, risks } from "./helpers.js";

suite("LoanSet", () => {
  it("real co-signed LoanSet (devnet 90B14608): terms and who has signed", () => {
    const p = card(fixture("devnet", "LoanSet-90B14608"));
    expect(p.summary).toBe("Loan of 60000000 (60 XRP if the vault holds XRP): 3 payments every 90 seconds at 0.5% interest");
    expect(line(p, "Interest rate")?.value).toBe("0.5%");
    expect(line(p, "Grace period")?.value).toBe("1 minute");
    expect(line(p, "Signatures")).toMatchObject({ value: "raB6a7…yZow: signed; rsQ9F4…HgGH: signed" });
    expect(line(p, "Signatures")?.risk).toBeUndefined();
    expect(risks(p)).toEqual([]);
  });
  it("real held-then-approved LoanSet (devnet 135D0B68, demo step 8): the terms the human approves", () => {
    const p = card(fixture("devnet", "LoanSet-135D0B68"));
    expect(p.summary).toBe("Loan of 60000000 (60 XRP if the vault holds XRP): 3 payments every 90 seconds at 8% interest");
    expect(line(p, "Loan broker")?.value).toBe("B4AC8086…632810");
    expect(line(p, "Counterparty")?.value).toBe("rEH59t…egVw");
    expect(line(p, "Principal")?.value).toBe("60000000 (60 XRP if the vault holds XRP)");
    expect(line(p, "Every")?.value).toBe("90 seconds");
    expect(line(p, "Grace period")?.value).toBe("1 minute");
    expect(line(p, "Interest rate")?.value).toBe("8%");
    expect(risks(p)).toEqual([]);
  });
  it("counterparty not signed yet warns (synthetic)", () => {
    const p = card(fixture("synthetic", "LoanSet-unsigned-counterparty"));
    expect(line(p, "Signatures")).toMatchObject({ value: "raB6a7…yZow: not signed yet; rsQ9F4…HgGH: not signed yet", risk: "warn" });
    expect(line(p, "Interest rate")?.value).toBe("50%");
    expect(line(p, "Every")?.value).toBe("30 days");
    expect(risks(p)).toEqual(["warn", "info"]);
  });
});

suite("LoanManage, LoanPay, LoanBrokerSet", () => {
  it("real default (devnet A8DCC893) is danger", () => {
    const p = card(fixture("devnet", "LoanManage-A8DCC893"));
    expect(p.title).toBe("Default loan 6930D229…7A24B2: seize the cover");
    expect(risks(p)).toEqual(["danger"]);
  });
  it("impair warns (synthetic)", () => {
    expect(risks(card(fixture("synthetic", "LoanManage-impair")))).toEqual(["warn"]);
  });
  it("LoanPay (synthetic)", () => {
    expect(card(fixture("synthetic", "LoanPay")).title).toBe("Pay 20.1 XRP toward loan 6930D229…7A24B2");
  });
  it("real LoanBrokerSet (devnet 1C47B8F1): rates in tenths of a basis point", () => {
    const p = card(fixture("devnet", "LoanBrokerSet-1C47B8F1"));
    expect(line(p, "Management fee")?.value).toBe("1%");
    expect(line(p, "Minimum first-loss cover")?.value).toBe("10%");
    expect(risks(p)).toEqual(["info"]);
  });
});

suite("Vault and domain", () => {
  it("real VaultCreate (devnet 47CD2A93) and VaultDeposit (devnet 5F4D7662)", () => {
    expect(card(fixture("devnet", "VaultCreate-47CD2A93")).title).toBe("Create a vault holding XRP");
    expect(card(fixture("devnet", "VaultDeposit-5F4D7662")).title).toBe("Deposit 20 XRP into vault 78926F13…747F79");
  });
  it("VaultWithdraw to another account warns (synthetic)", () => {
    expect(risks(card(fixture("synthetic", "VaultWithdraw")))).toEqual(["warn"]);
  });
  it("PermissionedDomainSet lists accepted credentials (synthetic)", () => {
    expect(line(card(fixture("synthetic", "PermissionedDomainSet")), "Members need one of")?.value).toBe('"x402-merchant" from agent (hot key) (rUPNkA…rm7m)');
  });
});

suite("Batch", () => {
  it("real AllOrNothing batch (devnet 35DF4112): mode in words, inner cards recursive", () => {
    const p = card(fixture("devnet", "Batch-35DF4112"));
    expect(p.title).toBe("Batch of 2 transactions from raB6a7…yZow");
    expect(line(p, "Mode")?.value).toBe("All or nothing: every inner transaction applies, or none does");
    expect(line(p, "#1")?.value).toBe("Send 55 XRP from raB6a7…yZow to rnVJbd…au1b");
    expect(line(p, "#1 Memo (invoice)")?.value).toMatch(/INV-BATCH-1/);
    expect(line(p, "#2 Amount")?.value).toBe("1 XRP");
  });
  it("a dangerous inner transaction surfaces on its summary line; co-signers listed (synthetic)", () => {
    const p = card(fixture("synthetic", "Batch-multi-account"));
    expect(line(p, "Mode")?.value).toMatch(/^Independent/);
    expect(line(p, "#2")?.risk).toBe("danger");
    expect(line(p, "Co-signers")?.value).toBe("rsQ9F4…HgGH");
    expect(risks(p)).toEqual(["info"]);
  });
  it("no mode flag is danger (synthetic)", () => {
    expect(line(card(fixture("synthetic", "Batch-no-mode")), "Mode")?.risk).toBe("danger");
  });
});
