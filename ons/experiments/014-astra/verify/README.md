# Verify the approval-to-loan binding

From the repository root, with the project's xrpl-py 5.2.0 environment installed:

```sh
lending/.venv/bin/python -I ons/experiments/014-astra/verify/verify.py --approval 8AC151230EAF1AC6F9928CF3E5A5F25DF2DE6AC2454C76DD6136466987B7919C --loanset C9627B03199430510F43567C6A93A446116606AC4DA5FAE763BA8FAA6CDDDF13
```

Expected last line: `BINDING PASS` (exit 0). A new reader can install an isolated environment without any stage services:

```sh
python3 -I -m venv /tmp/xrpl-binding-verifier
/tmp/xrpl-binding-verifier/bin/python -I -m pip install -r ons/experiments/014-astra/verify/requirements.txt
/tmp/xrpl-binding-verifier/bin/python -I ons/experiments/014-astra/verify/verify.py --approval 8AC151230EAF1AC6F9928CF3E5A5F25DF2DE6AC2454C76DD6136466987B7919C --loanset C9627B03199430510F43567C6A93A446116606AC4DA5FAE763BA8FAA6CDDDF13
```

Python 3.10+ and xrpl-py **5.2.0** are required. Use `-I` to isolate Python from working-directory imports and environment-injected module paths. The script never imports the wallet/desk, reads credentials, signs, submits a transaction, or calls local stage services. It only calls JSON-RPC `tx` on public testnet/devnet HTTPS nodes. Optional `--testnet-url` and `--devnet-url` select alternative testnet/devnet nodes; network names are caller assertions, not cryptographically authenticated chain identifiers. Do not supply mainnet URLs. No cache is read or written.

## What PASS means

Both requested transactions returned `validated: true`, `tesSUCCESS`, the requested hashes, and Payment/LoanSet types from the chosen nodes. Remove node metadata and `CounterpartySignature` from the validated LoanSet while retaining the borrower signature, canonical-encode with the pinned binary codec, and SHA256 those bytes. That digest equals the approval Payment's binary `loan-approval` memo:

`70C795FCADB20C0FE1EC53F722817476B2738853C7F448E3254C5205F616E646`

The decoded canonical loan also reproduces the UTF-8 `loan-terms` memo exactly:

`approve loan 30 XRP to rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG 6 payments`

Principal is interpreted as **XRP drops for this known XRP-vault demonstration**. Whole drops are converted using exact integer arithmetic, including six decimal places where needed; there is no floating-point rounding or truncation. This is not a generic token-vault verifier: the script does not fetch the vault asset. It rejects unsupported borrower multisigning, missing signature fields, unknown fields dropped by the codec, malformed or duplicate target memos and invalid principal/payment counts. Both target memos are mandatory here, unlike the desk's legacy optional-terms behavior.

Output includes observed approval Account/public key/destination/amount, requested and returned-identity checks, encoded field names and byte length, digest, decoded terms and comparison booleans. It intentionally does not print the full signed blob. Public signatures are not secrets, but the blob is unnecessary to review the binding.

## What PASS does not mean

- No on-ledger link or atomic enforcement exists between these two networks. The desk implements the approval gate off-chain; the broker signature is software-generated.
- This is **public-data binding**, not authorization. The script shows the observed approver; it does not pin an expected authorized account, check desk policy, establish freshness/replay prevention, or prove the desk actually checked the receipt before signing.
- The demonstrated signing environment was a **Speculos emulator**, not physical hardware. Public transaction data cannot prove hardware origin, emulator origin, a human review/tap, or that every committed field was displayed.
- The digest commits to the borrower-signed blob; the readable terms expose only principal, borrower and payment count. This is not a full field-by-field LoanSet review or CPT counterparty support.
- RPC validation is trusted as reported by the selected public nodes. This is not an independent consensus/light-client proof or a separate cryptographic signature audit.

## Negative control and errors

```sh
lending/.venv/bin/python -I ons/experiments/014-astra/verify/verify.py --approval 8AC151230EAF1AC6F9928CF3E5A5F25DF2DE6AC2454C76DD6136466987B7919C --loanset 0CE7AFEF47E0F092CFABBEB78DAD6848B1BE8E5338C5BFB9CCC0804A49B16243
```

Expected last line: `BINDING FAIL: digest_match, terms_match` (exit 1). Both transactions individually validate, but the approval does not bind to this different experiment-011 loan.

`BINDING ERROR: ...` (exit 1) means unavailable or malformed evidence, wrong transaction identity/type, unsuccessful/unvalidated transaction or unsupported schema. It is distinct from a demonstrated memo mismatch. RPC outages never become a PASS or a cached result; rerun explicitly if a public node is temporarily unavailable. Invalid CLI arguments also exit 1; `--help` exits 0.

Full public-node transcripts are in [RESULT.md](RESULT.md), including the positive and negative control. The first transient HTTP failure is retained separately. Offline adversarial tests:

```sh
lending/.venv/bin/python -I ons/experiments/014-astra/verify/test_verify.py
```

Based on `innovation/proof-of-concept/rpc_capture.py`. The app-xrp patch is open as draft PR [LedgerHQ/app-xrp#97](https://github.com/LedgerHQ/app-xrp/pull/97); the findings are written up and not filed yet.

## Optional static page status

`verify.html` was implemented after the CLI. Its pinned xrpl.js 5.3.0 UMD codec loads, but a direct `file://` browser run against the public testnet node is **blocked by CORS** (no Access-Control-Allow-Origin); both control runs report ERROR. It is retained as an experimental artifact, not a working verification path. Use the CLI above. No server, proxy, browser-security bypass or live-service change was added. See RESULT.md and BROWSER-RESULT.json.
