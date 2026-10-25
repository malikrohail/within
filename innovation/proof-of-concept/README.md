# Proof of concept: a Ledger-signed approval bound to an XLS-66 loan, from public data only

Captured 2026-10-24 from the public XRPL nodes. Every file here is the exact JSON-RPC request we sent and the exact response the node returned. Nothing was edited. Re-run `rpc_capture.py` to regenerate all of it.

## The claim

A Ledger device (Speculos Stax emulator, stock XRP app 2.8.1) signed a 1-drop testnet Payment whose memo is the SHA-256 of the borrower-signed `LoanSet`. Our desk then co-signed that exact `LoanSet` on devnet. The two are bound by the hash, and anyone can check it from the two ledgers without trusting us.

## Files

| File | What it is |
|---|---|
| `01-testnet-approval-payment.request.json` / `.response.json` | `tx` call on testnet for `8AC15123…7919C`: the approval Payment signed by the treasury account `rUGeRsKj…VQ6B`, 1 drop, two memos (`loan-approval` = hash, `loan-terms` = plain text), no `Delegate` |
| `02-devnet-loanset.request.json` / `.response.json` | `tx` call on devnet for `C9627B03…DF13`: the `LoanSet`, borrower `rBZQ4Z23…`, counterparty broker `rEH59te…`, 30,000,000 drops, 6 payments, `CounterpartySignature` present |
| `03-devnet-batch.request.json` / `.response.json` | `tx` call on devnet for `6C506E2B…9DDB`: the `tfAllOrNothing` Batch that paid the supplier 29 XRP and the broker 1 XRP from the loan |
| `04-binding-check.json` | The derived check: the `loan-approval` memo equals SHA-256 of the borrower-signed blob rebuilt from the validated `LoanSet`, and the `loan-terms` memo equals the terms derived from the same `LoanSet` |
| `rpc_capture.py` | Fetches the three transactions, writes the files above, rebuilds the blob (validated `LoanSet` minus `CounterpartySignature` and ledger metadata, canonical binary encoding via xrpl-py) and compares |

## How the binding check works

1. Take the validated `LoanSet` JSON from devnet.
2. Remove `CounterpartySignature` and the node-added fields (`hash`, `meta`, `ledger_index`, `validated`, `date`, …). What remains is exactly what the borrower signed before the broker added its signature.
3. Encode it with the canonical XRPL binary codec and hash it: `SHA-256 = 70C795FC…E646`.
4. Read the `loan-approval` memo on the testnet Payment: `70C795FC…E646`. Equal.
5. Read the `loan-terms` memo: `approve loan 30 XRP to rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG 6 payments`. Equal to the terms derived from the `LoanSet` (`PrincipalRequested` / 1,000,000, `Account`, `PaymentTotal`).

This check was also done independently by a reviewer who did not run our system (2026-10-24 ~18:50 ET) with the same result.

## What this proves, and what it does not

- Proves: the device-signed approval is cryptographically tied to one specific loan and its terms, both visible on public ledgers. The device never had to parse a `LoanSet`.
- Proves: the loan's `CounterpartySignature` was produced by the broker key, which our desk software holds. The approval Payment's ledger closed 9 seconds before the `LoanSet`'s ledger (testnet `date` 846194861, devnet `date` 846194870).
- Does not prove: that the desk checked the approval before it countersigned. Hash equality and close times cannot show the desk's internal order; that comes from the desk source (`lending/`) and the run log for lr_0030, not from the public ledgers.
- Does not prove: a physical Ledger device (this is the Speculos emulator). Does not prove an on-ledger link between the two networks; the desk enforces that link.

## The second finding: the XRP app cannot sign a `LoanSet` (fixed in a patch)

Stock XRP app 2.8.1 answers APDU `0x680b` to a `LoanSet` because its parser has no reader for the `Number` type (`PrincipalRequested`). Root cause, evidence chain and the patch: `../../ons/experiments/005-app-xrp-patch/RESULT.md` (section 1 root cause, section 7 Speculos run: 142 passed, 11 skipped, 0 failed on the app's own ragger suite; 89 screenshots; raw logs in `logs/`). The write-up for Ledger: `../../docs/LEDGER_DX_FEEDBACK.md` finding 12. The patch does not add the counterparty signing prefix (`CPT\0`), so a device still cannot be the loan's counterparty; that is why the approval-Payment bridge above exists.
