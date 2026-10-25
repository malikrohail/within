# Within documentation

Within is a policy wallet for AI agents on XRPL. The paying agent buys APIs over x402 through a wallet URL and never holds a signing key. Six policy checks run before the wallet signs. Eligible small payments sign on a hot key; eligible larger payments wait for approval in the Speculos emulator running the Ledger XRP app; off-policy requests are refused. A Lending Desk underwrites XLS-66 loans on devnet, and an XRP app patch lets the emulator display the lending fields before signing.

This page is the index. Each section names its audience, the pages to read, and the commands that reproduce the result. Everything here runs against XRPL testnet or devnet. Nothing touches mainnet or real funds.

| Audience | Start with |
|---|---|
| Anyone | [Verify the approval receipt in sixty seconds](../README.md#verify-it-yourself-in-sixty-seconds) |
| Wallet and x402 integrators | [Policy Wallet](#policy-wallet) |
| XLS-65 / XLS-66 developers | [Lending Desk](#lending-desk) and [The approval receipt](#the-approval-receipt) |
| Ledger embedded-app and Ledger Live engineers | [Ledger XRP app patch](#ledger-xrp-app-patch) and [Application previews](#application-previews) |
| Reviewers | [Evidence](#evidence) and [Limits](#limits) |

## Running the system

| Page | What it covers |
|---|---|
| [README](../README.md) | Overview, the sixty-second receipt check, one-time setup, repository map |
| [RUNBOOK](RUNBOOK.md) | Speculos emulator, start and stop scripts, the five-purchase demo, useful checks |
| [ARCHITECTURE](ARCHITECTURE.md) | Process diagram and the three invariants |

Prerequisites: Node 22, Python 3.12 or newer, Docker for the Speculos emulator (Ledger Stax, XRP app 2.8.1). Ports used:

| Process | Port | Network |
|---|---|---|
| Policy Wallet API (`wallet/`) | 7402 | testnet |
| Good merchant, rogue merchant (`agent/`) | 8001, 8002 | testnet |
| Wallet dashboard (`dashboard/`) | 5174 | |
| Speculos emulator REST API | 5000 | |
| Lending Desk API (`lending/`) | 7500 | devnet |
| Lending Desk UI (`lending/ui`) | 5175 | |

Offline test suites: `wallet` (`npm test`), `preview` (`npm test`), `dashboard` (`npx vitest run`), `agent` and `lending` (`pytest -m "not network"`), and the verifier (`test_verify.py`). The README lists the exact commands.

## Policy Wallet

The wallet is a Node service. It holds the hot key and the Ledger Device Management Kit session; the agent holds only `http://localhost:7402`.

| Page | What it covers |
|---|---|
| [CONTRACT](CONTRACT.md) | The HTTP API: `POST /v1/pay`, `GET /v1/requests`, device-tap and deny helpers, `GET`/`PUT /v1/policy`, `GET /v1/status`; how the x402 Payment is built; the dashboard and demo-agent behaviour |
| [wallet/README](../wallet/README.md) | Setup, start, test, environment variables |
| [agent/README](../agent/README.md) | The paying agent, the two demo merchants, merchant vetting on the ledger |
| [dashboard/README](../dashboard/README.md) | The wallet UI |

The six checks, in the order the code runs them (`wallet/src/policy.ts`):

1. Policy expiry, when `expiresAt` is configured: refuse `policy_expired`.
2. Network not in `allowedNetworks`: refuse `network_not_allowed`.
3. Asset not in `allowedAssets`: refuse `asset_not_allowed`.
4. Merchant neither in the static `allowedMerchants` list nor holding an accepted, unexpired Credential from the wallet's issuer: refuse `merchant_not_credentialed`.
5. Amount plus today's spend above `dailyBudgetDrops`: refuse `daily_budget_exceeded`.
6. Amount above `perTxCapDrops`: hold for emulator approval. Otherwise auto-sign on the hot key.

`POST /v1/pay` is synchronous. A held request blocks until the emulator approves, the operator denies, or `holdTimeoutSeconds` passes. A policy refusal is an HTTP 403 with the reason, returned before the wallet signs. A hold that times out returns 408, and a hold with no emulator connected returns 503. The merchant allowlist is ledger state: a Credential inside a Permissioned Domain, plus a static override list. The agent's direct spending right is a `DelegateSet` the treasury grants and revokes; after a revoke a delegated Payment returns `terNO_DELEGATE_PERMISSION`.

## Lending Desk

The desk is a Python (FastAPI) service that runs a loan broker on the XRPL Lending Protocol (XLS-66) over a Single Asset Vault (XLS-65), on devnet.

| Page | What it covers |
|---|---|
| [lending/INTERFACES](../lending/INTERFACES.md) | Constants, loan terms, the underwriting modules (`evidence.py`, `policy.py`), the desk API, borrower and demo scripts, working-capital Batch, sweeps |
| [lending/EVIDENCE](../lending/EVIDENCE.md) | Recorded runs with transaction hashes, responses and balances, including refusals |

Desk API summary (port 7500, JSON). Operator calls require the `X-Desk-Token` header and fail closed when the token is unset.

| Endpoint | Role |
|---|---|
| `POST /v1/loan-requests` | Borrower submits a signed `LoanSet` and, for a working-capital request, a signed supplier `Batch`; the desk scores it and returns `auto`, `held` or a refusal |
| `GET /v1/loan-requests`, `GET /v1/loan-requests/{id}` | List and read requests |
| `POST /v1/loan-requests/{id}/approve` | Operator. With `DESK_APPROVER_ACCOUNT` configured, `approvalTxHash` of the testnet approval receipt is required and verified before the broker key counter-signs; without it, approval is token-only |
| `GET /v1/loan-requests/{id}/signed-loan-set` | Operator. The held, borrower-signed blob and its hash, for building the receipt |
| `POST /v1/loan-requests/{id}/deny` | Operator |
| `POST /v1/loans/{loanId}/manage` | Operator. `impair`, `unimpair` or `default` |
| `GET /v1/loans`, `POST /v1/loans/{loanId}/sweeps` | Loan list with defaults and sweeps; the sweeper posts verified repayment records |
| `POST /v1/broker/cover`, `POST /v1/broker/credentials` | Operator. First-loss cover deposit; issue the borrower Credential |
| `GET /v1/vault`, `GET /v1/policy`, `PUT /v1/policy`, `GET /health` | State and policy |

Automatic approval requires a broker-issued Credential and a sufficient score computed from public ledger history plus the borrower's declared principal, debt, purpose and term. Eligible larger loans are held. Suppliers are paid from the loan in one `tfAllOrNothing` Batch.

## The approval receipt

In the gate-enabled approval flow (`DESK_APPROVER_ACCOUNT` set), an eligible loan above the automatic-approval limit waits for the Speculos emulator to sign a 1-drop Payment on testnet. The Payment carries two memos:

| MemoType (UTF-8) | MemoData | Meaning |
|---|---|---|
| `loan-approval` | 32-byte SHA-256, hex | Digest of the exact `LoanSet` blob the borrower signed: the validated transaction minus `CounterpartySignature` and node metadata, canonically encoded |
| `loan-terms` | UTF-8 text, for example `approve loan 30 XRP to rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG 6 payments` | Principal, borrower and payment count, readable on the signing screen |

The desk is designed to verify the signer, the digest and the terms before its software broker key counter-signs the `LoanSet` on devnet. Neither ledger enforces the link; the desk does.

| Page | What it covers |
|---|---|
| [Verifier](../ons/experiments/014-astra/verify/README.md) | A read-only script that rebuilds the borrower-signed loan from public nodes and compares it with the memos. `BINDING PASS` on the demonstrated pair, `BINDING FAIL` on a different loan, `BINDING ERROR` on bad evidence |
| [Proof of concept](../innovation/proof-of-concept/README.md) | The raw JSON-RPC requests and responses behind the check |

What the check proves: the binding between one approval and one loan, from public data. What it does not prove: hardware origin, human review, or the order in which the desk checked and signed. The recorded runs used scripted emulator taps.

## Ledger XRP app patch

The stock XRP app 2.8.1 rejects a `LoanSet` with status `0x680b` because it has no reader for the `STNumber` type, and it shows a `DelegateSet` as `Transaction Type: Unknown`. The patch adds the Number reader and the field labels for the lending, vault, credential and delegation transaction types. It does not add the counterparty signing prefix, so the broker still signs in software.

| Page | What it covers |
|---|---|
| [Experiment 005: the patch](../ons/experiments/005-app-xrp-patch/README.md) | Root cause, what the patch changes, how to build and test without Docker (`build_local.sh`), what a `LoanSet` shows on the Stax |
| [Experiment 005: results](../ons/experiments/005-app-xrp-patch/RESULT.md) | The app's own standalone suite in Speculos: 142 passed, 11 skipped, 0 failed; 20 new fixtures; pinned toolchain versions; screenshots in `screens/` |
| [Patch and PR text](../ons/experiments/005-app-xrp-patch/patch/) | `app-xrp-lending-fields.diff` against `LedgerHQ/app-xrp` at `7b5185f`, and the PR description |
| [Experiment 011: device-signed LoanSet](../ons/experiments/011-speculos-loanset-devnet/README.md) | The patched app in Speculos signs a `LoanSet` and a `LoanPay` as the borrower; both validated on devnet |
| [Ledger developer-experience feedback](LEDGER_DX_FEEDBACK.md) | Twelve findings from integrating the Device Management Kit, Speculos and the XRP app |

The patch is open as draft PR [LedgerHQ/app-xrp#97](https://github.com/LedgerHQ/app-xrp/pull/97). All device evidence comes from the Speculos emulator; no physical device signed anything.

## Application previews

`preview/` is a data package plus a small TypeScript engine: one JSON descriptor per transaction type turns `tx_json` into a titled, line-by-line preview with risk flags. It covers 19 types, 13 of them amendment-era (Credentials, Permissioned Domains, Permission Delegation, Batch, Vault, Lending).

| Page | What it covers |
|---|---|
| [preview/README](../preview/README.md) | Install, test, the `describe()` API, the descriptor format |
| [Application previews for XRPL](CLEAR_SIGNING_XRPL.md) | The format in full, what it borrows from ERC-7730 and what XRPL needs that ERC-7730 lacks, how a device app or wallet would consume it |

## Evidence

| Page | What it covers |
|---|---|
| [Proof on the ledger](../README.md#proof-on-the-ledger) | Thirteen validated transactions on testnet and devnet with explorer links |
| [lending/EVIDENCE](../lending/EVIDENCE.md) | Loan runs, refusals, the default and the sweeper repayment |
| [XRPL findings](XRPL_FINDINGS.md) | Seven integration findings from building on six amendments |
| [Ledger developer-experience feedback](LEDGER_DX_FEEDBACK.md) | Twelve findings; the two lists overlap |

The build exercised six amendments: Credentials, Permissioned Domains, Permission Delegation, Batch, Single Asset Vault (XLS-65) and the Lending Protocol (XLS-66).

## Limits

- Every device signature came from the Speculos emulator. No physical device signed anything.
- The wallet runs on testnet and the desk on devnet. The loop is stitched across two networks.
- The broker counter-signature is a software key. The patch does not add the counterparty signing prefix.
- Automatic x402 payments sign on the hot key under a software cap, because the facilitator refuses delegated payments. Held payments sign in the emulator.
- Devnet income is simulated with script-sent, memo-tagged Payments.
- The verifier checks one demonstrated pair and the selected terms. It is a binding check, not an authorization check.

The full list is in the README under [Honest limits](../README.md#honest-limits).

## Conventions

- Networks: testnet (`xrpl:1`) for the wallet, devnet for the desk. Never mainnet.
- Test fixtures include public test keys. Runtime credentials belong in gitignored `.env` files.
- Experiment folders under `ons/experiments/` document their procedure in a README and record the available evidence in a `RESULT.md`; some are offline-only.
- Findings are written up in this repository. The XRP app patch is filed as a draft PR; the issues are not yet filed.
