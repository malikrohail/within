# RESULT - 005 app-xrp patch

Date: 2026-10-24, 14:35-15:05 EDT (this machine, no Docker). Upstream: LedgerHQ/app-xrp
`7b5185ff09b4b3d15df242b156a6aaadfc99f555` (master 2026-10-15, APPVERSION 2.8.2). The parser
in 2.8.1 (the version that failed on the Mac) differs from this commit by one line
(`NFTokenAcceptOffer` removed from the supported list in `fc49520`), so everything below
applies to 2.8.1 as well.

## 1. Root cause of APDU `0x680b` on a LoanSet

**One-line version:** the app had no reader for the `STNumber` data type (XRPL type code 9,
new in rippled 3.x), `LoanSet.PrincipalRequested` is an `STNumber`, and the parser's
"unknown data type" branch returns the SDK exception `NOT_SUPPORTED`, which on the current
Ledger SDK is `0xB`, so the sign handler answers `0x6800 | 0xB = 0x680b`.

Evidence chain (line numbers at `7b5185f`, before the patch):

1. `src/apdu/messages/sign_transaction.c:246-248`
   `int exception = parse_tx(&parse_context); if (exception && exception != BLIND_SIGN_REQUIRED) return send_error(0x6800 | (exception & 0x7FF));`
   This is the only place in the app that emits a `0x68xx` status (grep of `src/` for `0x68`).
2. `src/xrp/xrp_parse.c:504-558` `read_field_value()`: the `switch (field->data_type)` has
   cases for UINT8/16/32, HASH128/256, AMOUNT, VL, ACCOUNT, VECTOR256, ARRAY, OBJECT,
   PATHSET, ISSUE; `default: err.err = NOT_SUPPORTED;` at line 554. `src/xrp/fields.h:27-42`
   (`field_type_t`) has no 0x09 (`Number`), 0x03 (`UInt64`), 0x0A (`Int32`) or 0x15
   (`Hash192`).
3. `ledger-secure-sdk/include/errors.h:142` (master `51d2f39`, 2026-10-21):
   `#define NOT_SUPPORTED 0xB`. The app's host stub `unit-tests/include/os.h:13` still says
   `NOT_SUPPORTED 8` (the legacy numbering), which is why one would otherwise expect `0x6808`.
   `EXCEPTION_OVERFLOW` is `0x7`, `INVALID_STATE` `0x4`, `NOT_ENOUGH_SPACE` `0x6`.
4. xrpl.js `definitions.json` (fetched 2026-10-24): `PrincipalRequested` is
   `{"type":"Number","nth":14}`; `TYPES.Number = 9`. Canonical serialization orders fields
   by type code then field code, so in a `LoanSet` everything up to `Account` (type 8)
   parses, and the first byte of the first `Number` field (`0x9E` = type 9, field 14)
   lands in the `default` branch.
5. Reproduced on the host (`patch/before-after-host-parser.txt`): the unpatched parser
   returns `NOT_SUPPORTED` for all three `LoanSet` vectors, for `LoanBrokerSet`
   (`DebtMaximum` is a Number) and for `VaultCreate` (`AssetsMaximum`), and
   `EXCEPTION_OVERFLOW` (device `0x6807`) for the two MPT vectors (33-byte MPT amount read
   as an 8-byte XRP amount). `VaultDeposit`/`VaultWithdraw`/`LoanPay`/`LoanManage` never
   crashed: they have no Number field, so they reached the "unsupported type -> blind sign"
   branch (`xrp_parse.c:712-714`).

Note that the parser stops at the first unknown type *before* the supported-type check at
`xrp_parse.c:712`, so this is an error reply, not a fall-through to blind signing. That is
what the user on the Mac saw: `0x680b` even with blind signing enabled.

**The Speculos exit 255 is not explained by this code and was not reproduced here.**
`send_error()` is an ordinary `io_send_sw()`; `app_main()` only exits when `io_send_sw`
fails (`src/app_main.c:68`), and Speculos's `sys_os_sched_exit()` is a plain `_exit(code)`
(`speculos/src/bolos/os.c:186-190`). Candidates: the DMK transport tearing down the
exchange, or the test harness killing the container. Keep it as a separate observation
in the Ledger issue; do not attribute it to the parser.

## 2. What was verified

| Check | Result |
|---|---|
| Patch applies to a clean `7b5185f` worktree (`git apply --check`) | yes |
| Host build of `src/xrp/*` with gcc 14, `-Wall` defaults of the repo CMake | no errors, no new warnings |
| Existing cmocka suite `unit-tests` (`test_tx`, `test_printers`, `test_swap`) | 3/3 pass before and after (`test_tx` alone: 2 tests before, 3 after) |
| 104 pre-existing `.txt` expectations unchanged after the patch | yes (`git status` on `testcases/` shows only new files) |
| 17 new field-review vectors parse with `rc=0` and render as in their `.txt` | yes |
| 4 blind-sign vectors return `BLIND_SIGN_REQUIRED` (unknown type, Batch, unknown data type, MPTokenIssuanceCreate) | yes |
| Unpatched parser on the same vectors | 7 x `NOT_SUPPORTED`, 2 x `EXCEPTION_OVERFLOW`, 10 x blind, 0 clear (table in `patch/before-after-host-parser.txt`) |
| Regression found and fixed during the work | first version flagged IOU amounts as MPT (bit 0x20 is an exponent bit in issued amounts); caught by `08-check-cash/03-issued.raw` |

## 3. What was not verified

- **Device build** (arm toolchain, `ledger-app-builder-lite`) and the **Speculos screenshot**:
  no Docker access here (`sg docker` asks for a password; not escalated per the rules). The
  code uses only functions already used elsewhere in the app (`snprintf`, `strncpy`,
  `memcpy`, `read_hex`, `print_uint64_t`), so a device build should be routine, but it has
  not been run.
- **Ragger snapshots** for the 20 new vectors do not exist; first run must be `--golden_run`.
- The `CounterpartySignature` object renders its inner `TxnSignature` with the same label as
  the top-level one (`03-countersigned.txt`): both appear as `Txn Sig.`. Objects are hidden
  markers in this app; a prefix for nested-object fields would be a follow-up.
- STNumber values print in the vault asset's own unit (`Principal Requested; 100000000` is
  100 XRP in drops). The asset is on the Vault/LoanBroker ledger object, not in the
  transaction, so the device cannot know it. Documented in the PR text.
- `has_unknown_flags()` keeps the upstream behaviour for types without a flags formatter
  (`Flags` prints "No flags for transaction type N"); same as `EscrowCreate` today.
- The on-device `snprintf` supports `%u`/`%d`/`%s` (already used by `general.c`); `%03u`
  (used by the new rate formatter) is the same family as the existing `%02u`/`%07u` in
  `time.c`/`percentage.c`.

## 4. Field table used (source of truth: xrpl.js `definitions.json`, 2026-10-24)

Type codes: UInt16=1, UInt32=2, UInt64=3, Hash256=5, Amount=6, Blob=7, AccountID=8,
Number=9, Int32=10, STObject=14, STArray=15, UInt8=16, Vector256=19, Hash192=21, Issue=24.
Transaction types: MPTokenIssuanceCreate 54, MPTokenIssuanceDestroy 55, MPTokenIssuanceSet 56,
MPTokenAuthorize 57, CredentialCreate 58, CredentialAccept 59, CredentialDelete 60,
PermissionedDomainSet 62, PermissionedDomainDelete 63, DelegateSet 64, VaultCreate 65,
VaultSet 66, VaultDelete 67, VaultDeposit 68, VaultWithdraw 69, VaultClawback 70, Batch 71,
LoanBrokerSet 74, LoanBrokerDelete 75, LoanBrokerCoverDeposit 76, LoanBrokerCoverWithdraw 77,
LoanBrokerCoverClawback 78, LoanSet 80, LoanDelete 81, LoanManage 82, **LoanPay 84** (83 is
unassigned; the XLS-66 draft text's "83" is wrong, as the issues draft suspected).

| Field | Type/code | Shown as | Used by |
|---|---|---|---|
| ManagementFeeRate | UInt16/22 | percent (1/10 bp) | LoanBrokerSet |
| PermissionValue | UInt32/52 | permission name (tx code + 1, or granular 65537-65548) | DelegateSet |
| StartDate | UInt32/54 | UTC time | Loan (ledger) |
| PaymentInterval | UInt32/55 | `N s` | LoanSet |
| GracePeriod | UInt32/56 | `N s` | LoanSet |
| PaymentTotal | UInt32/60 | integer | LoanSet |
| CoverRateMinimum | UInt32/62 | percent | LoanBrokerSet |
| CoverRateLiquidation | UInt32/63 | percent | LoanBrokerSet |
| OverpaymentFee | UInt32/64 | percent | LoanSet |
| InterestRate | UInt32/65 | percent | LoanSet |
| LateInterestRate | UInt32/66 | percent | LoanSet |
| CloseInterestRate | UInt32/67 | percent | LoanSet |
| OverpaymentInterestRate | UInt32/68 | percent | LoanSet |
| SubscriptionDate | UInt32/75 | UTC time | VaultCreate |
| RedemptionDate | UInt32/76 | UTC time | VaultCreate |
| DomainID | Hash256/34 | hex | VaultCreate/Set, PermissionedDomain* |
| VaultID | Hash256/35 | hex | Vault*, LoanBrokerSet |
| LoanBrokerID | Hash256/37 | hex | LoanBroker*, LoanSet |
| LoanID | Hash256/38 | hex | LoanDelete/Manage/Pay |
| AssetsMaximum | Number/3 | decimal | VaultCreate/Set |
| DebtMaximum | Number/7 | decimal | LoanBrokerSet |
| LoanOriginationFee | Number/9 | decimal | LoanSet |
| LoanServiceFee | Number/10 | decimal | LoanSet |
| LatePaymentFee | Number/11 | decimal | LoanSet |
| ClosePaymentFee | Number/12 | decimal | LoanSet |
| PrincipalRequested | Number/14 | decimal | LoanSet |
| LoanScale | Int32/1 | integer | Loan (ledger) |
| Data | Blob/27 | ASCII if printable, else hex | Vault*, LoanBroker*, LoanSet |
| MPTokenMetadata | Blob/30 | hex | VaultCreate, MPT |
| CredentialType | Blob/31 | ASCII if printable, else hex | Credential*, Credential{} |
| Holder | AccountID/11 | address | VaultClawback, MPT |
| Delegate | AccountID/12 | address | any (delegated tx) |
| Subject | AccountID/24 | address | CredentialCreate/Delete |
| Counterparty | AccountID/26 | address | LoanSet |
| CredentialIDs | Vector256/5 | count + `Credential ID [i]` rows | VaultWithdraw, Payment, ... |
| MPTokenIssuanceID | Hash192/1 | hex (also synthesized from MPT amounts) | MPT*, MPT amounts |
| Asset (MPT form) | Issue/3, 44 bytes | `MPT <48-hex issuance id>` | VaultCreate |
| Scale, AssetScale, WithdrawalPolicy, VaultKind | UInt8/4,5,20,22 | integer | VaultCreate, MPT |
| Permission, Credential, RawTransaction, BatchSigner, CounterpartySignature | STObject/15,33,34,35,37 | hidden marker (names for array titles) | DelegateSet, PermissionedDomainSet, Batch, LoanSet |
| AcceptedCredentials, Permissions, RawTransactions, BatchSigners | STArray/28,29,30,31 | hidden marker | same |
| Flags | VaultCreate: Private 0x10000, Share Non Transferable 0x20000; LoanManage: Default 0x10000, Impair 0x20000, Unimpair 0x40000; LoanPay: Overpayment 0x10000, Full Payment 0x20000, Late Payment 0x40000 (xrpl-py 5.2.0 enums) | names | |

STNumber wire format (xrpl-py `types/number.py`, matches rippled `STNumber`): 8-byte signed
mantissa then 4-byte signed exponent, big-endian; value = mantissa x 10^exponent; zero is
mantissa 0. Lending rates: 1/10 basis point, 100000 = 100 % (XLS-66 note, research_notes).

## 5. Surprises

- The SDK renumbered the legacy exception constants; the app's own unit-test stub still has
  the old numbers, so the status byte is misleading unless you read the real `errors.h`.
- xrpl-py writes the MPT sequence byte-swapped inside an `Issue` (and reads it back the
  same way, "for compatibility with rippled"); the formatter swaps it back so the device
  shows the same 48-hex `MPTokenIssuanceID` an explorer shows.
- The app already defined `XRP_VL_DATA` (0x1B) in `fields.h` but never named it.

## 6. Next step (written 2026-10-24; the PR is now open, see below)

On a Mac (Docker + Speculos): build for Stax and Nano S Plus, run
`pytest tests/standalone --device stax --golden_run -k "36-loan-set or 33-vault-deposit"`,
attach the PNGs, then open the PR with `patch/PR-DESCRIPTION.md`. Sideload the Nano S Plus
build with `make load` once the physical device arrives.

Update 2026-10-25: the patch is open as draft PR [LedgerHQ/app-xrp#97](https://github.com/LedgerHQ/app-xrp/pull/97).

## 7. Built and run in Speculos (2026-10-24, 17:10-17:35 EDT, a Linux build host, no Docker, no sudo)

The patched app was compiled for Ledger Stax and exercised in Speculos through the app's own ragger functional-test suite, the harness LedgerHQ's CI uses to accept pull requests. Reproduce with `./build_local.sh` (Docker-free; no new Docker images were allowed on the Mac, and the build host's Docker socket is root-only).

| Item | Result |
|---|---|
| Pinned versions | Ledger secure SDK `API_LEVEL_27` @ `33323fcc80619226f06b9d426dccaa5f4755efec` (2026-10-21); Speculos 0.27.1; ragger 1.47.4; xrpl-py 5.2.0; pytest 8.4.1; qemu-arm 10.0.13 (Debian 1:10.0.13+ds-0+deb13u1); clang 18.1.8; Arm GNU 13.3.Rel1 |
| Toolchain | clang 18.1.8 (LLVM tarball) + Arm GNU 13.3 sysroot, Ledger secure SDK branch `API_LEVEL_27` (`de9f8cb`-era master lacks an API level and Speculos rejects it; `API_LEVEL_22` lacks `status_words.h` the app needs; 24 to 27 are what the Speculos 0.27.1 wheel ships `stax-api-level-shared-*.elf` for) |
| Binary | `app-xrp-2.8.2-lending-stax-api27.elf`, 238 KB, sha256 in the `.sha256` file next to it. Loadable in any Speculos >= 0.27 with `--model stax` |
| Emulator | Speculos 0.27.1 from PyPI (its ARM launcher needs `qemu-arm-static`; Debian 13 ships the static binary in `qemu-user`, unpacked locally) |
| Golden run, selected tests | **26 selected tests passed** (`logs/01-golden-run-new-vectors.log`): the `-k` selection (loan, vault, broker, credential, delegate, permissioned, blind, mpt, batch, domain) picks up the 20 new raw fixtures, 4 pre-existing blind-sign fixtures and 2 pre-existing settings/menu tests (counted against upstream `7b5185f`). An earlier pair of runs reported 16 + 14 = 30 because four tests matched both selections. New vectors added by the patch: 20, as the README says |
| New vectors, verify run | 16 passed against the goldens just written (`logs/02-verify-lending-vectors.log`) |
| Full standalone suite | **142 passed, 11 skipped, 0 failed** in 4 min 15 s (`logs/03-full-stax-suite.log`, run with `-v -rs`). The 11 skips are the suite's own `skip invalid tx` vectors (malformed payments, unknown NFToken flags, an invalid vector length), unchanged by the patch. The 123 pre-existing vectors still match their committed Stax snapshots, so the patch changes no existing screen |
| Screens kept in this folder | `screens/` (89 PNG): `36-loan-set`, `38-loan-manage`, `35-loan-broker-set`, `32-vault-create`, `37-loan-pay`, `33-vault-deposit` |

What a `LoanSet` looks like on the Stax (`screens/36-loan-set/01-first-signer/00001..00003.png`): page 2 of 5 "Transaction Type: Loan Set / Account / Payment Interval 2592000 s / Grace Period 604800 s / Payment Total 12"; page 3 "Interest Rate 0.5 % / Loan Broker ID / Fee XRP 0.000012 / Data lr_0016"; page 4 "Counterparty / Loan Origination Fee 100 / Loan Service Fee 10 / Principal Requested 100000000". `LoanManage` page 2 shows "Flags: Default" and the Loan ID.

Before the patch the same APDU returned `0x680b` and crashed the emulator (section 1). After it, the app shows the lending fields, every field named, and signs.

Nits seen on the screens, for the PR description, not blockers: `Principal Requested` is shown as a raw `STNumber` (`100000000`, drops) because a Number carries no currency; rendering it as `XRP 100` would need the vault asset, which the transaction does not carry. `Loan Origination Fee` and `Loan Service Fee` are shown raw (they are amounts in the asset's units in XLS-66, not rates), and 32-byte IDs wrap over four lines.

Not done: no physical device (none owned yet), so this is Speculos only; the `.apdu` packaging for `ledgerblue.loadApp` was skipped. The Mac's stage Speculos still runs the unpatched 2.8.1; swapping it for this elf is a separate decision because the wallet's device gate is frozen.

