# Policy Wallet — API and behavior contract (v1, frozen)

The API and behavior every component builds against. Later changes are recorded as dated deltas at the end.

## Topology

| Process | Folder | Port | Notes |
|---|---|---|---|
| Wallet API (policy + hot key + Ledger signer) | `wallet/` | 7402 | |
| Merchants: good merchant server | `agent/` | 8001 | |
| Rogue merchant (not on allowlist) | `agent/` | 8002 | |
| Demo agent (Python) | `agent/` | — | |
| Dashboard | `dashboard/` | 5174 | |
| Speculos (Ledger Stax emulator, XRP app) | Docker | 5000 | started before the wallet |

Network: **XRPL testnet only** (`xrpl:1`). JSON-RPC `https://s.altnet.rippletest.net:51234/`, WSS `wss://s.altnet.rippletest.net:51233`. Facilitator: `https://xrpl-facilitator-testnet.t54.ai`. Never mainnet.

## Accounts

- **Hot account**: seed in `wallet/.env` as `HOT_WALLET_SEED`. Created and funded from the testnet faucet by `wallet/scripts/setup.ts` on first run. Signs `auto` decisions.
- **Device account**: derived on the Ledger (Speculos) at path `44'/144'/0'/0/0`. Address is `rUGeRsKjpnDVAi1uJYhAxWXbETC917VQ6B` with the current Speculos seed (already funded, ~98 XRP). Signs `approved` decisions. Read it live from the device at startup, do not hardcode.
- Merchant accounts: created by `agent/` from the faucet, addresses written to `agent/merchants.json` (committed; seeds only in `agent/.env`).

## Policy file: `wallet/policy.json`

```json
{
  "perTxCapDrops": "100000",
  "dailyBudgetDrops": "100000000",
  "allowedMerchants": [],
  "allowedNetworks": ["xrpl:1"],
  "allowedAssets": ["XRP"],
  "holdTimeoutSeconds": 90
}
```

Decision order, evaluated in code before any signing:
0. (v1.6) optional `expiresAt` (ISO 8601 with offset) has passed → **refuse** `policy_expired`; every audit row also records `policyHash`, the sha256 of policy.json at decision time
1. `network` not in `allowedNetworks` → **refuse** `network_not_allowed`
2. `asset` not in `allowedAssets` → **refuse** `asset_not_allowed`
3. `payTo` not in `allowedMerchants` → **refuse** `merchant_not_allowed`
4. `amount` + spent-today > `dailyBudgetDrops` → **refuse** `daily_budget_exceeded`
5. `amount` > `perTxCapDrops` → **hold** (device path)
6. else → **auto** (hot key)

"spent-today" = sum of `amountDrops` of requests with status `auto` or `approved` since 00:00 local time, from the audit log.

## Wallet HTTP API (port 7402, JSON, CORS allow `http://localhost:5174` and `http://localhost:5173`)

### `POST /v1/pay`
The x402 payer's signing hook. **Synchronous**: for a held request the call blocks until the device approves, denies, or `holdTimeoutSeconds` passes.

Request:
```json
{
  "requirements": {
    "scheme": "exact", "network": "xrpl:1", "amount": "1000", "asset": "XRP",
    "payTo": "rMerchant...", "maxTimeoutSeconds": 600,
    "extra": { "invoiceId": "4CDF07BC...", "sourceTag": 20260601 }
  },
  "purpose": "lookup comps for 123 Main St",
  "resource": { "url": "http://localhost:8001/lookup", "description": "..." }
}
```
`requirements` is the selected x402 v2 `PaymentRequirements` exactly as the 402 sent it (`extra` may also carry `destinationTag`, `facilitator`, `issuer`; `facilitator` is `{id, name?}` or absent).

Responses:
- `200` `{"decision":"auto","requestId":"...","signer":"hot","account":"r...","signedTxBlob":"<hex>","txHash":"<hex>"}`
- `200` `{"decision":"approved","requestId":"...","signer":"device","account":"r...","signedTxBlob":"<hex>","txHash":"<hex>"}`
- `403` `{"decision":"refused","requestId":"...","reason":"merchant_not_allowed|daily_budget_exceeded|network_not_allowed|asset_not_allowed|denied_on_device"}`
- `408` `{"decision":"expired","requestId":"...","reason":"hold_timeout"}`
- `400` on malformed body, `503` `{"reason":"device_unavailable"}` if a hold is needed and the device is not connected.

`txHash` = hash of the signed blob (not submitted by the wallet; the merchant/facilitator settles it).

### Building the Payment (must mirror `x402_xrpl.client.presigned_payment_payer.prepare_payment`)
Given `req` and `inv = req.extra.invoiceId` (required, else 400):
- `TransactionType: "Payment"`, `Account: <hot or device address>`, `Destination: req.payTo`
- `Amount: String(parseInt(req.amount))` (XRP only; refuse other assets per policy)
- `InvoiceID: sha256(utf8(inv)).hex().toUpperCase()`
- `Memos: [{Memo:{MemoData: utf8ToHexUpper(inv)}}]`
- If `req.extra.facilitator` has a non-empty `id`: append `{Memo:{MemoType: hexUpper("urn:x402:facilitator"), MemoData: hexUpper(JSON.stringify({id, name?, sourceTag?})), MemoFormat: hexUpper("application/json")}}` — key order `id, name, sourceTag`, no spaces. (Literal verified against `FACILITATOR_MEMO_TYPE` in the Python package, line 27.) Normalization mirrors Python `_facilitator_from_payment_req`: `id` trimmed and capped at 64 chars, `name` trimmed and capped at 128 and omitted when empty, and the memo is emitted only when the trimmed `id` is non-empty. (Added v1.2 from a reading of the Python source; the wallet has byte-for-byte parity tests against it.)
- `SourceTag: int(req.extra.sourceTag)` if present; `DestinationTag` likewise.
- `LastLedgerSequence: <latest validated ledger> + ceil(req.maxTimeoutSeconds / 5) + 2`
- `Fee`, `Sequence`: autofill via xrpl.js `client.autofill`. Reject if `Fee > 10000` drops.
- Check `server_info.info.network_id === 1` for `xrpl:1`, else 400 `rpc_network_mismatch`.
- Hot path: `wallet.sign(tx)` → `tx_blob`, `hash`.
- Device path: set `SigningPubKey` to the device public key (uppercase hex), `encode(tx)` (NOT `encodeForSigning`), `signer.signTransaction("44'/144'/0'/0/0", bytes)` → DER signature → `TxnSignature` = hex upper → `encode(tx)` again = blob; hash via xrpl.js `hashes.hashSignedTx(blob)`.

### `GET /v1/requests?limit=200`
Newest first. Each item:
```json
{"id":"...","ts":"2026-10-24T07:00:00Z","merchant":"r...","amountDrops":"1000","purpose":"...",
 "resourceUrl":"...","status":"auto|held|approved|refused|expired","reason":null,"signer":"hot|device|null","txHash":"...|null"}
```
Persist as JSON lines in `wallet/data/requests.jsonl` (gitignored). Held requests appear immediately with status `held` and update in place when resolved.

### `POST /v1/requests/:id/device-tap`
Demo helper. For a `held` request whose review is on the Speculos screen, drive the emulator REST API at `SPECULOS_URL` (default `http://127.0.0.1:5000`):
1. `POST /finger {"action":"press-and-release","x":350,"y":620}` once per review page until the "Hold to sign" page is showing, 700 ms apart. A Payment with the invoice memo reviews as **5 pages** (measured; a memo-less Payment reviews as 3 pages). Do not hardcode the count: read `GET /screenshot` or `/events` and tap until the sign page appears, with a cap of 8 taps.
2. `POST /finger {"action":"press","x":336,"y":515}`, wait 3000 ms, `POST /finger {"action":"release","x":336,"y":515}` (hold to sign)
Returns `202 {"ok":true}`. (A real device needs no helper.)

### `POST /v1/requests/:id/deny`
For a `held` request: cancel the device action, resolve the pending `/v1/pay` with `403 denied_on_device`. Also tap Reject on Speculos at `(80,625)` and then the confirmation "Yes, reject" (a second tap is required; measure its coordinate from a screenshot), best-effort.

### Exclusive device access
Only one process may hold a DMK session to Speculos. Any other DMK client (for example the workshop app on :5173 open in a browser) polls `getAppAndVersion` and its replies interleave with the wallet's sign APDU (observed: sign returns `6901`, the signature lands on the other client's request). Close any such tab before the wallet runs; `docs/RUNBOOK.md` says so.

### `GET /v1/policy` / `PUT /v1/policy`
Full policy object. PUT validates shape, writes `wallet/policy.json`, takes effect immediately.

### `GET /v1/status`
```json
{"hotAccount":"r...","hotBalanceDrops":"...","deviceAccount":"r...","deviceBalanceDrops":"...",
 "deviceConnected":true,"deviceApp":"XRP 2.8.1","spentTodayDrops":"...","pending":1}
```

### `GET /health` → `{"ok":true}`

## Python side: `agent/remote_signer.py`

```python
def make_wallet_header_factory(wallet_url="http://localhost:7402", purpose_getter=lambda: "agent purchase"):
    def factory(reqs, *, extensions=None, resource=None) -> str:
        # POST reqs.to_dict() + purpose + resource to /v1/pay
        # 200 -> build_payment_header_for_signed_blob(req=reqs, signed_tx_blob=blob, invoice_id=reqs.invoice_id(), extensions=extensions, resource=resource)
        # 403/408/503 -> raise PolicyRefused(reason, request_id)
    return factory
```
Use with `x402_requests(dummy_wallet, rpc_url=..., payment_header_factory=factory)`. The `wallet` argument is required by the library but unused when a factory is set; pass `Wallet.create()`.

## Merchants (`agent/merchants/`)

One FastAPI app on 8001 with three paid paths, one on 8002 (rogue) with one path:

| Port | Path | Price (drops) | Purpose |
|---|---|---|---|
| 8001 | `/lookup` | 1000 | cheap, auto |
| 8001 | `/infer` | 50000 | auto (under 100000 cap) |
| 8001 | `/dataset` | 5000000 | held, needs device |
| 8002 | `/lookup` | 1000 | refused: merchant not on allowlist |

Each uses `x402_xrpl.server.require_payment` as in the x402-xrpl examples (facilitator URL above, `network="xrpl:1"`, `asset="XRP"`, `extra={"sourceTag": <per-path int>}`). Both apps load their pay-to seeds from `agent/.env` (`MERCHANT_SEED`, `ROGUE_SEED`), generate via faucet on first run, and write `agent/merchants.json`:
```json
{"good":{"address":"r...","port":8001},"rogue":{"address":"r...","port":8002}}
```
`agent/scripts/apply_allowlist.py` PUTs `allowedMerchants=[good.address]` into the wallet policy (reads current policy, replaces only that key).

## Demo agent (`agent/demo.py`)

`python demo.py --scripted` runs exactly, in order, printing one line per step with decision and txHash:
1. GET 8001/lookup → expect `auto`
2. GET 8001/infer → expect `auto`
3. GET 8001/lookup → expect `auto`
4. GET 8001/dataset → expect `approved` (blocks until the device tap; the dashboard or `POST /v1/requests/:id/device-tap` provides it)
5. GET 8002/lookup → expect `refused` (caught `PolicyRefused`, printed, continue)
Exit 0 only if all five matched. `--llm` mode (only when `ANTHROPIC_API_KEY` is set) runs a Claude agent with four tools (`lookup`, `infer`, `dataset`, `rogue_lookup`) and a prompt that asks it to use all four; same session underneath. Model id `claude-sonnet-5-5`.

## Dashboard (`dashboard/`)

Vite + React + TypeScript + Tailwind, dev server on **5174** (5173 is taken by the Ledger workshop app). Polls the wallet every 1 s. Three panels on one page:
1. **Status bar**: hot/device accounts and balances (XRP, 6 dp), device connected, spent today, pending count.
2. **Pending approvals**: each `held` request with merchant, amount, purpose, and two buttons: "Approve on device" → `POST /v1/requests/:id/device-tap`, "Deny" → `POST /v1/requests/:id/deny`.
3. **Live feed**: table of requests, newest first, status pill colored green (`auto`/`approved`), amber (`held`), red (`refused`/`expired`), with the word in the pill, txHash linking to `https://testnet.xrpl.org/transactions/<hash>`.
4. **Policy editor**: form for the six policy fields, Save → `PUT /v1/policy`.


## v1.4 delta (2026-10-24 08:40Z) — on-ledger allowlist
Summary: `policy.json` gains `credentialIssuer` (default hot account) and `credentialType` (default `x402-merchant`); rule 3 passes if `allowedMerchants` contains payTo OR an accepted, unexpired Credential (issuer, type) exists for payTo on the ledger (30 s cache); refusal reason `merchant_not_credentialed`; new routes `POST /v1/merchants`, `DELETE /v1/merchants/:address`, `GET /v1/merchants`; merchants auto-accept at startup; `scripts/apply_allowlist.py` is replaced by `scripts/vet_merchant.py`. Payment blob unchanged.

## v1.5 delta (2026-10-24 09:40 ET) — Preview
- The wallet computes `preview = describe(tx)` from `preview/` when it builds any transaction it will sign or hold, and stores `preview: {title, lines[], summary}` on the audit row. `GET /v1/requests` returns it; `GET /v1/requests/:id` too. The hold log prints `summary`.
- Dashboard: the Pending panel shows the preview card above Approve/Deny; the Vetted merchants and Agent permissions panels build their previews client-side from the exact transaction they will send (same `describe`).
- `preview/` has no runtime dependencies (string and number operations only); `xrpl` is a dev dependency for tests. Field formats and risk rules are data (`preview/format/*.json`).
- Additive: no existing response field changes; rows without a preview are still valid.

## v1.7 delta (2026-10-24 17:06 ET): operator token and loan-terms memo
- **Operator token.** `PUT /v1/policy`, `POST /v1/merchants`, `DELETE /v1/merchants/:address`, `POST /v1/domain` and `POST /v1/delegate` require header `X-Wallet-Token` equal to `WALLET_ADMIN_TOKEN` in `wallet/.env`.
  - `WALLET_ADMIN_TOKEN` unset → `503 {"reason":"operator_token_unset"}`.
  - Missing or wrong header → `401 {"reason":"bad_operator_token"}`.
  - Unchanged: every GET, `/v1/pay`, `/v1/lend/approve`, `/v1/requests/:id/device-tap` and `/deny`.
  - The dashboard sends `VITE_WALLET_TOKEN` (`dashboard/.env.local`, gitignored). `agent/demo.py --revoke-drill` and `agent/scripts/vet_merchant.py` read `WALLET_ADMIN_TOKEN` from the env or `wallet/.env`.
- **Loan-terms memo on `POST /v1/lend/approve`.** When `loanSetBlob` is sent, the approval Payment carries two Memos, in this order:
  1. `MemoType` = hex(`loan-approval`), `MemoData` = loanSetHash (unchanged).
  2. `MemoType` = hex(`loan-terms`), `MemoData` = hex(ASCII text). The text is built from the decoded LoanSet only:
     ```
     approve loan <P> XRP to <Account> <PaymentTotal> payments
     ```
     - `<P>` is `PrincipalRequested` in drops ÷ 1,000,000, as a plain decimal: no exponent, no trailing zeros, no trailing point. 60000000 → `60`; 1500000 → `1.5`.
       - `PrincipalRequested` is an STNumber, and its decoded JSON switches to exponent form from 1e11 drops: `"1e11"`, `"15e10"`, `"123456789012e0"`. Parse the mantissa and exponent exactly; do not parse it as an integer string.
       - A principal that is not a whole number of drops, or a LoanSet without `PaymentTotal`, has no terms text. The wallet answers `400 {"reason":"bad_loan_terms"}` and holds nothing.
     - `<Account>` is the LoanSet's `Account`, the borrower who signs first in the desk's flow. It is not `Counterparty`, which is the broker.
     - `<PaymentTotal>` is the integer as is.
     - Example (fixture LoanSet-135D0B68): `approve loan 60 XRP to rBU5c38YumSZQAkxtPNwbgq6W6TzLM6Wbe 3 payments`.
  - The desk should rebuild this text from the blob it holds and compare it byte for byte. The XRP app shows an all-ASCII MemoData as text on the review screen.
  - Without `loanSetBlob`, there is only the first Memo, as before.
