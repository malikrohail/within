# 011 result: device-signed LoanSet and LoanPay validated on devnet (2026-10-24, Speculos emulator on a Linux build host)

Run finished 2026-10-24 evening EDT. App: LedgerHQ/app-xrp `7b5185f` + `../005-app-xrp-patch/patch/app-xrp-lending-fields.diff`,
built for Stax at SDK `API_LEVEL_27`, binary sha256 `940b42bf…5468f` (same file as experiment 005). Emulator: Speculos 0.27.1,
headless, default seed. Signing path `44'/144'/0'/0/0`, device account `ra7Zr8ddy9tB88RaXL8B87YkqhEJG2vkAJ`,
public key `038368B6F1151E0CD559126AE13910B8B8D790652EB5CC0B5019A63D2E60792961`. Network: XRPL devnet (`s.devnet.rippletest.net:51234`).

## Transactions (all validated `tesSUCCESS`, re-read from the public devnet node after the run)

| Step | Type | Signed by | Hash | Ledger |
|---|---|---|---|---|
| 1 | VaultCreate (close-ended, 60 s subscription) | broker (software key) | `734D13842DE7054C8BD45AB142074AD404549BAA697E76D9C2A4024A6CD4AC9F` | 6389951 |
| 2 | VaultDeposit 60 XRP | depositor (software key) | `01F355141F93AB8C4ADA9CE2C8BB8558ED598CF44C05AD3394E5114044A2403F` | 6389953 |
| 3 | LoanBrokerSet | broker | `B2907620EFF67C12B4B8CBAAF1EAADCC427EF47DDC2CE6072AD7DC90A68F07BC` | 6389955 |
| 4 | LoanBrokerCoverDeposit 5 XRP | broker | `95651B170BE5E4979E13CBAE203B14D6AABA5BF9FDBBFCFD5BED29EAFDF57C52` | 6389957 |
| **5** | **LoanSet 10 XRP, 3 payments x 60 s, 10 %** | **device = Account signer (patched app in Speculos); broker CounterpartySignature (software key)** | **`0CE7AFEF47E0F092CFABBEB78DAD6848B1BE8E5338C5BFB9CCC0804A49B16243`** | 6389970 |
| **6** | **LoanPay 3.343335 XRP (first installment + service fee)** | **device alone** | **`4B531D0B37124F41404EF8AA5359B5A8A433DA8DA507B23E5F6EE134D206644F`** | 6389974 |

Explorer: `https://devnet.xrpl.org/transactions/<hash>`. Loan object after step 6: `PrincipalOutstanding 6666668`, `PaymentRemaining 2`.

Checked from the node for steps 5 and 6: `validated: true`, `meta.TransactionResult tesSUCCESS`, `Account` equals the device
account, `SigningPubKey` equals the device public key above, and (step 5 only) `CounterpartySignature` present. The script
also verified each device signature locally against `encode_for_signing(tx)` with the device key before submitting
(`logs/01-run.log`: "device signature verifies against the Account key: True", twice).

## What the device showed (Stax, `screens/`)

LoanSet, five pages: (1) app home; (2) `Transaction Type: Loan Set`, `Account`, `Payment Interval 60 s`, `Grace Period 60 s`,
`Payment Total 3`; (3) `Interest Rate 10 %`, `Loan Broker ID`, `Fee XRP 0.0002`; (4) `Counterparty`, `Loan Origination Fee 100000`,
`Loan Service Fee 10000`, `Close Payment Fee 10000`, `Principal Requested 10000000`; (5) `Sign transaction?` with `Hold to sign`;
then `Transaction signed`. No blind-signing warning at any point: the app reviews the type field by field.

LoanPay, four pages: `Transaction Type: Loan Pay`, `Account`, `Loan ID`, `Amount XRP 3.343335`; `Fee XRP 0.0002`; `Sign transaction?`;
`Transaction signed`.

Driving: "next" taps at (350, 620) until `Hold to sign`, then press at (336, 515) for 3.2 s, the same recipe `wallet/src/speculos.ts`
uses on the stage emulator for app 2.8.1.

## What this does and does not prove

- Proves: the parser patch from experiment 005 produces borrower-side signatures the ledger accepts for two XLS-66 transaction
  types, and the lending fields (as raw Numbers where the app has no asset context) are on the emulator screen before the signature.
- Emulator only. Speculos Stax; no physical device was used or exists on the team. The Speculos default seed is public,
  so the device account is spendable by anyone running Speculos; it is an emulator account, never a treasury.
- The broker's `CounterpartySignature` is still a software key. The app has no `CPT\0` prefix (finding 12 in
  `docs/LEDGER_DX_FEEDBACK.md`), so a Ledger cannot be the broker side of a LoanSet with this patch either.
- A fresh vault and broker were created for this run. The stage desk (:7500) and its vault were not touched.
- Nits already listed in 005 section 7 and visible here: `Principal Requested` and the three fee fields render as raw
  drops (`10000000`, `100000`), not `XRP 10`; the 32-byte `Loan Broker ID` and `Loan ID` wrap over four lines.
- This is not the stage flow and does not replace it. On stage the agent is the borrower with its own software key and
  the human controls the broker's approval through the 1-drop approval Payment. Here the emulator signs as the borrower
  (`Account`); the broker side is still software. A hardware counter-signature for the broker needs the `CPT\0` prefix
  in the app, which this patch does not add. So the approval-Payment bridge stays necessary for the broker role; what
  this run adds is a borrower-side native signing proof.
- The taps were driven by the script (`run.py`), not by a person; this is recorded emulator evidence plus independently
  verified public signatures (checked by a separate reviewer), not proof that a human approved anything, and
  not proof of exclusive key custody.
- Neither transaction exercised multi-packet APDU chunking (234 and 144 bytes with the path, both under 255); that
  code path is source-reviewed only.
- The driver as run would have tapped "Continue anyway" on a blind-signing warning; the saved pages show none, but the
  run did not assert that. The script now fails closed on such a page and asserts `tesSUCCESS` on every step.
