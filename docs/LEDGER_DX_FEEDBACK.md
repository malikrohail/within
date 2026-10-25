# Ledger developer-experience feedback (for Ledger's "Documentation Feedback" section)

Collected while building Policy Wallet on the pre-release XRP Device Management Kit signer, Oct 24 2026. Each item: what we hit, where, what would have saved time.

## 1. The XRP signer page does not say the output is a DER signature
`developers.ledger.com/docs/device-interaction/dmk-ts/references/signers/xrp`. The workshop README says it ("The output is a DER signature (Uint8Array)") but the reference page does not, and `TxnSignature` on XRPL is the DER bytes as upper hex. One sentence plus the `bufferToHexaString(sig, false).toUpperCase()` line would remove a guess.

## 2. `encode` vs `encodeForSigning` is the single most likely mistake and is only in the workshop README
The XRP device app adds the signing prefix itself, so callers must pass `encode(tx)`, not `encodeForSigning(tx)`. Put this in the signer reference with a red box. Every other XRPL signing path in the ecosystem uses `encodeForSigning`, so muscle memory is wrong here.

## 3. No Node.js example for the XRP signer
The reference shows browser transports. The workshop README has one paragraph on `speculosTransportFactory` and `nodeHidTransportFactory` for Node. A copy-pasteable 30-line Node script (build DMK, connect Speculos, get address, sign a Payment) is what an agent backend needs, and it is what we had to assemble ourselves.

## 4. Speculos touch coordinates for Stax are undocumented
To script a demo (or integration-test a hold/approve flow) you need the REST `/finger` coordinates for "next" and "hold to sign" on each model. We found Stax by reading screenshots: next at (350,620), hold-to-sign button at (336,515) with a ~3 s press. A table per model in the Speculos README, or a `/button/sign` convenience endpoint, would make device-flow CI possible.

## 5. The workshop app's embedded Speculos screen does not accept taps from an automated browser
Clicks delivered through browser automation on the `<img>` screen did not advance the review; the REST API did. If the screen element forwarded pointer events via the same `/finger` call, automated QA could use the app directly.

## 6. "Blind signing" setting appears without explanation
The device app shows a "Blind signing" toggle in settings. Nothing in the signer docs says which XRPL transaction types need it. A list (which types are shown field-by-field, which need blind signing) would prevent a demo-day surprise.

## 7. Clear Signing has no XRPL equivalent, and the docs do not say so up front
The Clear Signing docs are EVM/ERC-7730 only. A one-line note on the XRP signer page ("XRPL transactions are displayed by the device app; there is no metadata format yet") would stop people looking for it. The hackathon page says it, the docs do not.

## 8. Version pinning guidance for the pre-release
`@ledgerhq/device-signer-kit-xrp` is pre-release. The reference page should say which `device-management-kit` and transport versions it was tested with. We pinned to the workshop's `package.json` to be safe.

## 9. Two DMK clients on one Speculos silently corrupt each other's exchanges
With the workshop app open in a browser (its DMK session polls `getAppAndVersion`) and a Node DMK client signing at the same time, the Node client's `signTransaction` returned `6901` and the signature was delivered on the browser's request. Nothing in the DMK or Speculos docs says a device session is exclusive, and nothing fails loudly. A warning in the Speculos README, or a session lock in the transport (reject a second connection, or at least log it), would save a confusing hour.

## 10. Review page count depends on the transaction, so scripted approval cannot use a fixed tap count
A Payment with no memos reviews as 3 pages on Stax; the same Payment with the x402 invoice memo reviews as 5. Reject also needs a second "Yes, reject" tap. For CI or demo scripting against Speculos, a documented way to detect "on the sign page" (an `/events` marker or a screen-text endpoint) would replace screenshot polling.

## 11. XRP app 2.8.1 cannot clear-sign `DelegateSet` (PermissionDelegation), so granting an agent spending rights is a blind signature
With blind signing off (the default), signing a treasury `DelegateSet` returned `6985` and left this screen on the Stax: "This transaction cannot be clear-signed. Enable blind signing in the settings to sign this transaction." with "Go to settings" and "Reject transaction". The screen stays up after the APDU has already failed, so a script must dismiss it itself. With blind signing on, the review is: "Blind signing ahead. This transaction's details are not fully verifiable. If you sign, you could lose all your assets." (Continue anyway / Back to safety). Then "Review transaction, Blind signing required." Then a details page showing "Transaction Type: Unknown", Account, Fee, Authorize, and the permission list as "Unknown [1]: 1". Then "Sign transaction? Hold to sign". The device shows the grantee address but not which permission is granted ("Payment" appears as "1"). That permission is exactly the field a user must check before they let an agent spend from their treasury. A revoke (empty `Permissions`) shows the same pages without the "Unknown [1]" row, so on the device a grant and a revoke differ only by one unlabeled row. Asks: a parser for `DelegateSet` (and the other amendment-era types) in the XRP app, or a documented list of the types that need blind signing (see 6). Demo talking point: this gap is why the Policy Wallet Preview module exists. It shows the human what the device cannot.

## 12. XRP app 2.8.1 rejects an XLS-66 `LoanSet` (`0x680b`); its fixed signing prefix also rules out `CounterpartySignature`
We wanted the Ledger to co-sign a held loan: the counterparty signature on a `LoanSet` (XLS-66 Lending Protocol, devnet). The setup was device-signer-kit-xrp 0.2.0, Speculos Stax with XRP app 2.8.1 and blind signing ON. The script is `wallet/scripts/spike-counterparty.ts`. Sending `encode()` of the LoanSet signing fields (borrower first-party signed, `TxnSignature` removed) failed:
- `signTransaction` returned APDU status **`0x680b`** ("Unexpected device exchange error"). No review page was shown.
- Speculos closed the HTTP socket ("other side closed").
- The `speculos-xrp` container died with **exit code 255**: `docker events` showed `die … exitCode=255`, then `destroy`, because it runs with `--rm`.

The app's own answer is the `0x680b` rejection (no reader for the `Number` type). The emulator exit that followed in our run is unexplained: we have not shown that the app caused it. Because the container runs with `--rm`, the exit also cut off every other client sharing it. We restored it from the RUNBOOK command (same seed, same device address) and had to re-enable blind signing by hand.

A parser alone would not fix this. The app prepends the first-party prefix `STX\0` itself (finding 2). Under `fixCleanup3_4_0`, which is enabled on devnet (rippled 3.4.1), a counterparty signature must cover the `CPT\0` prefix (`0x43505400`). We checked on devnet with throwaway unfunded keys, no device:
- xrpl.js `signLoanSetByCounterparty` (CPT) gives `terNO_ACCOUNT`, so the signature checks pass.
- The same key signing the `STX\0` data gives `invalidTransaction: fails local checks: Counterparty: Invalid signature.`, for both secp256k1 and ed25519.

The same will apply to sponsor signatures, which use the `SPN\0` and `SPM\0` prefixes. Asks:
1. A parser for the XLS-65/66 types (`LoanSet`, `LoanPay`, `LoanManage`, `Vault*`, `LoanBroker*`, including the `STNumber` amounts).
2. A sign mode, as a P2 flag or a field-driven choice, that uses the counterparty and sponsor prefixes.
3. A clear on-screen error for an unknown type, in addition to the `0x680b` status the app already returns.

Our workaround: the device signs a 1-drop approval Payment from the treasury, with `sha256` of the signed LoanSet blob in a Memo. The desk co-signs the LoanSet with its own key only after that Payment validates.

**Fix status (2026-10-24):** our app-xrp patch (`ons/experiments/005-app-xrp-patch`, 5fc3819) adds the XLS-65/66 parser (item 1 above). In Speculos the patched Stax build shows the lending fields of a `LoanSet` and signs it, where the stock app rejects it, and the app's own ragger suite passes 142 passed / 11 skipped / 0 failed. It does not add the counterparty prefix (item 2), so a device `CounterpartySignature` is still not possible and the workaround above stays. Opened upstream on 2026-10-25 as draft PR [LedgerHQ/app-xrp#97](https://github.com/LedgerHQ/app-xrp/pull/97). The issue drafts are not filed yet.

## Things that were good
- The workshop README's "How to sign an XRPL transaction with the DMK" five-step list is exactly right and got us to `tesSUCCESS` in under an hour on the emulator.
- Speculos with the prebuilt XRP app for every model, one `docker run`, no build step, was the reason the device work was not the critical path.
