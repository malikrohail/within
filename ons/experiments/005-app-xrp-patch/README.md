# 005 - app-xrp patch: the Ledger XRP app shows the lending fields of XLS-65/66 transactions

Written 2026-10-24 (hackathon day 1). A patch for a gap between the Ledger XRP app and the lending amendments.

## Goal

Make Ledger's XRP device app ([LedgerHQ/app-xrp](https://github.com/LedgerHQ/app-xrp), C)
understand the XRPL 3.x transaction types and fields so that a `LoanSet` (XLS-66) and a
`VaultDeposit` (XLS-65) render human-readable fields on the device instead of failing.

Starting point (from an earlier spike on a Mac, 2026-10-24 16:40 ET): app 2.8.1 in
Speculos (Stax) answered APDU status `0x680b` to an encoded `LoanSet` and the container
exited 255. The app's supported-type list stopped at `AMMDelete` (40) and `fields.c` had no
names for any Loan, Vault, Batch, Credential, MPT or DelegateSet field.

## What is in this folder

| Path | What |
|---|---|
| `app-xrp/` | clone of LedgerHQ/app-xrp at `7b5185ff09b4b3d15df242b156a6aaadfc99f555` (master, 2026-10-15, `APPVERSION` 2.8.2) with the patch applied in the working tree. Gitignored here; treat as untrusted upstream code. |
| `patch/app-xrp-lending-fields.diff` | the full diff (`git diff --binary`, 70 files: 13 source/test files, 57 test-vector files). Applies cleanly to `7b5185f` with `git apply`. |
| `patch/PR-DESCRIPTION.md` | draft pull-request text for LedgerHQ/app-xrp. |
| `patch/before-after-host-parser.txt` | parser result for every new vector, unpatched vs patched (host build). |
| `make_vectors.py` | generates the 20 new test vectors (`.json` + `.raw`) with xrpl-py 5.2.0. |
| `logs/` | raw pytest output of the three Speculos runs (`-v -rs`, skip reasons included): golden run of the 26 new vectors, verify of the 16 lending vectors, full Stax suite. Force-added: the root `.gitignore` ignores `*.log` |
| `build_local.sh` | Docker-free build + Speculos ragger run (clang 18, Arm GNU 13.3, SDK `API_LEVEL_27`, Speculos wheel, static qemu-arm), verified on a Linux build host 2026-10-24 |
| `app-xrp-2.8.2-lending-stax-api27.elf` (+ `.sha256`) | the built Stax binary; loads in Speculos >= 0.27 with `--model stax` |
| `screens/` | 89 Stax snapshots from the ragger golden run for the lending, vault, broker vectors (RESULT.md section 7) |
| `RESULT.md` | what was verified, what was not, the `0x680b` root cause with file:line evidence, the field table. |

## Preparing `app-xrp/` on a fresh checkout

`app-xrp/` is gitignored (upstream code, 70 MB with build output). Before `./build_local.sh` on a machine that does not have it:

```bash
git clone https://github.com/LedgerHQ/app-xrp.git app-xrp
git -C app-xrp checkout 7b5185ff09b4b3d15df242b156a6aaadfc99f555
git -C app-xrp apply ../patch/app-xrp-lending-fields.diff
```

`build_local.sh` does these three steps itself when `app-xrp/Makefile` is missing. Pinned versions it was verified with: Ledger secure SDK `API_LEVEL_27` at `33323fcc80619226f06b9d426dccaa5f4755efec` (2026-10-21), Speculos 0.27.1, ragger 1.47.4, xrpl-py 5.2.0, pytest 8.4.1, qemu-arm 10.0.13, clang 18.1.8, Arm GNU 13.3.Rel1.

## What the patch changes (app-xrp `src/xrp/`, 12 files, +~700 lines, -17)

1. **No more APDU error on unknown data types.** `read_field_value()` learns the fixed-size
   XRPL types the app lacked: `STNumber` (type 9, 12 bytes), `UInt64` (3), `Int32` (10),
   `Hash192` (21). A type it still cannot size now stops parsing and routes the transaction
   to the blind-signing flow (`BLIND_SIGN_REQUIRED`) instead of returning
   `0x6800 | NOT_SUPPORTED`. A `stopped_early` flag guarantees such a transaction can never
   reach the normal field-by-field review.
2. **MPT amounts and MPT assets** parse (`0x60`-prefixed 33-byte amounts; 44-byte
   `Issue` with the ACCOUNT_ONE marker). Before, both ended in `EXCEPTION_OVERFLOW`.
3. **26 transaction type names** (MPT 54-57, Credentials 58-60, PermissionedDomain 62-63,
   DelegateSet 64, Vault 65-70, Batch 71, LoanBroker 74-78, Loan 80/81/82/84). All but
   MPT* and Batch are added to `is_supported_transaction_type()`, so they get the field-by-field review.
4. **Field names** for the XLS-65/66, Credential, PermissionedDomain and DelegateSet
   fields exercised by the 20 new fixtures (table in `RESULT.md`; the 26 transaction-type
   names are separate from full field review), plus formatters: STNumber as a decimal; lending rates
   (1/10 bp) as percent (`500` -> `0.5 %`); `PaymentInterval`/`GracePeriod` as seconds;
   `StartDate`/`SubscriptionDate`/`RedemptionDate` as UTC timestamps; `PermissionValue`
   as the permission name (`Payment`, `Trustline Authorize`); flags for `VaultCreate`
   (Private, Share Non Transferable), `LoanManage` (Default, Impair, Unimpair) and
   `LoanPay` (Overpayment, Full Payment, Late Payment) with the unknown-bit check.
5. **Tests**: 17 field-review vectors (folders `30-` to `38-`) and 3 blind-sign vectors added
   to `tests/standalone/testcases/` and to the cmocka suite `unit-tests/src/test_tx.c`,
   which gains a third test asserting that blind-sign vectors return `BLIND_SIGN_REQUIRED`.

## What a LoanSet shows on the device after the patch

From `tests/standalone/testcases/36-loan-set/01-first-signer.txt` (host rendering, same
code path as the device):

```
Transaction Type; Loan Set
Account; rTooLkitCksh5mQa67eaa2JaWHDBnHkpy
Payment Interval; 2592000 s
Grace Period; 604800 s
Payment Total; 12
Interest Rate; 0.5 %
Loan Broker ID; b2b2...b2b2
Fee; XRP 0.000012
Data; lr_0016
Counterparty; rPT1Sjq2YGrBMTttX4GZHjKu9dyfzbpAYe
Loan Origination Fee; 100
Loan Service Fee; 10
Principal Requested; 100000000
```

`VaultDeposit` shows `Vault ID`, `Amount; XRP 100` (or `USD 2500.5` + `Issuer`, or
`MPT 1000000` + `MPT Issuance ID`) and `Fee`.

## How to build with Docker

```sh
cd ons/experiments/005-app-xrp-patch   # from the repository root
git clone https://github.com/LedgerHQ/app-xrp && cd app-xrp
git checkout 7b5185ff09b4b3d15df242b156a6aaadfc99f555
git apply ../patch/app-xrp-lending-fields.diff      # or use the already-patched app-xrp/ here

docker run --rm -it -v "$(pwd):/app" --user "$(id -u):$(id -g)" \
  ghcr.io/ledgerhq/ledger-app-builder/ledger-app-builder-lite:latest
# inside the container:
BOLOS_SDK=$STAX_SDK   make -j      # -> build/stax/bin/app.elf
BOLOS_SDK=$NANOSP_SDK make -j      # -> build/nanos2/bin/app.elf (Nano S Plus sideload)
BOLOS_SDK=$FLEX_SDK   make -j      # -> build/flex/bin/app.elf
```

## How to test

### Host unit tests (done here, 3/3 pass; no Docker needed)

```sh
cd app-xrp
cmake -B unit-tests/build unit-tests        # needs libcmocka-dev, libssl-dev, gcc, cmake
make -C unit-tests/build
cd unit-tests/build && ./test_tx            # must run from unit-tests/build (relative paths)
```

Without root for cmocka: build it from source and pass
`-DCMAKE_C_FLAGS=-I<cmocka>/include -DCMAKE_EXE_LINKER_FLAGS=-L<cmocka>/lib`, run with
`LD_LIBRARY_PATH=<cmocka>/lib`.

### Speculos, manual (gives the screenshot)

```sh
docker run --rm -it -v "$(pwd):/app" -p 5000:5000 \
  ghcr.io/ledgerhq/ledger-app-builder/ledger-app-dev-tools:latest
# inside:
speculos --model stax --display headless --api-port 5000 build/stax/bin/app.elf &
# in a second shell inside the container (the APDU call blocks until approve/reject):
curl -s -X POST -d @- http://127.0.0.1:5000/apdu <<'EOF'
{"data":"e0040040e7058000002c800000908000000000000000000000001200502400000007201b0061a800203700278d00203800093a80203c0000000c2041000001f45025b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b268400000000000000c732102b79da34f4551ca976b66aa78a55c43707ec2bb2bec39f95bd53f24e2e45a9e67701b076c725f3030313681140511e17db83bb6f113939d67bc8ea539edc926fc801a14f667b0ca50cc7709a220b0561b85e53a48461fa8990de0b6b3a7640000fffffff09a0de0b6b3a7640000ffffffef9e0de0b6b3a7640000fffffff6"}
EOF
curl -s http://127.0.0.1:5000/screenshot -o loanset-stax-1.png
# Stax: tap right half of the screen to page, then screenshot again
curl -s -X POST -d '{"action":"press-and-release","x":300,"y":620}' http://127.0.0.1:5000/finger
```

The APDU is `CLA=E0 INS=04 P1=00 (single chunk) P2=40 (secp256k1) Lc=E7`, data = BIP32 path
(`05` elements: `44'/144'/0'/0/0`) followed by the 210-byte serialized `LoanSet` from
`tests/standalone/testcases/36-loan-set/01-first-signer.raw` (the host sends `encode()`
output; the app prepends `STX\0` itself). Blind signing can stay **off**: the point of the
patch is that this transaction gets the field-by-field review. Expected: no `0x680b`; the review screens
show the fields listed above; approve returns a DER signature with `0x9000`.

Any other vector: `xxd -p <file>.raw | tr -d '\n'` and prefix with
`e0040040<Lc>058000002c80000090800000000000000000000000` where `Lc` = 21 + raw length
(hex). Blobs over 234 bytes need chunking (`P1=80` first, `81` middle, `01` last, 255-byte
APDUs); `tests/standalone/xrp.py::sign()` does this.

### Speculos, automated (ragger; also produces the screenshots as snapshots)

```sh
# inside ledger-app-dev-tools, after building:
pip install -r tests/standalone/requirements.txt
pytest tests/standalone --device stax --golden_run -k "36-loan-set or 33-vault-deposit"
# snapshots land in tests/standalone/snapshots/stax/36-loan-set/01-first-signer/*.png
pytest tests/standalone --device stax -k "36-loan-set or 33-vault-deposit"   # replays them
```

Golden snapshots for the 20 new vectors do not exist yet (no Speculos here); the first run on
the Mac must be a `--golden_run` for the new folders, then the full suite should pass.

## Status

- Patch: build-ready, applies cleanly, host parser suite passes (3/3), before/after table in
  `patch/before-after-host-parser.txt`.
- Device build and Speculos screenshot: **not done here** (Docker is installed but this user
  is not in the `docker` group; `sg docker` prompts for a password). Next step is on
  a Mac with Docker, see above. (Done later without Docker: RESULT.md section 7.)
- Network use: `git clone` of app-xrp, ledger-secure-sdk, speculos, cmocka; one fetch of
  xrpl.js `definitions.json`. No devnet or mainnet traffic.
