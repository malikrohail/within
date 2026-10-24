# Show the fields of XRPL 3.x lending, vault, credential and delegation transactions; stop rejecting STNumber fields

Draft PR text for LedgerHQ/app-xrp (base: master `7b5185f`, 2.8.2). Written 2026-10-24 at
the XRPL NYC hackathon. Verified in Speculos (Stax) only; no physical device was used. Stax PNGs from the ragger golden run are in `../screens/`; they are not attached to the PR. Posted on 2026-10-25 as draft PR [LedgerHQ/app-xrp#97](https://github.com/LedgerHQ/app-xrp/pull/97).

## Problem

rippled 3.x (XLS-65 Single Asset Vault, XLS-66 Lending Protocol, XLS-70 Credentials,
XLS-75 Permission Delegation, XLS-80 Permissioned Domains, XLS-33 MPT, XLS-56 Batch) added
transaction types 54-84 and a new serialized data type, `STNumber` (type code 9).

1. Any transaction carrying an `STNumber` field (`LoanSet.PrincipalRequested`,
   `LoanBrokerSet.DebtMaximum`, `VaultCreate.AssetsMaximum`, ...) is rejected with APDU
   status `0x680b` even when blind signing is enabled: `read_field_value()` has no case for
   type 9, returns `NOT_SUPPORTED` (`0xB` in the current SDK `errors.h`), and
   `handle_packet_content()` maps it to `0x6800 | 0xB`. MPT amounts (`0x60` prefix, 33 bytes)
   are read as 8-byte XRP amounts and fail with `EXCEPTION_OVERFLOW` (`0x6807`). So a Ledger
   cannot sign these transactions at all, not even blind.
2. The types that do reach blind signing (`VaultDeposit`, `LoanPay`, `LoanManage`,
   `DelegateSet`, ...) show `Transaction Type: Unknown` and every type-specific field as
   `Unknown`. For `LoanManage`, "default this loan and seize the cover" and "mark it
   impaired" differ only by an unlabeled flag; for `DelegateSet`, which transaction type a
   delegate is granted is an unlabeled integer.

## Change

- `fields.h`/`xrp_parse.c`: readers for `STNumber` (12 bytes), `UInt64`, `Int32`, `Hash192`;
  MPT amounts (with the issuance ID exposed as its own row, like `Issuer` for IOUs); MPT
  `Issue` (44 bytes, ACCOUNT_ONE marker). A data type that still has no reader now stops
  parsing and forces the blind-signing flow instead of answering an error; a
  `stopped_early` flag makes sure such a transaction can never skip the blind-signing flow, in line with the
  existing rule that an unexplainable field means blind signing (V-057 follow-up).
- `transaction_types.h`/`general.c`: names for types 54-84. Credential*, PermissionedDomain*,
  DelegateSet, Vault*, LoanBroker*, Loan* are added to `is_supported_transaction_type()`.
  `MPToken*` and `Batch` are named but stay blind-sign (Batch nests a `TransactionType`
  per inner transaction, which `post_process_field()` already refuses to trust).
- `fields.c` + formatters: names for all XLS-65/66, Credential, PermissionedDomain and
  DelegateSet fields; `STNumber` as a decimal string; XLS-66 rates (1/10 basis point) as
  percent; `PaymentInterval`/`GracePeriod` as seconds; `StartDate`, `SubscriptionDate`,
  `RedemptionDate` as timestamps; `PermissionValue` by name (`Payment`, `Trustline
  Authorize`, ...); `Flags` for `VaultCreate`, `LoanManage`, `LoanPay` with the
  unknown-bit check; `CredentialIDs` vector entries labelled `Credential ID [i]`.
- Tests: 17 field-review vectors (`testcases/30-credential-create` ... `38-loan-manage`) and 3
  blind-sign vectors (Batch, unknown data type, MPTokenIssuanceCreate) generated with
  xrpl-py 5.2.0 (`.json` next to each `.raw`), wired into `unit-tests/src/test_tx.c`, which
  gains `test_blind_sign_transactions` asserting `BLIND_SIGN_REQUIRED`. No existing
  expectation changes. [Ragger golden snapshots for the new folders: to be added from the
  device run.]

Field codes and type ids come from xrpl.js `ripple-binary-codec` `definitions.json`
(note `LoanPay` is 84; 83 is unassigned). Flag values from xrpl-py 5.2.0.

## What the device shows now

`LoanSet` (vector `36-loan-set/01-first-signer`): Transaction Type `Loan Set`, Account,
Payment Interval `2592000 s`, Grace Period `604800 s`, Payment Total `12`, Interest Rate
`0.5 %`, Loan Broker ID, Fee, Data `lr_0016`, Counterparty, Loan Origination Fee `100`,
Loan Service Fee `10`, Principal Requested `100000000`.

`VaultDeposit`: Vault ID, Amount (`XRP 100` / `USD 2500.5` + Issuer / `MPT 1000000` + MPT
Issuance ID), Fee. `LoanManage`: Flags `Default` / `Impair` / `Unimpair`. `LoanPay`: Flags
`Full Payment`. `DelegateSet`: `Permission [1]; Payment`, `Permission [2]; Set Trust Line`,
`Permission [3]; Trustline Authorize`.

## Known limits (deliberate, for review)

- `STNumber` values are printed in the vault asset's smallest unit (drops for XRP) with
  no currency: the asset lives on the Vault/LoanBroker ledger object, not in the signed
  bytes, so the device cannot name it.
- Fields inside a nested object (e.g. `CounterpartySignature.TxnSignature`) keep their plain
  label; objects are hidden markers in this app. A nested-object prefix is a follow-up.
- Types without a flags formatter keep the upstream behaviour for a non-zero `Flags`.
- `MPTokenIssuanceCreate/Set` and `Batch` remain blind-sign on purpose.

## Testing

- `cmake -B unit-tests/build unit-tests && make -C unit-tests/build && (cd unit-tests/build && ./test_tx)`:
  3/3 pass (host, gcc 14). Before the patch the same vectors give `NOT_SUPPORTED` x7,
  `EXCEPTION_OVERFLOW` x2, blind x10, clear x0.
- Speculos 0.27.1, Stax, SDK `API_LEVEL_27` @ `33323fcc`, ragger 1.47.4, 2026-10-24: `pytest tests/standalone --device stax --golden_run -k "loan or vault or broker or credential or delegate or permissioned or blind or mpt or batch or domain"` → 26 selected tests passed (the 20 new fixtures plus 4 existing blind-sign fixtures and 2 settings tests caught by the `-k` filter), snapshots written; verify run of the 16 lending vectors → 16 passed; full standalone suite → 142 passed, 11 skipped, 0 failed, the pre-existing Stax snapshots unchanged. Raw logs in `../logs/`. No physical device yet (Nano S Plus / Stax runs still to do before merge); the `.apdu` packaging step was skipped.
