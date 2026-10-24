# 001 - vault-loan-baseline

**Goal.** Prove the full XLS-65 (Single Asset Vault) + XLS-66 (Lending Protocol) happy path on the main XRPL devnet
with xrpl-py only, and record every transaction hash, every field value that worked, and every surprise.
Everything downstream (agentic lending desk, Ledger signing, x402) builds on this flow.

**Status 2026-10-24:** all steps succeeded, see `RESULT.md`.

## How to run

```bash
cd ons
experiments/.venv/bin/python experiments/001-vault-loan-baseline/run.py            # ~4 min (2 min is waiting for the vault's Investment phase)
experiments/.venv/bin/python experiments/001-vault-loan-baseline/run.py --withdraw # + ~8 min: waits for RedemptionDate, then VaultWithdraw
experiments/.venv/bin/python experiments/001-vault-loan-baseline/withdraw.py <VaultID>  # redeem shares from an earlier run's vault
```

- Network: devnet JSON-RPC `https://s.devnet.rippletest.net:51234` (rippled 3.4.1, network_id 2).
- Seeds: `experiments/.secrets/001.json` (`{"depositor","broker","borrower"}`); created and faucet-funded on first run,
  topped up from the faucet on later runs if a balance is below the step's need. Seeds are never printed.
- Every run creates a *new* vault, broker and loan (ledger objects are cheap; the vault lifecycle is time-boxed anyway).
- `run-log.json` is rewritten on each run with every step's result code, hash and explorer link plus the final objects.

## What each step does

| Step | Tx | Signer | Notes |
|---|---|---|---|
| 1 | faucet | - | depositor needs 220 XRP (faucet gives 100 per call, so it is called 3x), broker 40, borrower 20 |
| 2 | `VaultCreate` | broker | XRP asset, public, **close-ended** (`VaultKind=1`, `SubscriptionDate=now+120s`, `RedemptionDate=+600s`). Under `LendingProtocolV1_1` a LoanBroker can only be attached to a close-ended vault. Fee is one owner-reserve increment (200000 drops) |
| 3 | `VaultDeposit` | depositor | 200 XRP during the Subscription phase; depositor receives 200000000 share MPTs |
| 4a | `LoanBrokerSet` | broker (= vault owner, required by spec) | `ManagementFeeRate=1000` (1%), `DebtMaximum=100000000`, `CoverRateMinimum=10000` (10%), `CoverRateLiquidation=50000` (50%) |
| 4b | `LoanBrokerCoverDeposit` | broker | 20 XRP first-loss capital into the broker's pseudo-account |
| 5 | `LoanSet` | borrower signs, broker counter-signs, borrower submits | waits until ledger time > `SubscriptionDate` (LoanSet is `tec` during Subscription). 50 XRP, 3 payments x 60 s, 10 % APR, 0.1 XRP origination fee, 0.01 XRP service and close fees |
| 6a | `LoanPay` | borrower | one installment: `ceil(Loan.PeriodicPayment) + LoanServiceFee` |
| 6b | `LoanPay` + `tfLoanFullPayment` | borrower | early payoff with 2 payments left (not allowed with 1 left) |
| 6c | `LoanDelete` | broker | removes the paid-off Loan object (it is not auto-deleted) |
| 7 | reads | - | balances, Vault, LoanBroker objects |
| 8 | `VaultWithdraw` (`--withdraw`) | depositor | only after `RedemptionDate` |

## Expected outcome
Eight `tesSUCCESS` results (nine with `--withdraw`), the vault ending with `AssetsTotal = 200 XRP + interest`,
`LoanBroker.DebtTotal` absent (zero) and `CoverAvailable = 20000000`, and the borrower's XRP back to roughly the
starting balance minus fees and interest.
