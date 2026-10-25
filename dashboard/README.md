# dashboard/: the wallet UI

A React (Vite) front end for the Policy Wallet: the pay feed with each request's decision, the held request waiting for emulator approval, merchant vetting, the Delegate grant and revoke, and the policy editor. It reads the wallet API on `http://localhost:7402` and polls once a second.

## Run

```sh
cd dashboard
npm install
cp .env.example .env.local
# VITE_WALLET_TOKEN must equal WALLET_ADMIN_TOKEN in wallet/.env; operator actions fail without it
npm run dev          # http://localhost:5174
```

`wallet/bin/up.sh` starts the dashboard together with the wallet.

## Test and build

```sh
npm test             # vitest
npm run typecheck
npm run build
```

What each panel calls is listed in [docs/CONTRACT.md](../docs/CONTRACT.md) under Dashboard; the client is `src/api.ts`.
