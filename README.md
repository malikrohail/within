<p align="center"><img src="docs/assets/within-logo.png" alt="Within" width="360"></p>

# Within

**Agent spending. Within your rules.**

Within is a policy wallet for AI agents on the XRP Ledger. The paying agent buys APIs over x402 through a wallet URL and never holds a signing key. Six policy checks run before the wallet signs. Eligible payments up to 0.1 XRP auto-sign on a hot key; eligible larger ones wait for review and hold-to-sign in the Ledger XRP app on the Speculos Stax emulator; off-policy requests are refused before anything reaches the ledger. Merchant access uses an on-ledger Credential (or an explicit static allowlist entry), and the agent's direct spending right is a revocable Delegate.

- **Demo video:** https://youtu.be/BD3VG-yo4MM
- **Event:** XRPL Commons AI & Fintech XRP Ledger Hackathon, New York, October 24–25, 2026
- **Track:** Agentic Finance. **Sponsor bounty:** Ledger.
- **Networks:** XRPL testnet (wallet) and devnet (Lending Desk) only. No real funds.

## How it works

The agent pays for APIs over x402 (HTTP 402 pay-per-call) by calling the wallet URL (`http://localhost:7402`). Six checks run in order before signing:

1. Policy expiry
2. Network
3. Asset
4. Merchant access: an accepted Credential inside the wallet's Permissioned Domain, or an explicit static allowlist entry
5. Daily budget
6. Per-payment cap

A request that fails checks 1 to 5 is refused with a reason, and nothing reaches the ledger. A payment up to and including 0.1 XRP auto-signs on the hot key. A larger eligible payment is held: the Ledger XRP app in the Speculos Stax emulator shows it for review, then hold-to-sign. A pending hold expires if it is not approved in time. Rules and order: [docs/CONTRACT.md](docs/CONTRACT.md). Design: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

The treasury grants the agent key a revocable Delegate (`DelegateSet`) for direct Payments. We granted it, revoked it, granted it again and sent a delegated Payment, all on testnet. After a revoke, a delegated Payment returns `terNO_DELEGATE_PERMISSION`.

## What the ledger enforces, what the wallet enforces

| Enforced by | What |
|---|---|
| XRPL ledger | The revocable Delegate: the treasury grants, revokes and re-grants the agent key's right to send Payments; after a revoke, a delegated Payment returns `terNO_DELEGATE_PERMISSION`. Covers direct Payments only. Supplier Payments in a `tfAllOrNothing` Batch apply together or not at all. |
| XRPL ledger state, checked by the wallet | The merchant Credential inside a Permissioned Domain. The wallet also accepts an explicit static allowlist entry. |
| Wallet (server policy, before signing) | Policy expiry, network, asset, daily budget, per-payment cap and hold timeout. Automatic x402 payments sign on the hot key under this software cap. |
| Lending Desk (software) | The Credential and score gate for automatic loans, and the receipt check before the software broker key counter-signs. Neither ledger enforces the link between the two ledgers; the desk does. |

## Proof on the ledger

| Network | What it shows | Transaction |
|---|---|---|
| testnet | Held 5 XRP agent payment, approved in the Ledger Speculos emulator; its account signs | [`F4BFF2ADB2C2C7F2A22F4D91E45BF5D7903443DA2015B5CD68CE78B6591C4589`](https://testnet.xrpl.org/transactions/F4BFF2ADB2C2C7F2A22F4D91E45BF5D7903443DA2015B5CD68CE78B6591C4589) |
| testnet | PermissionedDomainSet: membership is the merchant vetting Credential | [`74C098DAE8010EC40EE684C122012A23B18ACC92C4B0D7CCD09D619041D18DBB`](https://testnet.xrpl.org/transactions/74C098DAE8010EC40EE684C122012A23B18ACC92C4B0D7CCD09D619041D18DBB) |
| testnet | DelegateSet grant: treasury lets the agent key send Payments | [`ED86FFF48E158D52DC963D328E149EE0C5A998D552648B61228D5AF3BD50457D`](https://testnet.xrpl.org/transactions/ED86FFF48E158D52DC963D328E149EE0C5A998D552648B61228D5AF3BD50457D) |
| testnet | DelegateSet revoke | [`1F17133345A14245484127663CF375AE784ADDA0750882DCDC8859AC226EA448`](https://testnet.xrpl.org/transactions/1F17133345A14245484127663CF375AE784ADDA0750882DCDC8859AC226EA448) |
| testnet | DelegateSet re-grant | [`5230ABA2EB1221CE3B4FCCF97AE64E8F4FE1D79D933071B7B87D265ADE8FFCF4`](https://testnet.xrpl.org/transactions/5230ABA2EB1221CE3B4FCCF97AE64E8F4FE1D79D933071B7B87D265ADE8FFCF4) |
| testnet | Delegated Payment after the re-grant: Account = treasury, signed by the agent key | [`203F666CF1896D36EAB17C42F886242EE921C1A7CBE8AE9E0B47708401B30725`](https://testnet.xrpl.org/transactions/203F666CF1896D36EAB17C42F886242EE921C1A7CBE8AE9E0B47708401B30725) |
| testnet | Loan approval Payment signed in Speculos; memos carry the LoanSet hash and the terms "approve loan 30 XRP ... 6 payments" | [`8AC151230EAF1AC6F9928CF3E5A5F25DF2DE6AC2454C76DD6136466987B7919C`](https://testnet.xrpl.org/transactions/8AC151230EAF1AC6F9928CF3E5A5F25DF2DE6AC2454C76DD6136466987B7919C) |
| devnet | Held 30 XRP LoanSet that the approval binds; counter-signed by the software broker key | [`C9627B03199430510F43567C6A93A446116606AC4DA5FAE763BA8FAA6CDDDF13`](https://devnet.xrpl.org/transactions/C9627B03199430510F43567C6A93A446116606AC4DA5FAE763BA8FAA6CDDDF13) |
| devnet | All-or-nothing Batch from that loan: 29 XRP to the supplier, 1 XRP fee | [`6C506E2B9E7B6027C9BBC80E6A75480A1DF2382346567F0BD98E60A540A29DDB`](https://devnet.xrpl.org/transactions/6C506E2B9E7B6027C9BBC80E6A75480A1DF2382346567F0BD98E60A540A29DDB) |
| devnet | LoanSet signed as the borrower by the patched app in Speculos (experiment 011) | [`0CE7AFEF47E0F092CFABBEB78DAD6848B1BE8E5338C5BFB9CCC0804A49B16243`](https://devnet.xrpl.org/transactions/0CE7AFEF47E0F092CFABBEB78DAD6848B1BE8E5338C5BFB9CCC0804A49B16243) |
| devnet | LoanPay signed by the patched app alone (experiment 011) | [`4B531D0B37124F41404EF8AA5359B5A8A433DA8DA507B23E5F6EE134D206644F`](https://devnet.xrpl.org/transactions/4B531D0B37124F41404EF8AA5359B5A8A433DA8DA507B23E5F6EE134D206644F) |
| devnet | Loan default: 12.666667 XRP from the broker's cover, 47.333333 XRP from the vault | [`5777AFE33BA266BD8C898492E18C21A22E3FF25119351BB52F15726632785DF8`](https://devnet.xrpl.org/transactions/5777AFE33BA266BD8C898492E18C21A22E3FF25119351BB52F15726632785DF8) |
| devnet | Sweeper repays with a borrower-signed LoanPay after a simulated income Payment | [`E276E391D2979A899D85CCDADEC9E48101EB94DA7B9A4E724BC4CEF4A584BF75`](https://devnet.xrpl.org/transactions/E276E391D2979A899D85CCDADEC9E48101EB94DA7B9A4E724BC4CEF4A584BF75) |

Refusals happen before the wallet signs or the broker counter-signs, so they leave no transaction; their evidence is the API response and the unchanged balances, recorded in [lending/EVIDENCE.md](lending/EVIDENCE.md).

The build exercised six amendments end to end: Credentials, Permissioned Domains, Permission Delegation, Batch, Single Asset Vault (XLS-65) and the Lending Protocol (XLS-66). Seven XRPL integration findings are in [docs/XRPL_FINDINGS.md](docs/XRPL_FINDINGS.md) and twelve Ledger developer-experience findings in [docs/LEDGER_DX_FEEDBACK.md](docs/LEDGER_DX_FEEDBACK.md); the two lists overlap.

## Honest limits

- Every device signature came from the Speculos emulator. No physical device signed anything.
- The wallet runs on testnet and the desk on devnet, so the loop is stitched across two networks. Loans are in XRP.
- The broker counter-signature uses a software key.
- The score uses public ledger history plus the borrower's own declared outside debt; no bank or credit-bureau data.
- Devnet income is simulated: script-sent, memo-tagged Payments, shown as evidence, not a score weight.
- Automatic x402 payments run on the hot key under a software cap, because the facilitator refuses delegated payments; eligible held payments sign in the Speculos emulator.
- The revocable Delegate covers direct Payments only.
- The wallet listens on localhost only, and the policy file is operator-controlled.
- Agent credit is small today; we built the broker to exercise the protocol.
- No seed is committed; wallet test keys are derived at test time from fixed test entropy.

## Also in the repo

A **Lending Desk** on devnet runs a loan broker on the XRPL Lending Protocol (XLS-66) over a Single Asset Vault (XLS-65): automatic loans need a broker-issued Credential and a sufficient score, eligible larger loans are held, and suppliers are paid in one all-or-nothing Batch. For a held loan, a **one hash, two ledgers** receipt applies: the Speculos emulator signs a 1-drop testnet Payment whose memos carry the SHA-256 of the exact LoanSet the borrower signed and its terms, and the desk is designed to verify the signer, the hash and the terms before its software broker key counter-signs on devnet. Our **XRP app patch** adds the Number reader and lending field labels the stock app 2.8.1 lacks (it rejects a LoanSet with `0x680b`); the app's own suite in Speculos gave 142 passed, 11 skipped, 0 failed, and the patched app signed a LoanSet and a LoanPay that validated on devnet. The patch does not add the counterparty signing prefix, so the broker still signs in software. See [experiment 005](ons/experiments/005-app-xrp-patch/) and [experiment 011](ons/experiments/011-speculos-loanset-devnet/).

## Verify it yourself in sixty seconds

A read-only script fetches the receipt's two public transactions, rebuilds the loan the borrower signed, and checks it against the approval's memos. Run from the repository root (Python 3.10+, needs responsive public XRPL nodes):

```sh
python3 -m venv /tmp/verify-venv
/tmp/verify-venv/bin/pip install -r ons/experiments/014-astra/verify/requirements.txt
/tmp/verify-venv/bin/python -I ons/experiments/014-astra/verify/verify.py --approval 8AC151230EAF1AC6F9928CF3E5A5F25DF2DE6AC2454C76DD6136466987B7919C --loanset C9627B03199430510F43567C6A93A446116606AC4DA5FAE763BA8FAA6CDDDF13
```

Expected last line: **`BINDING PASS`**, exit 0.

Negative control: the same command with `--loanset 0CE7AFEF47E0F092CFABBEB78DAD6848B1BE8E5338C5BFB9CCC0804A49B16243` (experiment 011's LoanSet, which this approval does not bind). Expected: **`BINDING FAIL: digest_match, terms_match`**, exit 1.

PASS means the approval memo equals the SHA-256 of the borrower-signed LoanSet and the terms memo matches the loan (principal, borrower, payment count). It checks one demonstrated pair. It is a binding check, not an authorization check: public data does not prove hardware, human review, or the order in which the desk checks and signs. Details: [the verifier](ons/experiments/014-astra/verify/).

## How this was built and verified

Code was written by AI agents under human direction and review; automation drove the emulator taps.

The checks recorded in this repository:

- **Receipt verifier, public nodes.** The PASS run (exit 0) and the negative control (`BINDING FAIL: digest_match, terms_match`, exit 1), with the verifier's SHA-256 and the timestamp: [verify/RESULT.md](ons/experiments/014-astra/verify/RESULT.md). An earlier run that hit an RPC transport error is kept in [verify/INITIAL-RPC-ERROR.md](ons/experiments/014-astra/verify/INITIAL-RPC-ERROR.md). Offline tests: `ons/experiments/014-astra/verify/test_verify.py`.
- **XRP app patch tests in Speculos.** The app's full standalone suite: 142 passed, 11 skipped, 0 failed. The golden run passed 26 selected tests, and the verify run passed 16 against the new goldens. Results in [005 RESULT.md](ons/experiments/005-app-xrp-patch/RESULT.md); raw logs in `ons/experiments/005-app-xrp-patch/logs/`; screens in `ons/experiments/005-app-xrp-patch/screens/`.
- **Patched app on devnet.** The LoanSet and LoanPay above, re-read from the public devnet node after the run: [011 RESULT.md](ons/experiments/011-speculos-loanset-devnet/RESULT.md).
- **Transactions.** The thirteen hashes in [Proof on the ledger](#proof-on-the-ledger), each linked to its public explorer page. Raw public-node request and response captures of the binding are in [innovation/proof-of-concept/](innovation/proof-of-concept/).
- **Lending runs.** Desk transactions, responses and balances, including refusals: [lending/EVIDENCE.md](lending/EVIDENCE.md). Earlier protocol experiments: [001 RESULT.md](ons/experiments/001-vault-loan-baseline/RESULT.md) and [010 RESULT.md](ons/experiments/010-iou-vault/RESULT.md).
- **Offline test suites** for the wallet, desk, agent, previews, dashboard and verifier; commands under [Run it locally](#run-it-locally).

Disclosure: an x402 client and Ledger DMK signing on the emulator were proven in separate spikes before the event and reused, not claimed. This repository is a curated export; the original build history starts at 02:24 EDT on 24 October 2026, before the doors opened.

## Run it locally

You need Node 22, Python 3.12+, and Docker for the Speculos emulator. [docs/RUNBOOK.md](docs/RUNBOOK.md) covers Speculos, one-time setup and the demo checklist.

```bash
# one-time setup
(cd wallet && npm ci && npm run setup)
(cd dashboard && npm ci)
(cd agent && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt)

wallet/bin/up.sh                                    # wallet :7402, merchants :8001/:8002, dashboard :5174
(cd agent && .venv/bin/python scripts/vet_merchant.py)   # once: vets the good merchant on the ledger
# until vet_merchant.py has run once, up.sh shows ✗ allowlist and exits 1; rerun up.sh after
(cd agent && .venv/bin/python demo.py --scripted)   # five purchases: auto, held, refused; approve step 4 in the Speculos emulator (start it before this, see RUNBOOK)
(cd lending && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/python setup.py)
(cd lending && .venv/bin/python -m desk)            # desk :7500; UI :5175 via cd lending/ui && npm install && npm run dev
```

Tests (offline): `cd wallet && npm ci && npm test`, `cd lending && .venv/bin/python -m pytest -q -m "not network"`, `cd agent && .venv/bin/python -m pytest -q -m "not network"`, `cd preview && npm ci && npm test`, `cd dashboard && npm ci && npx vitest run`, `cd ons/experiments/014-astra/verify && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/python -I test_verify.py`.

## Repository map

- `wallet/`: the Policy Wallet service (TypeScript): policy rules, hot key, Speculos signing over the Ledger Device Management Kit.
- `agent/`: the paying agent and two demo merchants (one vetted, one rogue).
- `dashboard/`: the wallet UI: treasury money-flow graph, pay feed, vetting and permissions.
- `preview/`: readable signing previews for 19 XRPL transaction types, 13 of them amendment-era.
- `lending/`: the Lending Desk: underwriting policy, approval check (`lending/auth.py`), sweeper, UI.
- `innovation/proof-of-concept/`: raw public-node captures of the one-hash, two-ledgers binding.
- `ons/experiments/005-app-xrp-patch/`: the XRP app patch that adds the lending fields, with test logs and screens.
- `ons/experiments/011-speculos-loanset-devnet/`: the patched app signs a LoanSet and a LoanPay that validate on devnet.
- `ons/experiments/014-astra/verify/`: the standalone binding verifier and its offline tests.
- `ons/experiments/001-vault-loan-baseline/`, `010-iou-vault/`: earlier lending experiments.
- `ons/branding/`: the Within logo, brand strings and design tokens.
- `playground/`: a separate, flag-gated 'be the agent' demo on devnet (not part of the submission flow).
- `docs/`: the [documentation index](docs/README.md), runbook, architecture, policy contract, application-preview format and findings.

## Team

Team Axesec: Malik Salim and Ons Ali.
