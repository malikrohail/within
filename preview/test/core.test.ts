import { describe as suite, expect, it } from "vitest";
import { describe } from "../src/index.js";
import { card, fixture, line, risks } from "./helpers.js";

suite("Payment", () => {
  it("real x402 payment (testnet D49DBB58): invoice memo matched to InvoiceID", () => {
    const p = card(fixture("testnet", "Payment-D49DBB58"));
    expect(p.title).toBe("Pay 5 XRP to good merchant (rwKL4B…VpCa)");
    expect(line(p, "From")?.value).toBe("treasury (Ledger) (rUGeRs…VQ6B)");
    expect(line(p, "x402 invoice")?.value).toBe("88014CEBCFA64B069E504AFD437194BE (matches InvoiceID)");
    expect(line(p, "Network fee")?.value).toBe("0.000012 XRP");
  });
  it("real x402 payment with the facilitator memo (testnet 3A9A18D0)", () => {
    const p = card(fixture("testnet", "Payment-3A9A18D0"));
    expect(line(p, "x402 facilitator")?.value).toMatch(/^\{"id":/);
    expect(line(p, "x402 invoice")?.value).toMatch(/\(matches InvoiceID\)$/);
  });
  it("real delegated treasury payment (testnet 203F666C): says a delegate signs", () => {
    const p = card(fixture("testnet", "Payment-203F666C"));
    expect(line(p, "Signed by delegate")?.value).toBe("agent (hot key) (rUPNkA…rm7m)");
    expect(p.lines.find((l) => l.label === "Risk")?.value).toMatch(/this account pays, but the delegate's key signs/);
  });
  it("an invoice memo that does not hash to InvoiceID is not called x402 (synthetic)", () => {
    const p = describe({ TransactionType: "Payment", Account: "rA", Destination: "rB", Amount: "1", InvoiceID: "00".repeat(32), Memos: [{ Memo: { MemoData: "616263" } }] });
    expect(line(p, "x402 invoice")).toBeUndefined();
    expect(line(p, "Memo")?.value).toBe("abc");
  });
  it("IOU and MPT amounts, partial payment warn (synthetic)", () => {
    expect(card(fixture("synthetic", "Payment-IOU")).title).toBe("Pay 12.5 USD (issuer agent (hot key) (rUPNkA…rm7m)) to good merchant (rwKL4B…VpCa)");
    expect(line(card(fixture("synthetic", "Payment-MPT")), "Amount")?.value).toBe("100 MPT 0000012F…ED47");
    expect(risks(card(fixture("synthetic", "Payment-partial")))).toEqual(["warn"]);
  });
});

suite("DelegateSet (the Stax shows 'Transaction Type: Unknown' and 'Unknown [1]: 1')", () => {
  it("real grant (testnet ED86FFF4) names the permission", () => {
    const p = card(fixture("testnet", "DelegateSet-ED86FFF4"));
    expect(p.title).toBe("Let agent (hot key) (rUPNkA…rm7m) sign Payment for treasury (Ledger) (rUGeRs…VQ6B)");
    expect(line(p, "Permissions")?.value).toBe("Payment");
    expect(risks(p)).toEqual(["warn"]);
  });
  it("real revoke (testnet 1F171333): empty list reads as revoking everything", () => {
    const p = card(fixture("testnet", "DelegateSet-1F171333"));
    expect(p.title).toBe("Revoke every permission delegated to agent (hot key) (rUPNkA…rm7m)");
    expect(p.lines.find((l) => l.label === "Risk")?.value).toMatch(/^Revokes every permission/);
    expect(p.lines.some((l) => l.value === "missing")).toBe(false);
  });
});

suite("Credentials", () => {
  it("real CredentialCreate (testnet 01F93247): type decoded, no-expiry info", () => {
    const p = card(fixture("testnet", "CredentialCreate-01F93247"));
    expect(p.title).toMatch(/^Vouch for r\w+…\w+ as "x402-merchant"$/);
    expect(line(p, "Issuer")?.value).toBe("agent (hot key) (rUPNkA…rm7m)");
    expect(risks(p)).toEqual(["info"]);
  });
  it("real CredentialAccept (testnet F6993225)", () => {
    const p = card(fixture("testnet", "CredentialAccept-F6993225"));
    expect(p.title).toBe('Accept the "x402-merchant" credential from agent (hot key) (rUPNkA…rm7m)');
    expect(line(p, "Subject")?.value).toBe("good merchant (rwKL4B…VpCa)");
  });
  it("real CredentialDelete (testnet 74793D7E) warns", () => {
    const p = card(fixture("testnet", "CredentialDelete-74793D7E"));
    expect(p.title).toMatch(/^Delete the "x402-merchant" credential of /);
    expect(risks(p)).toEqual(["warn"]);
  });
});

suite("account control (synthetic)", () => {
  it("AccountSet asfDisableMaster is danger", () => {
    const p = card(fixture("synthetic", "AccountSet-disable-master"));
    expect(line(p, "Turn on")).toMatchObject({ value: "DISABLE MASTER KEY", risk: "danger" });
    expect(risks(p)).toEqual(["danger", "danger"]);
  });
  it("any AccountSet carries a danger line; Domain decoded", () => {
    const p = card(fixture("synthetic", "AccountSet-domain"));
    expect(line(p, "Domain")?.value).toBe("example.com");
    expect(risks(p)).toEqual(["danger"]);
  });
  it("SignerListSet lists signers and weights; quorum 0 deletes", () => {
    const p = card(fixture("synthetic", "SignerListSet"));
    expect(p.title).toBe("Replace the signer list of treasury (Ledger) (rUGeRs…VQ6B) (quorum 2)");
    expect(line(p, "Signers")?.value).toBe("agent (hot key) (rUPNkA…rm7m) (weight 1), good merchant (rwKL4B…VpCa) (weight 1)");
    expect(risks(p)).toEqual(["danger"]);
    expect(card(fixture("synthetic", "SignerListSet-delete")).title).toBe("Delete the signer list of treasury (Ledger) (rUGeRs…VQ6B)");
  });
});

suite("Escrow (synthetic)", () => {
  it("EscrowCreate: times as ISO + relative, no warn when CancelAfter is set", () => {
    const p = card(fixture("synthetic", "EscrowCreate"));
    expect(p.title).toBe("Lock 10 XRP in escrow for good merchant (rwKL4B…VpCa)");
    expect(line(p, "Can release after")?.value).toBe("2026-10-24T23:33:20Z (in 10 hours)");
    expect(risks(p)).toEqual([]);
  });
  it("condition and no CancelAfter both warn", () => {
    expect(risks(card(fixture("synthetic", "EscrowCreate-condition")))).toEqual(["warn", "warn"]);
  });
  it("EscrowFinish / EscrowCancel", () => {
    expect(card(fixture("synthetic", "EscrowFinish")).title).toBe("Release escrow 7 of treasury (Ledger) (rUGeRs…VQ6B)");
    expect(card(fixture("synthetic", "EscrowCancel")).title).toBe("Cancel escrow 7 of treasury (Ledger) (rUGeRs…VQ6B)");
  });
});

suite("engine", () => {
  it("unknown type is a danger card", () => {
    const p = describe({ TransactionType: "Frobnicate", Account: "rUGeRsKjpnDVAi1uJYhAxWXbETC917VQ6B" });
    expect(p.title).toBe("Unrecognised transaction type");
    expect(p.lines[0].risk).toBe("danger");
  });
});
