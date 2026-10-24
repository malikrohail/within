# 010 - IOU (trust-line token) vault + loan on devnet

## Goal
Prove on the main XRPL devnet that the native lending protocol (XLS-65 Single Asset Vault + XLS-66 Lending Protocol)
works when the vault asset is a **trust-line token** (IOU, https://xrpl.org/docs/concepts/tokens/fungible-tokens/trust-line-tokens)
instead of XRP, i.e. a stablecoin-denominated vault and loan. Devnet has no RLUSD, so one of our faucet wallets issues a
test `USD` and plays the stablecoin issuer. Experiment 001 is the XRP baseline; this one records everything that differs
for an IOU: DefaultRipple, trust lines, pseudo-account trust lines, Number-typed loan fields in asset units, precision.

## What the script does (`run.py`)
1. Five faucet wallets: issuer, depositor, broker (= vault owner, XLS-66 requires it), borrower, borrower2 (probe).
2. a) PROBE `VaultCreate` with the IOU asset **before** the issuer sets DefaultRipple (submitted with `fail_hard` so a
   `ter*` is not retried); b) issuer `AccountSet asfDefaultRipple`.
3. `TrustSet` from depositor, broker, borrower (limit 1,000,000 USD); issuer `Payment`s 1000 / 100 / 50 USD.
4. `VaultCreate` with `Asset={"currency":"USD","issuer":...}`, close-ended (`VaultKind=1`, SubscriptionDate +120 s,
   RedemptionDate +900 s). Reads the Vault back, the share MPT and the vault pseudo-account's trust line.
5. `VaultDeposit` 500 USD; `LoanBrokerSet` (DebtMaximum "200"); `LoanBrokerCoverDeposit` 50 USD.
6. After SubscriptionDate: `LoanSet` 100 USD (PaymentTotal 3, PaymentInterval 60, GracePeriod 60, 10 % APR, fees
   0.1 / 0.01 / 0.02 USD), borrower signs, broker counter-signs (`sign_loan_set_by_counterparty`, xrpl-py 5.2.0).
7. `LoanPay` one installment in USD, `LoanPay tfLoanFullPayment`, `LoanDelete`. Then (7p) the same cycle for 1 USD to
   borrower2, who has **no trust line**, to see whether the ledger creates one.
8. After RedemptionDate: `VaultWithdraw` 500 USD by the depositor, then the remainder (`AssetsTotal`).

Every tx prints the result code, hash and `https://devnet.xrpl.org/transactions/<hash>`; `run-log.json` holds the
machine-readable log, `logs/` the console output of each run.

## Run
```
cd ons
experiments/.venv/bin/python -u experiments/010-iou-vault/run.py            # full run, ~20 min (waits for both phases)
experiments/.venv/bin/python -u experiments/010-iou-vault/run.py --skip-noline --no-withdraw
```
`repay_probe.py` is the follow-up to step 7p (the 1 USD probe borrower ran out of USD before its payoff): it shows the
`tecPATH_DRY` on an issuer Payment into the auto-created limit-0 line, sets a TrustSet, funds, repays and deletes the loan.
Run it before the Redemption phase if 7pb fails, otherwise the depositor cannot withdraw the full deposit.

Seeds: `experiments/.secrets/010.json` (created on first run, mode 600, gitignored, never printed). A re-run reuses the
accounts, skips the DefaultRipple probe (flag already on) and only tops up trust lines / balances that are short.
Each run creates a new vault; the previous vault's shares stay with the depositor until withdrawn.

Requirements: `experiments/.venv` (Python 3.13, xrpl-py 5.2.0), devnet JSON-RPC `https://s.devnet.rippletest.net:51234`,
faucet `faucet.devnet.rippletest.net`. Spends only faucet XRP (fees + 0.2 XRP vault reserve).

## Expected outcome
All on-ledger steps `tesSUCCESS` except the deliberate probe 2a (`terNO_RIPPLE`). See `RESULT.md` for the hashes and the
IOU gotcha list.
