# RESULT - 010 iou-vault (trust-line token as the vault and loan asset)

Run on 2026-10-24 16:05-16:35 EDT (ledgers 6387040 - 6387400, devnet rippled 3.4.1, xrpl-py 5.2.0). The whole XLS-65/66
flow works with a self-issued trust-line token `USD` as the vault asset: **18 tesSUCCESS in the main flow + 5 in the
follow-up, 3 deliberate/instructive failures** (`terNO_RIPPLE`, `tecINSUFFICIENT_FUNDS`, `tecPATH_DRY`).
Console logs: `logs/2026-10-24-run1.log`, `logs/2026-10-24-run1-repay-probe.log`; machine logs `run-log.json`, `probe-log.json`.

## Accounts (devnet)
| Role | Address |
|---|---|
| issuer of `USD` | `rEp2qoQxM86q4RJc11DNaFKjeNx22eG5qu` (DefaultRipple on, no RequireAuth, no TransferRate) |
| depositor | `r9gDkMoBHYFoaJmrCTXJygV1HUWvidXFcA` |
| broker = vault owner | `rKZuhbJfv25D137Rje9ioxkSDiVkC7HbRK` |
| borrower | `rZF3jeQrj5NVuzeiL5s7QSh1KqyvUQACb` (trust line set up front) |
| borrower2 (probe) | `rJFQSzApX3ageSPPfHHheBfshKc59HcH1T` (NO trust line before LoanSet) |
| vault pseudo-account | `rUVDHptHWCeEkxzpfwXPjBr9MANmjUJifx` (holds the deposited USD on an auto-created trust line) |
| loan-broker pseudo-account | `rNz6XC2jrzPbsm8tiVz8ubU9edp4H7KEA` (holds the 50 USD cover, same kind of line) |

## Ledger objects
| Object | ID |
|---|---|
| Vault | `753D271A792889E31DDED7B3FD68371B121BF6365B709FAEF73497D481A9EC47` (`Scale=6`, `VaultKind=1`, SubscriptionDate 846187540, RedemptionDate 846188440) |
| Share MPT (`ShareMPTID`) | `000000017DFF4744C05A826E982500E7916C0B16AE49CC4A` |
| LoanBroker | `339C05F14786FA737B423008F72813D0AA51395B7B107E37F87DAD9F36359211` |
| Loan (main, 100 USD) | `7AF38579FF85F25F4CC65DB1D0ABEABCE079104B8E892397B11366017D7A2B64` (deleted in 6c) |
| Loan (probe, 1 USD) | `F1CE6CC7CF50C01A33A4CBEE2C31A129DAB87C4ADEB48A238BD5ECC7DA09D077` (deleted in p5) |

## Transactions
| Step | Tx | Result | Hash / explorer |
|---|---|---|---|
| 2a | VaultCreate(IOU) **before** DefaultRipple, `fail_hard` | `terNO_RIPPLE` "Path does not permit rippling" | not applied (ter), no hash |
| 2b | AccountSet `SetFlag=8` (asfDefaultRipple), issuer | tesSUCCESS | [0920...B954](https://devnet.xrpl.org/transactions/0920735783E036A2A20D9374E83CB8C93D3A4D074C1840F8407A7211C532B954) |
| 3 | TrustSet depositor, limit 1000000 USD | tesSUCCESS | [CB6A...F792](https://devnet.xrpl.org/transactions/CB6A78AE1B2F6DD38A673AEBD8FD79209387A78FA19B85028D0A97902974F792) |
| 3 | Payment issuer -> depositor 1000 USD | tesSUCCESS | [FC1B...E53C](https://devnet.xrpl.org/transactions/FC1B4A6FF84259184ABA7B812F437D80D0FD82FE6E003069965D82C99C55E53C) |
| 3 | TrustSet broker | tesSUCCESS | [7A7E...6C81](https://devnet.xrpl.org/transactions/7A7EDCC8B9A5BF43BA655B0528B999C8FFC276176DED16960EE8EBF356986C81) |
| 3 | Payment issuer -> broker 100 USD | tesSUCCESS | [5700...3C62](https://devnet.xrpl.org/transactions/5700369E0AAB6686304E08F45113826905D0F02ED4E87FBB53FBB97BADAA3C62) |
| 3 | TrustSet borrower | tesSUCCESS | [D922...060F](https://devnet.xrpl.org/transactions/D922F9739D8313134488B5615931C0F97F3ABD0031C162233BA4239910B7060F) |
| 3 | Payment issuer -> borrower 50 USD | tesSUCCESS | [79E3...4C84](https://devnet.xrpl.org/transactions/79E3038C24B28484BF1ED052FFEB4D3D32A76E61AE756E192F66AE8415744C84) |
| 4 | VaultCreate `Asset={"currency":"USD","issuer":...}`, close-ended, Fee 200000 | tesSUCCESS | [8111...E302](https://devnet.xrpl.org/transactions/81111F71839C555FA96B0173A7C7ED3A6B0DF99B9741D85EF7E45A433857E302) |
| 5a | VaultDeposit 500 USD | tesSUCCESS | [2A48...855A](https://devnet.xrpl.org/transactions/2A484A418566F723CA8770A615F56702473E6D5C9408EECFD1B7FA6F5B45855A) |
| 5b | LoanBrokerSet `DebtMaximum="200"` | tesSUCCESS | [4FEE...6D84](https://devnet.xrpl.org/transactions/4FEEFA44CDE51EDC6658967C5B98D9874E7BF955707D173126C687DB9BA56D84) |
| 5c | LoanBrokerCoverDeposit 50 USD | tesSUCCESS | [6E22...9E61](https://devnet.xrpl.org/transactions/6E224760B4ACA8B02A4869409AFC9EBFC83CB11C16C4927DB2C56F8B7D599E61) |
| 6 | LoanSet 100 USD, two signatures, Fee 200 | tesSUCCESS | [1366...FCBD](https://devnet.xrpl.org/transactions/136604FF9F893C7D0582A69EEF0BF9EC116076832007AF0BAE96374F23F6FCBD) |
| 6a | LoanPay installment 33.343347 USD | tesSUCCESS | [0B8E...5059](https://devnet.xrpl.org/transactions/0B8ECC7A6CD44A38A977E8037E383A0B7F84917B339756A06CA33E5B39F75059) |
| 6b | LoanPay tfLoanFullPayment 66.696693 USD offered | tesSUCCESS | [913B...14C5](https://devnet.xrpl.org/transactions/913BE492954A87CDE79E971C72B4944F85F00CBA4073A42C9BB66DC59F4314C5) |
| 6c | LoanDelete by broker owner | tesSUCCESS | [A8A4...32F1](https://devnet.xrpl.org/transactions/A8A4B6C4094C8AAF6301E29647B4A06A8DF2A3476A97C55567F6230C2BB332F1) |
| 7p | LoanSet 1 USD to borrower2 **with no trust line** | tesSUCCESS (line auto-created) | [9E3F...7EBB](https://devnet.xrpl.org/transactions/9E3F464E5EE6A2845B08BEBED30199DE46C3B5D6503A7B06503EBD3C03A57EBB) |
| 7pa | LoanPay installment 0.343334 USD | tesSUCCESS | [1437...647C](https://devnet.xrpl.org/transactions/1437AFBCF71C797AABBDAE13562221A6AAF2288EFFDE0833F6B244AFE4AF647C) |
| 7pb | LoanPay full payoff 0.696667 USD with only 0.5567 USD held | **tecINSUFFICIENT_FUNDS** | [17BB...B2C5](https://devnet.xrpl.org/transactions/17BB9CE211EE6A682F05D2AED0747ED8C6D744BF9B2F81B7BDCAD7B4FC4FB2C5) |
| p1 | Payment issuer -> borrower2 1 USD onto the auto-created **limit-0** line | **tecPATH_DRY** | [80E1...A2C6](https://devnet.xrpl.org/transactions/80E1762497E3838242E353FFFA895FBCBF27BE125B180951FB0C3933FF5EA2C6) |
| p2 | TrustSet borrower2 limit 1000000 | tesSUCCESS | [E3E0...0288](https://devnet.xrpl.org/transactions/E3E09C1BE4899A1024F29F9200126F00529C13EE51659C04C1886A28CC50E288) |
| p3 | Payment issuer -> borrower2 1 USD | tesSUCCESS | [F8C3...B8E8](https://devnet.xrpl.org/transactions/F8C3E722CB7479DAA967FE5A4CE7D25F08954185DADBD4CCDE56C329686EB8E8) |
| p4 | LoanPay tfLoanFullPayment 0.696667 USD | tesSUCCESS | [9D52...5375](https://devnet.xrpl.org/transactions/9D522D909D5BF4BA37CC2BC70F19C2373A2BA8C52162953B3EF46AFD34F85375) |
| p5 | LoanDelete probe loan | tesSUCCESS | [0CE9...C606](https://devnet.xrpl.org/transactions/0CE985717340D307C930F2CC168CFE473B0C39B7211C0B835F925ECDE445C606) |
| 8a | VaultWithdraw 500 USD after RedemptionDate | tesSUCCESS | [816F...3F34](https://devnet.xrpl.org/transactions/816F7E173D71A87EC02C77D195D766144B2352719DE394DB79566EA73A513F34) |
| 8b | VaultWithdraw remainder 0.0000200000008 USD (the interest) | tesSUCCESS | [AB72...8B3C](https://devnet.xrpl.org/transactions/AB725FE883012D863E49F7BDB78265B38EA024FF487061EA104FD26879718B3C) |

## Exact field values that worked

**Issuer setup**: `AccountSet{SetFlag: 8}` (asfDefaultRipple). Nothing else: RequireAuth off, no TransferRate, no freeze.
Probe 2a proves the requirement: `VaultCreate` with an IOU asset whose issuer lacks DefaultRipple is rejected with
`terNO_RIPPLE` (a *retry* code: without `fail_hard=true` the node would hold it and apply it once the flag is set, which
would have created a vault with stale dates).

**TrustSet** holders -> issuer: `LimitAmount={"currency":"USD","issuer":<issuer>,"value":"1000000"}`, no flags.
**Issuance**: plain `Payment` from the issuer with an issued-currency `Amount`.

**VaultCreate** (broker): `Asset={"currency":"USD","issuer":"rEp2qoQx..."}`, `WithdrawalPolicy=1`, `VaultKind=1`,
`SubscriptionDate=846187540` (ledger close + 120 s), `RedemptionDate=846188440` (+900 s), `Data="303130"`, no `Scale`
(defaulted to **6**), Fee 200000 (one owner reserve, autofilled). Meta `CreatedNode`s: `MPTokenIssuance, Vault, AccountRoot,
DirectoryNode, RippleState, MPToken`, i.e. **VaultCreate itself creates the pseudo-account's trust line** (`RippleState`
with `limit="0"`, `no_ripple=true`, balance 0). Resulting Vault: `Scale=6`, `Flags=0`, `ShareMPTID` set.

**VaultDeposit** (depositor): `Amount={"currency":"USD","issuer":...,"value":"500"}` -> `AssetsTotal=AssetsAvailable="500"`
(Number strings in asset units); pseudo-account line balance `500` on its limit-0 line (limits are not enforced on
vault/loan transfers, only on Payments).

**LoanBrokerSet**: `ManagementFeeRate=1000`, `DebtMaximum="200"` (Number, **asset units, not drops**), `CoverRateMinimum=10000`,
`CoverRateLiquidation=50000`. **LoanBrokerCoverDeposit**: `Amount` as an issued-currency amount, value `"50"` ->
`CoverAvailable="50"`, broker pseudo-account gets its own auto-created limit-0 line holding 50 USD.

**LoanSet** (Account = borrower, `Counterparty` = broker owner): `PrincipalRequested="100"`, `PaymentTotal=3`,
`PaymentInterval=60`, `GracePeriod=60`, `InterestRate=10000`, `LoanOriginationFee="0.1"`, `LoanServiceFee="0.01"`,
`ClosePaymentFee="0.02"`, `Fee="200"`. All money fields are **Number** (JSON strings in asset units, no currency/issuer
inside them: the asset is implied by the broker's vault). Same signing recipe as 001 (`autofill` -> `sign(borrower)` ->
`sign_loan_set_by_counterparty(broker, signed)` -> `submit tx_blob`). Resulting Loan: `PrincipalOutstanding="100"`,
`TotalValueOutstanding="100.0000380515684"`, `PeriodicPayment="33.33334601718946356"`, **`LoanScale=-13`** (absent on the
XRP loan in 001), `StartDate=846187552` = ledger close time, `NextPaymentDueDate=+60`. Balance effects (tx meta): vault pseudo-account line 500 -> 400, borrower line 50 -> **149.9**
(100 principal - 0.1 origination fee), broker owner's own line 50 -> 50.1 (the origination fee goes to the owner, not the broker pseudo-account).

**LoanPay installment**: `Amount={"currency":"USD","issuer":...,"value":"33.343347"}` = `PeriodicPayment` rounded **up** to 6
places + `LoanServiceFee`. Charged exactly `33.3433460171895` (= PeriodicPayment + 0.01, from the tx meta; the 0.00000098
excess stayed with the borrower). Vault pseudo-account +`33.3333458269319`, broker +`0.0100001902576` (service fee + the
1 % **management fee on the interest**, `0.0000001902576`, which rounded to 0 drops in the XRP run). `PaymentRemaining`
3 -> 2, `PrincipalOutstanding` -> `66.6666730085771`.
**LoanPay full payoff**: `Flags=0x20000`, offered `66.696693` = ceil6(`TotalValueOutstanding`) + ClosePaymentFee +
LoanServiceFee. Charged exactly `66.6866730085771` = `PrincipalOutstanding` 66.6666730085771 + **ClosePaymentFee 0.02 only**
(no LoanServiceFee and no accrued interest 20 s into the period; broker +0.0200000000000, vault +66.6666730085771).
That answers 001's open question: the single fee on a full payoff is the `ClosePaymentFee`. Borrower end balance
`49.8699809742334` = 50 + 99.9 - 33.3433460171895 - 66.6866730085771 (so the loan cost 0.1 origination + 0.01 service +
0.02 close + 0.0000190257666 interest, of which 1 % went to the broker as management fee). Vault `AssetsTotal` after the main cycle: `500.000018835509`
(after the probe loan's interest: `500.0000190238642`).
**LoanDelete** by the broker owner: tesSUCCESS, `LoanBroker.OwnerCount` back to 0 after both deletes.

**VaultWithdraw** (depositor, after ledger close time > `RedemptionDate`): `Amount={"currency":"USD","issuer":...,"value":"500"}`
-> tesSUCCESS, vault left with `AssetsTotal=AssetsAvailable="0.0000200000008"` (the two loans' net interest). A second
`VaultWithdraw` for exactly that `AssetsTotal` string -> tesSUCCESS and the Vault now omits `AssetsTotal`/`AssetsAvailable`
(zero), i.e. unlike the XRP run no share dust was left behind. Depositor line: 500 -> `1000.00001908665` USD.

## Errors hit and how they were resolved
| Code | Where | Cause | Fix |
|---|---|---|---|
| `terNO_RIPPLE` | 2a VaultCreate | issuer without `lsfDefaultRipple` | `AccountSet SetFlag 8` on the issuer first. Submit probes with `fail_hard` so the ter is not retried. |
| `tecINSUFFICIENT_FUNDS` | 7pb LoanPay full | borrower2 held 0.5567 USD, payoff needed 0.6967 (my sizing: a 1 USD loan nets 0.9 after the 0.1 origination fee, and the first installment took 0.3433). LoanPay requires the **whole `Amount`** to be held even if less is needed. | fund the borrower (`repay_probe.py` p1-p3), retry -> tesSUCCESS |
| `tecPATH_DRY` | p1 Payment issuer -> borrower2 | the trust line that LoanSet auto-created has `limit=0`; an issuer Payment cannot push a balance above the holder's limit | holder submits `TrustSet` with a real limit, then the Payment succeeds |

## IOU-specific gotchas (what differs from the XRP case in 001)
1. **DefaultRipple is mandatory on the issuer** for an IOU vault: `VaultCreate` -> `terNO_RIPPLE` otherwise (verified).
   RLUSD on mainnet/testnet already has it. A `ter` code is retried by the node for several ledgers, so a probe must
   use `fail_hard` or it can succeed later with stale dates.
2. **Pseudo-accounts need no TrustSet**: `VaultCreate` creates the vault pseudo-account's `RippleState` to the issuer in
   the same transaction (`limit=0`, `no_ripple=true`); `LoanBrokerCoverDeposit` does the same for the broker
   pseudo-account. Trust-line limits are not enforced on Vault*/Loan* transfers (the 500 USD sat on a limit-0 line).
3. **A borrower does not need a trust line before `LoanSet`**: the ledger created one for borrower2 (`limit=0`,
   `no_ripple=true`) and paid the principal into it (tesSUCCESS). But that line has **limit 0**, so the borrower can
   receive the token afterwards only via lending txs, not via ordinary Payments (`tecPATH_DRY` until it sets a limit).
   A borrower that must top up to repay needs a real `TrustSet`. (LoanPay from that line works fine.)
4. **Money fields on `LoanSet` / `LoanBrokerSet` are Number strings in asset units** (`"100"`, `"0.1"`, `"200"`), with no
   currency/issuer object; the asset is implied by the vault. `LoanPay`, `VaultDeposit`, `VaultWithdraw`,
   `LoanBrokerCoverDeposit` take full issued-currency `Amount` objects (`tecWRONG_ASSET` if they differ from the vault).
5. **Precision**: the vault gets `Scale=6` by default for a trust-line asset (optional field on `VaultCreate`, 0-18); the
   Loan carries `LoanScale=-13` (XRP loans have none) and `PeriodicPayment` / `TotalValueOutstanding` come back with 13-19
   significant decimals. Rounding the payment **up** to 6 places works; excess is ignored. Amounts more precise than the
   scale would give `tecPRECISION_LOSS` (docs; not triggered).
6. **Fees are exact in IOU**: full payoff charges `ClosePaymentFee` only (not `LoanServiceFee`); the 1 % management fee
   on interest is actually paid to the broker (0.00000019 USD) instead of rounding to zero as with drops.
7. **LoanPay checks the full `Amount` is held** (`tecINSUFFICIENT_FUNDS`) even when the required payment is smaller,
   so over-offering an installment with a thin balance fails: size payoffs from `TotalValueOutstanding`, not generously.
8. **Not tested, documented risks**: issuer `TransferRate` would be charged on vault/loan transfers between non-issuer
   accounts (keep it 0 for a lending stablecoin); `RequireAuth` would need the issuer to authorize every holder *and*
   leaves no way to authorize the pseudo-account's line (expect `tecNO_AUTH`); a global or individual freeze gives
   `tecFROZEN` on deposit/pay; deleting the trust line before repaying gives `tecNO_LINE`.
9. Everything else is identical to XRP: close-ended vault mandatory, vault owner == broker owner, two-signature LoanSet,
   phase gating by ledger close time, Loan object survives payoff until `LoanDelete`, VaultCreate costs one owner reserve.

## Summary (three sentences)
- XRPL's native lending protocol is asset-agnostic: we ran the same vault, broker, two-signature loan, repayment and
  redemption flow with a trust-line stablecoin on devnet, with no contract code, only ledger transactions.
- Stablecoin lending needs exactly two things from the issuer: DefaultRipple on (RLUSD already has it) and no transfer
  fee; the ledger itself creates the trust lines for the vault, the broker and even a borrower who had none.
- Interest, management fee and close fee were all settled on-ledger to 13 decimal places in USD, so a dollar-denominated
  agent loan can be priced and audited from the Loan object alone.

## Open questions / next step
- Repeat with an MPT asset (XLS-89 metadata `ac:"rwa"`) and with the testnet RLUSD issuer once lending reaches testnet.
- Test `TransferRate` and `RequireAuth` issuers explicitly (expected `tecNO_AUTH` on VaultCreate or deposit).
- The desk (`lending/`) assumes drops everywhere (`DebtMaximum`, `PrincipalRequested`, payment rounding); an IOU vault
  needs an asset-aware amount layer (Number strings for LoanSet/LoanBrokerSet, `IssuedCurrencyAmount` for the rest).
