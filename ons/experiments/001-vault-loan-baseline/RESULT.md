# RESULT - 001 vault-loan-baseline

Run on 2026-10-24 (ledgers 6382604 - 6382649, devnet rippled 3.4.1). Every step returned `tesSUCCESS` at the first
on-ledger attempt; the only failure was a local Python type bug before any tx was sent. Full machine-readable log: `run-log.json`.

## Accounts (devnet)
| Role | Address |
|---|---|
| depositor | `rnvBrqEMBr5uqyne4AqMtSiD8t4c3xDpQe` |
| broker = vault owner | `rfWhYXgxaxmoaUcsNTnvHSqmFFWckQgyas` |
| borrower | `rs98JSqCz7qm8iBLFGcCS1Gdc2kYwAFU2L` |
| vault pseudo-account | `r9kY3eLs11EXEq3ksAxxAzGeYairRrYATX` (holds the deposited XRP) |
| loan-broker pseudo-account | `rDKAvuUhMBfGe9wt59BKK1rGhLMZ61oofh` (holds the 20 XRP cover) |

## Ledger objects created
| Object | ID |
|---|---|
| Vault | `C08AD6CA2CB458EC9C09A4D63AEC91B1A0B4E6A0F3D2E3B623277BA027C443F1` |
| Vault share MPT (`ShareMPTID`) | `000000015FFCE1506D68CD6DF922B1ED5CA11103C73D4C54` (MPTokenIssuance index `024D88022C51E8AD40266538257F1090F86F5CAA98AB0D5C372AA7D783B45345`, Flags 56) |
| LoanBroker | `6CB4EF713E609CABC59290BB2978700E23AEEF6454CB27A3B1D68E2C397E2BD4` |
| Loan | `0EE298F93AA3CD79587E19968B7EF91D3D32956357FA7F1BA58339D3D4281E00` (deleted in 6c) |

## Transactions (all tesSUCCESS)
| Step | Tx | Fee (drops) | Hash / explorer |
|---|---|---|---|
| 2 | VaultCreate | 200000 | [DF80A8B5...00FF7](https://devnet.xrpl.org/transactions/DF80A8B517E321E4CF56D0FACBE0ABF2B840DFE915EF0829C4095C6391D00FF7) |
| 3 | VaultDeposit 200 XRP | 1 | [D1E22952...0BD8](https://devnet.xrpl.org/transactions/D1E229528F53156DBFF62A4C47F586FFD87190C5B3241A03D1049EF551430BD8) |
| 4a | LoanBrokerSet | 1 | [8672F01B...39DA](https://devnet.xrpl.org/transactions/8672F01B8AD314A50617F2E9B7FB53C6C15DBA7E937371E5E413065E14EB39DA) |
| 4b | LoanBrokerCoverDeposit 20 XRP | 1 | [26799AB9...A8A6](https://devnet.xrpl.org/transactions/26799AB91233BB4345F2D243A75D5C57378237CBA1A2AFA3E174F1C3ADC0A8A6) |
| 5 | LoanSet 50 XRP (two signatures) | 200 (set by hand) | [20B724D0...9260](https://devnet.xrpl.org/transactions/20B724D09E1416A1F9379DEB03F881E149061EE3A177690EDCD17AE2C0BE9260) |
| 6a | LoanPay installment 16676674 drops | 1 | [82536879...E047](https://devnet.xrpl.org/transactions/825368795FB868210BC0667916281F5FAD4DD2634AC4CAD629F24C9011CFE047) |
| 6b | LoanPay full payoff, Flags 0x20000, 33353346 drops offered | 1 | [AE84BB47...B877](https://devnet.xrpl.org/transactions/AE84BB47C8DEC333A565EF168317ABD11BD323C9857E9D322D2806679762B877) |
| 6c | LoanDelete by broker | 1 | [32768168...0820](https://devnet.xrpl.org/transactions/3276816811CAD14893EF8D7ABE4E0388FD563BA239FD69036CCC5C39A4720820) |
| 8 | VaultWithdraw 200 XRP after RedemptionDate (`withdraw.py`) | 1 | [AB425C99...A555](https://devnet.xrpl.org/transactions/AB425C99B74FB1A4A2280E0C0467C237896177F4AB2D9909A34CEC579453A555) |

Full hashes:
```
DF80A8B517E321E4CF56D0FACBE0ABF2B840DFE915EF0829C4095C6391D00FF7  VaultCreate
D1E229528F53156DBFF62A4C47F586FFD87190C5B3241A03D1049EF551430BD8  VaultDeposit
8672F01B8AD314A50617F2E9B7FB53C6C15DBA7E937371E5E413065E14EB39DA  LoanBrokerSet
26799AB91233BB4345F2D243A75D5C57378237CBA1A2AFA3E174F1C3ADC0A8A6  LoanBrokerCoverDeposit
20B724D09E1416A1F9379DEB03F881E149061EE3A177690EDCD17AE2C0BE9260  LoanSet
825368795FB868210BC0667916281F5FAD4DD2634AC4CAD629F24C9011CFE047  LoanPay (installment)
AE84BB47C8DEC333A565EF168317ABD11BD323C9857E9D322D2806679762B877  LoanPay (tfLoanFullPayment)
3276816811CAD14893EF8D7ABE4E0388FD563BA239FD69036CCC5C39A4720820  LoanDelete
AB425C99B74FB1A4A2280E0C0467C237896177F4AB2D9909A34CEC579453A555  VaultWithdraw
```

## Exact field values that worked

**VaultCreate** (broker): `Asset={"currency":"XRP"}`, `WithdrawalPolicy=1`, `VaultKind=1`, `SubscriptionDate=846173711`
(ledger close time + 120 s), `RedemptionDate=846174311` (+600 s), `Data="303031"`, no flags (public, transferable shares).
Resulting Vault: `Flags=0`, `LEVersion=1`, `ShareMPTID` set, `AssetsTotal/AssetsAvailable="200000000"` after the deposit.
There is **no `SharesTotal` field** on the Vault; outstanding shares live in `MPTokenIssuance.OutstandingAmount`
(200000000) and the depositor's `MPToken.MPTAmount` (200000000, 1 share per drop since Scale is 0 for XRP).

**LoanBrokerSet** (broker, same account as vault owner): `VaultID`, `ManagementFeeRate=1000`, `DebtMaximum="100000000"`,
`CoverRateMinimum=10000`, `CoverRateLiquidation=50000`, `Data="303031"`. Resulting LoanBroker: own pseudo-`Account`,
`LoanSequence=1` (2 after the loan), `DebtTotal` **absent when zero**, `CoverAvailable="20000000"` after the cover deposit.

**LoanSet** (Account = borrower, `Counterparty` = broker owner): `LoanBrokerID`, `PrincipalRequested="50000000"`,
`PaymentTotal=3`, `PaymentInterval=60`, `GracePeriod=60`, `InterestRate=10000` (10 % APR in 1/10 bp),
`LoanOriginationFee="100000"`, `LoanServiceFee="10000"`, `ClosePaymentFee="10000"`, `Fee="200"`.
Signing recipe that worked (xrpl-py 5.2.0):
1. `tx = autofill(LoanSet(...), client)` with the borrower's account.
2. `signed = sign(tx, borrower_wallet)` -> fills `SigningPubKey` + `TxnSignature`.
3. `cs = xrpl.transaction.counterparty_signer.sign_loan_set_by_counterparty(broker_wallet, signed)` -> adds
   `CounterpartySignature={"SigningPubKey":..., "TxnSignature":...}` (single-sig form; a `Signers` array form exists for multisig).
4. `client.request(GenericRequest(method="submit", tx_blob=cs.tx_blob))`, then poll `tx` by `cs.hash`.
   `CounterpartySignature` is not a signing field, so the borrower's signature stays valid after it is added.
Resulting Loan: `StartDate=846173723` (the ledger close time, not SubscriptionDate), `NextPaymentDueDate=StartDate+60`,
`PeriodicPayment="16666673.00859473178"` (a decimal string, Number type), `TotalValueOutstanding="50000020"`,
`PrincipalOutstanding="50000000"`, `PaymentRemaining=3`, `LoanSequence=1`, `Flags=0`. No `LoanScale` field on an XRP loan.
Balance effects of LoanSet: vault pseudo-account -50000000, borrower +49899800 (50 XRP - 0.1 XRP origination fee - 200 fee),
broker +100000 (origination fee goes straight to the broker owner's account).

**LoanPay installment**: `Amount = ceil(PeriodicPayment) + LoanServiceFee = 16666674 + 10000 = 16676674` drops, no flags.
Consumed exactly: vault +16666674 (of which 11 drops interest -> `Vault.AssetsTotal` 200000011), broker +10000 service fee,
`Loan.PrincipalOutstanding` 50000000 -> 33333337, `PaymentRemaining` 3 -> 2, `LoanBroker.DebtTotal` 50000000 -> 33333337.

**LoanPay full payoff**: `Flags=0x00020000` (`tfLoanFullPayment`), offered `Amount=33353346`
(`ceil(TotalValueOutstanding) + ClosePaymentFee + LoanServiceFee`). Charged only 33343338: vault +33333337 (principal only,
0 accrued interest after ~10 s), broker +10000 (one fee), the remaining 10008 drops stayed with the borrower (excess is ignored
when overpayment is not enabled). Afterwards the Loan object still exists with `PrincipalOutstanding`, `TotalValueOutstanding`,
`PaymentRemaining` and `NextPaymentDueDate` omitted (zero), `Vault.AssetsAvailable == AssetsTotal == 200000011`,
`LoanBroker.DebtTotal` absent, `LoanBroker.OwnerCount=1`.

**LoanDelete**: `LoanID`, submitted by the broker owner -> tesSUCCESS (borrower not tried because the first attempt worked).
After it, `LoanBroker.OwnerCount` is omitted (zero) and the Loan is gone from the borrower's `account_objects`.

**VaultWithdraw** (depositor, after ledger time > `RedemptionDate`): `VaultID`, `Amount="200000000"` (asset units, not shares)
-> tesSUCCESS. Depositor +199999999 drops (200 XRP - 1 drop fee). The vault kept `AssetsTotal=AssetsAvailable="11"`: the
11 drops of interest stay in the vault, and the depositor still holds the matching share dust (`MPToken.MPTAmount="11"`,
`MPTokenIssuance.OutstandingAmount="11"`, checked after the withdraw). To exit fully, withdraw by share amount or withdraw `AssetsTotal` instead of the deposit.

## Verification run (same script, 2026-10-24, second vault)
Re-ran the final `run.py` end to end to prove reproducibility: 8/8 tesSUCCESS. Hashes: VaultCreate
`F93276B36D4B9E80809A0767F2B08BCEDB0F6B27174F37F8AFAF68CDB45B8DA8`, VaultDeposit `BBAAED6E7444B1ED02893777D962D69B781F78BBB985E305C2690248450E180D`,
LoanBrokerSet `D3402DD6DD45494834284986F6180FA0C6498A1022AC76FC731E50AF8730E859`, LoanBrokerCoverDeposit `46032C851FE0CE884F95F421A1DA4E98BF32EF9F8BF8E7573A2EA45394B4C7A3`,
LoanSet `CCACD8AF07D132148DE65DC46D55D5DC39F701BDDA660621F2793DA4C137C515`, LoanPay `1B4D75016B00732450000614C1FFC7BD140058EDC39C3AABAC38528F3418FDBB`,
LoanPay full `A5F81C6AF07CB592E6D17588EB3B955A0BBB87BB32D7C406733B06EEB1BC6D81`, LoanDelete `945E3984BDE24DED9B3E0A7D899FAF10A68260828EE41615DCD3A38019FB5430`.
Vault `8E758E98E2383755178BBAD782EA552718F6DEDBB0041BE947166CF72A5A0248` (RedemptionDate 846174730) still holds the
depositor's 200 XRP; redeem with `withdraw.py 8E758E98E2383755178BBAD782EA552718F6DEDBB0041BE947166CF72A5A0248`.
Console logs of both runs are in `logs/`; `run-log.json` holds the latest run only.

## Final balances (run 1, before withdraw)
depositor 99.999999 XRP (300 - 200 deposit - 1 drop), broker 79.919998 XRP (100 - 20 cover - 0.2 VaultCreate fee + 0.1 origination
+ 0.02 fees - 3 drops), borrower 99.879787 XRP (100 + 50 - 0.1 - 16.676674 - 33.343338 - 0.000201).

## Errors hit and how they were resolved
- Local only: `TypeError: '>=' not supported between 'int' and 'str'` because `xrpl.utils.xrp_to_drops` returns a **string**.
  Fixed with `int(...)`. No on-ledger error occurred in this run.
- Avoided by reading the spec first (would otherwise have been errors):
  - `LoanBrokerSet` on an open-ended vault -> `tecNO_PERMISSION` under `LendingProtocolV1_1`. Vault must be `VaultKind=1`.
  - `LoanSet` during the Subscription phase -> `tecTOO_SOON`; at/after `RedemptionDate` -> `tecEXPIRED`; loan maturity must
    end at least 60 s before `RedemptionDate` -> `tecNO_PERMISSION`. The script waits for `ledger close_time > SubscriptionDate`.
  - `tfLoanFullPayment` with `PaymentRemaining == 1` -> `tecKILLED`; that is why `PaymentTotal=3`.
  - `redemption_date - subscription_date` must be in `[180, 946708560)` s (xrpl-py validates this client side).

## Surprises / gotchas (write these into the glossary)
1. **Close-ended vault is mandatory for lending** on devnet now (`LendingProtocolV1_1`). That makes every lending demo
   time-boxed: deposits only before `SubscriptionDate`, loans only between `SubscriptionDate` and `RedemptionDate - 60 s`,
   withdrawals only after `RedemptionDate`. Plan demo timelines around this (minimum investment window 180 s).
2. **Vault owner and LoanBroker owner must be the same account** (spec: "may change in the future"). Three roles, not four.
3. **LoanSet is a two-signature single transaction**, not two transactions. Either party can be `Account`; the other is
   `Counterparty` (defaults to the broker owner when omitted). xrpl-py 5.2.0 ships `sign_loan_set_by_counterparty`;
   there is no RPC-side "accept loan" step. For an agent flow this means the borrower and broker must exchange a signed
   blob off-ledger (or use Batch, where the counterparty signature is not required inside a batch per the spec).
4. **VaultCreate costs one owner-reserve increment as its fee** (200000 drops on devnet), autofilled by xrpl-py.
   Devnet base fee is otherwise 1 drop.
5. **Both Vault and LoanBroker get pseudo-accounts** that hold the funds; `account_info` on the broker owner does not show
   the cover. `DebtTotal`, `PrincipalOutstanding`, `PaymentRemaining` are **omitted when zero**, so read with `.get(..., 0)`.
6. **Number-typed fields come back as decimal strings** (`PeriodicPayment="16666673.00859473178"`); the borrower is charged
   `ceil()` of it. Overpaying is safe (excess ignored) unless `tfLoanOverpayment` is set.
7. **A fully repaid loan is not deleted automatically**; the broker owner (or borrower) must `LoanDelete` to free reserves.
8. The faucet gives exactly 100 XRP per call and happily tops up an existing account; `generate_faucet_wallet(client, wallet=w,
   faucet_host="faucet.devnet.rippletest.net")` is the call.
9. `Vault.SharesTotal` does not exist as a field; use the MPTokenIssuance `OutstandingAmount`.
10. `VaultWithdraw.Amount` is in asset units; withdrawing the original deposit leaves the earned interest (and share dust) in
    the vault. Close-ended vaults are strictly gated by **ledger close time**, not wall-clock: compare against the
    `close_time` of the last validated ledger.

## Open questions
- Was the single 10000-drop fee on the full payoff the `LoanServiceFee` or the `ClosePaymentFee`? Both were 10000, so the run
  cannot tell. Re-run with distinct values.
- Accrued interest on the early payoff rounded to 0 after ~10 s; at what loan size / duration does `CloseInterestRate` and
  accrued interest become visible? Needed if we want to show "interest earned" in a demo.
- Can `LoanDelete` be submitted by the borrower too? (Spec says yes; untested.)
- Does `LoanSet` inside a `Batch` really skip `CounterpartySignature` (spec: "outside a Batch")? That would be the clean
  agent-to-agent pattern. Candidate for experiment 002.
- Management fee: with 11 drops of interest the 1 % broker share rounded to 0; `ManagementFeeOutstanding` never appeared.
- xrpl-py `submit_and_wait` autofilled `Fee=1` on devnet; mainnet/testnet load fees will differ. Not a protocol issue.

## Next step
Experiment 002: same flow with `Batch` (borrower + broker signatures in one atomic batch), a permissioned-domain private
vault, and distinct fee values to answer the open questions; then wire the borrower side to a Ledger-signed wallet.
