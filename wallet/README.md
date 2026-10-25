# wallet/: the Policy Wallet

A Node service that holds the signing keys so the agent does not have to. The agent calls `POST /v1/pay` with the x402 payment requirements; the wallet runs six policy checks, then signs on the hot key, holds for approval in the Speculos emulator, or refuses. XRPL testnet only.

The API, the policy file and the decision order are specified in [docs/CONTRACT.md](../docs/CONTRACT.md). The checks run in `src/policy.ts` in this order: expiry, network, asset, merchant access (static allowlist or an accepted Credential), daily budget, per-payment cap. Above the cap the request is held, not refused.

## Prerequisites

- Node 22.
- The Speculos emulator (Ledger Stax, XRP app) on `http://127.0.0.1:5000` for held payments; [docs/RUNBOOK.md](../docs/RUNBOOK.md) has the Docker command. Auto and refused decisions work without it.
- Testnet faucet access on first setup.

## Setup

```sh
cd wallet
npm install
cp .env.example .env
# WALLET_ADMIN_TOKEN gates the operator routes; generate one:
echo "WALLET_ADMIN_TOKEN=$(openssl rand -hex 32)" >> .env
npm run setup        # creates the hot key, funds it from the testnet faucet, writes HOT_WALLET_SEED to .env
```

`.env` is gitignored. It holds the hot seed, the port (7402), the Speculos URL and the testnet WebSocket URL.

## Run

```sh
npm run up           # wallet :7402, both demo merchants :8001/:8002, dashboard :5174 (bin/up.sh)
npm run down
npm start            # the wallet alone
curl -s 127.0.0.1:7402/health
curl -s 127.0.0.1:7402/v1/status
```

The first `npm run up` fails on the allowlist check until the good merchant has been vetted once: run `agent/scripts/vet_merchant.py` (see [agent/README.md](../agent/README.md)), then `npm run up` again.

## Operator routes

`PUT /v1/policy`, `POST`/`DELETE /v1/merchants`, `POST /v1/domain` and `POST /v1/delegate` require the header `X-Wallet-Token` equal to `WALLET_ADMIN_TOKEN`. With the token unset they answer `503 operator_token_unset`. The dashboard sends the token from `dashboard/.env.local` as `VITE_WALLET_TOKEN`.

## Test

```sh
npm test             # offline unit tests; test keys derive from fixed test entropy, no seed is read
npm run typecheck
npm run smoke        # against a running wallet
npm run test:live    # live tests, need the wallet, the merchants and Speculos
```

## Layout

- `src/policy.ts`: the six checks and the policy file hash.
- `src/server.ts`: the HTTP API.
- `src/speculos.ts`: Speculos REST driver for the scripted demo taps.
- `scripts/setup.ts`, `scripts/smoke.ts`: setup and smoke test.
- `bin/up.sh`, `bin/down.sh`: start and stop the demo processes.
- `policy.json`: the operator's policy; `data/` (gitignored) holds the audit log `requests.jsonl`.
