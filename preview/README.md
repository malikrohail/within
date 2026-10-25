# preview/: signing previews for XRPL transactions

A data package and a small TypeScript engine. One JSON descriptor per transaction type turns a `tx_json` object into a titled, line-by-line preview with risk flags, so a wallet, a dashboard or a device app can show what a transaction does before it is signed. It is used by the Within dashboard and is the worked basis of [Application previews for XRPL](../docs/CLEAR_SIGNING_XRPL.md).

Coverage: 19 transaction types in `format/`, 13 of them amendment-era.

| Group | Types |
|---|---|
| Core | `Payment`, `AccountSet`, `SignerListSet`, `EscrowCreate`, `EscrowFinish`, `EscrowCancel` |
| Credentials (XLS-70) and Permissioned Domains (XLS-80) | `CredentialCreate`, `CredentialAccept`, `CredentialDelete`, `PermissionedDomainSet` |
| Permission Delegation (XLS-75) | `DelegateSet` |
| Batch (XLS-56) | `Batch` |
| Single Asset Vault (XLS-65) | `VaultCreate`, `VaultDeposit`, `VaultWithdraw` |
| Lending Protocol (XLS-66) | `LoanBrokerSet`, `LoanSet`, `LoanPay`, `LoanManage` |

## Install and test

Node 22. No network access is needed.

```sh
cd preview
npm ci
npm test          # vitest: core and lending fixtures
npm run typecheck
```

## Use

```ts
import describe from "./src/index.js";   // or: import { describe } from "./src/index.js"

const preview = describe(txJson, {
  names: { rTreasury: "treasury", rAgent: "agent" },   // optional address labels
  network: "testnet",                                   // optional
  now: Date.now(),                                      // optional clock for relative times
});

preview.title;    // "Loan of XRP 30 between borrower and broker"
preview.summary;  // one sentence
preview.lines;    // [{ label, value, risk?, full? }, ...]
```

`describe(tx, ctx)` returns `{ title, lines, summary }`. Each line has a `label`, a `value`, an optional `risk` of `info`, `warn` or `danger`, and an optional `full` untruncated value. `worstRisk(preview)` returns the highest risk on the card or `null`. An unknown `TransactionType` does not throw: the engine falls back to a generic preview (`unknownType` in `src/engine.ts`).

Other exports: `descriptorFor(type)`, `template(text, tx, ctx)`, `when(expr, tx)`, `dropsToXrp`, `hexText`, and the types `Ctx`, `Descriptor`, `Line`, `Preview`, `Risk`, `Tx`.

## Descriptor format

One file per type, `format/<TransactionType>.json`:

```json
{
  "type": "LoanSet",
  "title": "Loan of {PrincipalRequested|vault_amount} between {Account|account} and {Counterparty|account}",
  "summary": "Loan of {PrincipalRequested|vault_amount}: {PaymentTotal} payments every {PaymentInterval|seconds} at {InterestRate|tenth_bps} interest",
  "variants": [{ "when": "Flags & 0x00010000", "title": "..." }],
  "fields": [
    { "path": "PrincipalRequested", "label": "Principal", "format": "vault_amount", "required": true },
    { "path": "PaymentInterval", "label": "Every", "format": "seconds" }
  ],
  "risk": [
    { "when": "!CounterpartySignature", "level": "warn", "text": "The counterparty has not co-signed yet: the ledger rejects the loan until both parties sign." }
  ]
}
```

- `title` and `summary` are templates. A placeholder is `{Path}` or `{Path|format}`; `Path` is a dot path into `tx_json`, for example `Amount.value`.
- `variants`: the first entry whose `when` holds replaces the title and summary (grant versus revoke, default versus impair).
- `fields`: rendered in order. A missing field is skipped unless `required` is set, which renders `missing`. `format` names a formatter; without one the raw value is shown.
- `risk`: rules evaluated against the transaction. The `when` grammar is `Path`, `!Path`, `Path & 0x10000`, `Path == 3`, `Path != "x"`, `len(Path) == 0`.

Formatters live in `src/formats.ts` (`raw`, `count`, `int`, `account`, `accounts`, `amount`, `drops`, `hash`, `hex_text`, `ripple_time`, `duration`, `flags`, `asf_flag`, `signer_entries`, `signers`, `permissions`, `batch_mode`, `inner_transactions`) and `src/formats-lending.ts` (`vault_amount`, `asset`, `seconds`, `tenth_bps` for XLS-66 rates, `loan_signed_by` for the signature state of a `LoanSet`, `accepted_credentials`). `account` labels addresses through `ctx.names`; `inner_transactions` previews a Batch's inner transactions by calling `describe` recursively.

## Add a type

1. Write `format/<Type>.json` with the fields in the order a reviewer should read them.
2. Import it in `src/descriptors-core.ts` or `src/descriptors-lending.ts`; `src/descriptors.ts` concatenates the two lists.
3. Add a fixture under `test/fixtures/` (`testnet/`, `devnet/` or `synthetic/`) and a test in `test/core.test.ts` or `test/lending.test.ts`.
4. `npm test`.

## How a device app would consume it

The descriptors are data, not code. A device app or wallet that already parses `tx_json` can map each descriptor field to a review screen: label, formatted value, and a risk badge. Section 4 of [Application previews for XRPL](../docs/CLEAR_SIGNING_XRPL.md) describes that path and what XRPL needs that ERC-7730 does not provide. Within's own Ledger patch ([experiment 005](../ons/experiments/005-app-xrp-patch/README.md)) implements the field labels for the lending types inside the XRP app itself; the previews are the wallet-side counterpart.
