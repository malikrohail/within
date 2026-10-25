# Application previews for XRPL: a metadata format and an in-app parser

This is the Clear Signing idea applied to XRPL in our wallet and dashboard, not on the device: Ledger's Clear Signing covers ERC-7730 (EVM) only, and XRP app 2.8.1 does not clear-sign the amendment-era types below.

This document describes a metadata format and an in-app parser that turn XRPL payloads into plain-language summaries before signing. The format lives in `preview/format/*.json`. The parser is `describe()` in `preview/src/`; see [preview/README.md](../preview/README.md).

## 1. Problem

The XRP app (2.8.1) on the Stax cannot clear-sign amendment-era transaction types. We watched it fail on `DelegateSet` twice on the Speculos emulator ([docs/LEDGER_DX_FEEDBACK.md](LEDGER_DX_FEEDBACK.md), finding 11).

**Blind signing off (the default).** The device refuses with `6985` and shows: "This transaction cannot be clear-signed. Enable blind signing in the settings to sign this transaction."

**Blind signing on.** The pages, verbatim:

| Page | Text |
|---|---|
| Warning | "Blind signing ahead. This transaction's details are not fully verifiable. If you sign, you could lose all your assets." (Continue anyway / Back to safety) |
| 1 of 3 | "Review transaction. Blind signing required." |
| 2 of 3 | "Transaction Type: Unknown", Account, Fee, Authorize, **"Unknown [1]: 1"** |
| 3 of 3 | "Sign transaction? Hold to sign" |

The permission being granted ("Payment") shows as `Unknown [1]: 1`. A revoke (empty `Permissions`) shows the same pages without that one row. On the device, a grant and a revoke differ by one unlabeled line.

Why this matters for agent wallets:

- The one field a human must check before an agent may spend from a treasury is the permission list. The device does not name it.
- An agent wallet signs many transactions of types the user has never seen. `DelegateSet`, `Batch`, `LoanSet`, `SignerListSet` and `AccountSet` can move funds or change who controls the account.
- A blind-signing prompt trains the user to tap "Continue anyway". The warning is identical for a harmless type and a dangerous one.
- Clear Signing is the control that lets a human approve what an agent proposes. Without it, approval is a formality.

## 2. The format

One JSON file per `TransactionType` in `preview/format/`. The parser is data-driven: adding a type means adding a file and listing it in `preview/src/descriptors-*.ts`. Types are in `preview/src/types.ts`.

### Descriptor

| Field | Meaning |
|---|---|
| `type` | The `TransactionType` this file describes. It is the lookup key. |
| `title` | Intent title with placeholders. Example: `"Pay {Amount\|amount} to {Destination\|account}"`. |
| `summary` | One sentence for logs. Same placeholders. Defaults to `title`. The engine appends the worst non-info risk: `(danger: …)`. |
| `variants[]` | Optional `{ when, title, summary? }`. The first variant whose `when` holds replaces the title and summary. One file then covers a grant and a revoke (`DelegateSet`) or default, impair and unimpair (`LoanManage`). |
| `fields[]` | Rows of the card, in order. See below. |
| `risk[]` | Conditions that add a `Risk` row. See below. |

**Placeholders.** `{Path}` or `{Path|format}`. A missing path renders as `?`. No format means `raw`.

**Paths.** Dot paths into `tx_json`: `Amount.value`, `Memos`. No roots, no slices, no wildcards.

### Fields

`{ path, label, format, risk?, required? }`

- `path`: where to read in `tx_json`.
- `label`: the row label on the card.
- `format`: the name of a formatter (list below). Default `raw`.
- `risk`: `info`, `warn` or `danger`. Forces a minimum risk level on that row. The row takes the higher of this and the formatter's own risk.
- `required`: if the field is absent, show the row as `missing` with `warn`. Without `required`, an absent field is skipped.

A formatter may return one value or several whole lines (memos, inner transactions). A format name that does not exist renders as `(unknown format "x")` with `warn`.

### Risk rules

`{ when, level, text }`. When `when` is true, the card gets a `Risk` row with `text` at `level`.

| `when` | True if |
|---|---|
| `Path` | the field is present and not empty |
| `!Path` | the field is absent or empty |
| `Path & 0x00020000` | any bit in the mask is set in the field (use for `Flags`) |
| `Path == 3` / `Path != "x"` | the field equals / differs from a number, string or boolean |
| `len(Path) == 0` | the array length compares to a number (`==`, `!=`, `>`, `<`) |

An expression that does not parse counts as true. A broken rule fails loud, not silent.

### Formatters

| Name | Output |
|---|---|
| `raw` | The value as text, or JSON for objects. |
| `int` | An integer as text. |
| `account` | A known name from `ctx.names`, with the shortened address. The full address is kept for hover. Unknown accounts show the short form. |
| `accounts` | A list of accounts, comma-separated. |
| `amount` | Drops as `N XRP`, an IOU as `value CODE (issuer …)`, an MPT as `value MPT <id>`. Hex currency codes decode to text when printable. |
| `drops` | Drops as `N XRP`, with up to 6 decimals and no float rounding. |
| `hash` | A shortened hash with the full value on hover. |
| `hex_text` | Hex decoded as UTF-8 when every character is printable, else shortened hex. |
| `ripple_time` | Ripple-epoch seconds as an ISO date plus "in 2 minutes" or "3 hours ago". |
| `duration` | Seconds as "1 day", "2 hours", and so on. |
| `flags` | The flag word as `0x…` hex. |
| `memos` | One line per memo. Recognises the x402 invoice memo and the facilitator memo (section 3). |
| `inner_transactions` | One line per inner transaction of a `Batch`, then that transaction's own card lines, prefixed `#n`. Recursive. |
| `batch_mode` | The `Batch` mode flag as a sentence: all or nothing, only one, until failure, independent. No mode flag shows `danger`. |
| `permissions` | The `DelegateSet` permission list by name. An empty list shows "none: revokes every permission" with `warn`. |
| `signers` | Who has signed so far, from `BatchSigners` or `Signers`. Empty shows "nobody yet". |
| `count` | The length of an array (`Batch` titles). |
| `asf_flag` | An `AccountSet` `SetFlag`/`ClearFlag` by name. "Disable master key", "no freeze" and "allow clawback" (the last two are permanent) show `danger`. An unknown flag shows `warn`. |
| `signer_entries` | `SignerListSet` entries as `account (weight n)`. |

Lending-era formatters live in `preview/src/formats-lending.ts`. Units were checked against the xrpl.js 5.3 validators.

| Name | Output |
|---|---|
| `tenth_bps` | A rate in tenths of a basis point as a percent: `500` → `0.5%`. The xrpl.js maximum is `100000` = 100%. |
| `vault_amount` | An STNumber in the vault asset's units, with the XRP reading when the vault holds XRP: `60000000 (60 XRP if the vault holds XRP)`. |
| `asset` | A vault asset: `XRP`, `CODE issued by …` or `MPT <id>`. |
| `loan_signed_by` | Who has signed a `LoanSet`: the submitter (`TxnSignature`) and the counterparty (`CounterpartySignature`). If either is missing, the row shows `warn`. |
| `seconds` | Payment intervals and grace periods as a duration. |
| `accepted_credentials` | `PermissionedDomainSet` members as `"type" from issuer`. |

### Coverage today

There are 19 descriptors, with tests in `preview/test/`. Real fixtures are validated `tx_json` re-read from the ledger, with the hash in the file name and in `_source`. Synthetic fixtures carry `"_synthetic": true`, and their test names say so.

| Type | Fixture | Card highlights |
|---|---|---|
| `Payment` | real testnet: x402 payment `D49DBB58…`, facilitator memo `3A9A18D0…`, delegated payment `203F666C…`; synthetic: IOU, MPT, partial payment | The x402 invoice memo is matched to `InvoiceID`, the facilitator memo is decoded, and "Signed by delegate" is shown. A partial payment shows `warn`. |
| `DelegateSet` | real testnet: grant `ED86FFF4…`, revoke `1F171333…` | A grant reads "Let agent … sign **Payment** for treasury …". A revoke reads "Revoke every permission delegated to …". Compare the Stax, which shows "Unknown [1]: 1". |
| `CredentialCreate` / `Accept` / `Delete` | real testnet `01F93247…`, `F6993225…`, `74793D7E…` | `CredentialType` is decoded to `x402-merchant`. "No expiry" shows `info`. A delete shows `warn`. |
| `LoanSet` | real devnet co-signed `90B14608…`; synthetic: counterparty not signed | Principal, payments, interval, rates and who has signed. A missing `CounterpartySignature` shows `warn`. |
| `LoanManage` | real devnet default `A8DCC893…`; synthetic: impair | A default shows `danger` and the title "Default loan …: seize the cover". An impair shows `warn`. |
| `LoanBrokerSet`, `VaultCreate`, `VaultDeposit` | real devnet `1C47B8F1…`, `47CD2A93…`, `5F4D7662…` | Fees and cover rates as percents. A debt limit of 0 reads as "no limit". |
| `Batch` | real devnet AllOrNothing `35DF4112…`, `2DCCD2D2…`; synthetic: multi-account, no mode | The mode is shown in words and each inner transaction gets its own card (`#n`). A dangerous inner transaction surfaces on its `#n` summary row. |
| `LoanPay`, `VaultWithdraw`, `PermissionedDomainSet`, `AccountSet`, `SignerListSet`, `EscrowCreate` / `Finish` / `Cancel` | synthetic | `AccountSet` and `SignerListSet` always carry a `danger` row: they change who controls the account. |

### Unknown types

A type with no descriptor does not fail quietly. `describe()` returns the title "Unrecognised transaction type" and a `danger` row: "No descriptor for this type: the wallet cannot say what it does. Read the raw fields before signing."

### Worked example: `Payment.json`

```json
{
  "type": "Payment",
  "title": "Pay {Amount|amount} to {Destination|account}",
  "summary": "Send {Amount|amount} from {Account|account} to {Destination|account}",
  "fields": [
    { "path": "Account", "label": "From", "format": "account" },
    { "path": "Destination", "label": "To", "format": "account", "required": true },
    { "path": "Amount", "label": "Amount", "format": "amount", "required": true },
    { "path": "SendMax", "label": "Spend at most", "format": "amount" },
    { "path": "DeliverMin", "label": "Deliver at least", "format": "amount" },
    { "path": "Delegate", "label": "Signed by delegate", "format": "account" },
    { "path": "DestinationTag", "label": "Destination tag", "format": "int" },
    { "path": "SourceTag", "label": "Source tag", "format": "int" },
    { "path": "InvoiceID", "label": "Invoice ID", "format": "hash" },
    { "path": "Memos", "label": "Memos", "format": "memos" },
    { "path": "Fee", "label": "Network fee", "format": "drops" },
    { "path": "LastLedgerSequence", "label": "Valid until ledger", "format": "int" }
  ],
  "risk": [
    { "when": "Paths", "level": "warn", "text": "Uses payment paths: the delivered currency may differ from what you send." },
    { "when": "Flags & 0x00020000", "level": "warn", "text": "Partial payment: the recipient may receive less than Amount." }
  ]
}
```

Input: an x402 payment from the treasury to the good merchant. The first memo is the invoice text. `InvoiceID` is `sha256` of that text. The second memo is the facilitator memo.

```json
{
  "TransactionType": "Payment",
  "Account": "rUGeRsKjpnDVAi1uJYhAxWXbETC917VQ6B",
  "Destination": "rwKL4Bir4ED8jbMheyMGMnTWyeUcL3VpCa",
  "Amount": "2000000",
  "Fee": "12",
  "LastLedgerSequence": 4242424,
  "InvoiceID": "2F9C865DD0D5D5B36C1F40DCD89BF1C988AED5CC294AA691F4CDC207DE4E0A86",
  "Memos": [
    { "Memo": { "MemoData": "<hex of: x402 invoice inv_7f3a: 2 XRP for GET /api/quote>" } },
    { "Memo": { "MemoType": "<hex of: urn:x402:facilitator>", "MemoData": "<hex of: t54>" } }
  ]
}
```

The card from `describe(tx, { names })`, run on this input:

```
Pay 2 XRP to good merchant (rwKL4B…VpCa)

From               treasury (rUGeRs…VQ6B)
To                 good merchant (rwKL4B…VpCa)
Amount             2 XRP
Invoice ID         2F9C865D…4E0A86
x402 invoice       x402 invoice inv_7f3a: 2 XRP for GET /api/quote (matches InvoiceID)
x402 facilitator   t54
Network fee        0.000012 XRP
Valid until ledger 4242424

summary: Send 2 XRP from treasury (rUGeRs…VQ6B) to good merchant (rwKL4B…VpCa)
```

No risk row appears because neither `Paths` nor the partial-payment flag is set. Set `Flags: 0x00020000` and the card gains `Risk: Partial payment: the recipient may receive less than Amount.` (warn), and the summary ends with `(warn: …)`.

## 3. What came from ERC-7730, and what XRPL needs that it lacks

ERC-7730 is "a JSON descriptor that tells wallets how to display smart contract calldata and EIP-712 messages in human-readable form" ([EIP-7730](https://eips.ethereum.org/EIPS/eip-7730)). Section names below are the EIP's.

### Borrowed

| ERC-7730 | Here |
|---|---|
| Field paths ("Common concepts"): a limited JSON Path with dot notation, relative to the structured data | `fields[].path` and `{Path}` placeholders. We keep dot paths only. We drop the `#`, `$`, `@` roots and slices, because `tx_json` is flat JSON with no calldata to slice. |
| Field formats ("Field formats"): `raw`, `amount`, `date`, `duration`, `enum`, `addressName`, `unit` | `raw`, `amount`/`drops`, `ripple_time`, `duration`, `batch_mode` (an enum over `Flags`), `account` (names from `ctx.names`, as `addressName` takes names from local sources). The set is XRPL-shaped: drops, IOUs, MPTs, ripple epoch. |
| `intent` and `interpolatedIntent` ("Display section") | `title` and `summary`, with `{Path\|format}` placeholders. Same idea as `{path}` inside `interpolatedIntent`, plus a per-placeholder format. |
| Interpolation falls back when it fails ("Interpolated intent security") | A missing path renders as `?`, never as an empty string. |
| Formatting inside a sentence must match the formatting of the standalone field ("Interpolated intent security") | Title, summary and rows call the same formatter code. |
| One descriptor per signable thing, found by a key (selector for contracts, `encodeType` for EIP-712) | One descriptor per `TransactionType`. |
| Wallet-side curation is out of scope ("Context and Binding") | We also leave the registry open (section 4). |
| Flat field lists for small hardware screens ("Wallet limitations") | `describe()` returns flat `lines[]`. Nesting (Batch) is flattened with `#n` prefixes. |

### XRPL needs that ERC-7730 lacks

ERC-7730 has no `risk` rule, and its `context` binding has no XRPL analogue (no contract address, selector or domain). The table lists what we had to add. Note: the EIP text read for this document covers the specification, rationale and the first four security subsections. We did not find an equivalent for the rows below in it.

| XRPL need | Why ERC-7730 does not cover it | What the format does |
|---|---|---|
| **Memos** | Calldata has no free-text, attacker-writable side channel. XRPL puts payment context in `Memos`. | `memos` formatter: hex to UTF-8 when printable, one labeled line per memo. **x402 invoice memo:** the memo has no `MemoType`, and `sha256(text)` must equal `InvoiceID`. A match shows `x402 invoice … (matches InvoiceID)`. **Facilitator memo:** `MemoType` `urn:x402:facilitator` shows as `x402 facilitator`. Memo text stays on its own line and out of `title` and `summary` (the EIP warns about injected text in `interpolatedIntent`). |
| **Counterparty and multi-signature state** | One signature, one signer. XRPL transactions can need several parties. | `LoanSet` shows the counterparty and who has signed (`CounterpartySignature`). `signers` formatter reads `BatchSigners` and `Signers`. |
| **Batch nesting** | The EIP calls recursive constructs like `calldata` something hardware wallets may restrict at first, and joins EIP-5792 batches with " and " in an intent. | `inner_transactions` calls `describe()` on each inner transaction and indents its lines with `#n`. `batch_mode` states atomicity in a sentence. Each `#n` line carries the worst risk of its inner card. |
| **Account-control risk** | Calldata descriptors say what a call does, not whether it hands over the account. | `risk` rules. `AccountSet` and `SignerListSet` carry `danger` because they change who controls the account. |
| **Delegated signing** | The signer and the payer are the same address. With `Delegate`, `Account` pays and the delegate signs. | `Payment.json` shows `From` (the payer) and `Signed by delegate`. `DelegateSet` uses the `permissions` formatter, so "Payment" is named. An empty list says "revokes every permission". |
| **Unknown types** | An unbound contract call is simply not clear-signed. | An unknown `TransactionType` produces a `danger` card. Silence is never the fallback. |

## 4. How a device app or wallet would consume it

1. Load the descriptors into a registry keyed by `TransactionType`.
2. Take the transaction. In the wallet this is the `tx_json` it just built.
3. `describe(tx, ctx)` returns `{ title, lines[], summary }`. Each line has `label`, `value`, optional `risk` (`info`, `warn`, `danger`) and optional `full` (untruncated value for hover).
4. Show the card. Highest `risk` drives a badge (`worstRisk()`).
5. If the type has no descriptor, show the `danger` card. Do not offer a quiet sign button.

`describe()` in `preview/` is the reference implementation. It has no runtime dependencies. It uses string and number operations only, and its own sha256. `xrpl` is a dev dependency for tests.

**Where trust comes from.** ERC-7730 binds a descriptor to deployments the wallet can verify. XRPL has no deployments. The key is the transaction type, which is part of the signed bytes. A registry, signing of descriptors, and provenance are open. The EIP lists registry poisoning as a risk for any registry ("Registry poisoning"). The same applies here.

**Limits, stated plainly:**

- The card is rendered **off-device**, in the dashboard. The device does not show it.
- The device still blind-signs these types. A user who approves in the dashboard and then holds to sign on the Stax sees the blind-signing warning (section 1).
- The card is computed from the `tx_json` the wallet built. The device shows what it parses from the serialized blob. The two are not cryptographically tied here. A device app that parses the blob itself removes that gap.
- The descriptor is a **proposal for the device app**. We did not change the XRP app. A device-side version would need the descriptors compiled to a compact form, and screens sized for the Stax and Flex.
- A non-matching text memo is shown as a plain memo. It is not flagged as a mismatch.
- Scope: Ledger's docs describe Clear Signing as defined by ERC-7730, "an open Ethereum standard" ([Ledger developer docs](https://developers.ledger.com/docs/clear-signing/reference/external-resources)). Third-party wallets need an agreement with Ledger for Clear Signing ([Ledger Clear Signing overview](https://developers.ledger.com/docs/clear-signing/overview)). This work is an XRPL extension of the idea, not part of that registry.

## 5. Where it runs in Policy Wallet

| Surface | What shows |
|---|---|
| Dashboard Pending panel | The preview card above Approve and Deny. |
| Permissions and Vetted merchants panels | A preview built client-side from the exact transaction the click will send. Same `describe()`. |
| Wallet hold log | The `summary` line. |
| Audit rows (contract v1.5) | `preview: {title, lines[], summary}` stored on the row. `GET /v1/requests` and `GET /v1/requests/:id` return it. Rows without it stay valid. |

See `docs/CONTRACT.md`, "v1.5 delta".

## Sources

- ERC-7730: Structured Data Clear Signing Format (Draft), https://eips.ethereum.org/EIPS/eip-7730
- Ledger developer docs, Clear Signing overview, https://developers.ledger.com/docs/clear-signing/overview
- Ledger developer docs, external resources, https://developers.ledger.com/docs/clear-signing/reference/external-resources
- `docs/LEDGER_DX_FEEDBACK.md`, finding 11
- `preview/src/{types,engine,formats}.ts`; `preview/format/Payment.json`
