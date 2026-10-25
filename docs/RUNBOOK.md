# Runbook

## Two-minute walkthrough

The rows below come from the local audit log in `wallet/data/`, which a fresh clone does not have: complete one-time setup and one `demo.py --scripted` run first (see Demo).

1. **`wallet/bin/up.sh`** prints green lines, in this order:
   - `✓ speculos`;
   - an amber `! workshop` note when :5173 is running;
   - `✓ wallet`, `✓ good`, `✓ rogue`, `✓ dashboard`;
   - `✓ device` with both balances, `connected XRP 2.8.1`, spent today and `pending 0`;
   - `✓ allowlist 1 accepted credential(s) · domain 31BF6256…`.
2. **Open http://localhost:5174.**
   - The header shows the hot and device accounts with balances, **Device ● connected XRP 2.8.1**, **Spent today … of 100 XRP budget** (0 on a fresh day; it resets at local midnight, see Demo below) and **Pending 0**.
   - The **Treasury** tab is open. On the left, *testnet: agent payments*: treasury (Ledger), agent (hot key), good merchant, rogue merchant. On the right, *devnet: lending desk*: broker, depositors, borrower, customers, vaults.
   - Edges are coloured by how the payment was authorised: teal auto, amber approved on Ledger, red dashed refused, blue loan, violet vault deposit. The ticker on the right lists each flow with an explorer link; a refusal reads "never reached the ledger".
3. **Click the amber edge** from treasury (Ledger) to good merchant. The explorer opens that edge's latest Ledger-approved Payment, which was signed by the device account. Click any node to open its account page.
4. **Pay tab.** The live feed lists, newest first:
   - `REFUSED` "Merchant not vetted on-ledger" (the rogue merchant, no tx);
   - `APPROVED` 5 XRP, signer `device`;
   - `AUTO` rows, signer `hot`.

   Click **details** on the APPROVED row. The preview card reads "Pay 5 XRP to rwKL4B…VpCa", From "treasury (Ledger)", and "x402 invoice … (matches InvoiceID)". This is the same card that sits above **Approve on device** while a payment is held (`docs/assets/preview-payment.png`).
5. **Vet tab.**
   - The header reads **Domain 31BF6256… · membership = x402-merchant credential**. Click the id to open the PermissionedDomainSet.
   - The merchant `rwKL4B…VpCa` shows **ACCEPTED** with its credential tx.
   - Type any r-address in the box and a CredentialCreate preview appears. Do not press Vet.
6. **Permissions tab.**
   - The **PAYMENT** pill shows that the agent holds the treasury's delegated Payment permission.
   - Click **▸ What Re-grant sends**. The card reads "Let agent (hot key) (rUPNkA…rm7m) sign Payment for treasury (Ledger) (rUGeRs…VQ6B)", with an amber risk line and "The Ledger shows this as 'Transaction Type: Unknown'; this card is what it actually does."
   - Compare it with the device screen in `docs/assets/stax-delegateset-unknown.png`.
   - Do not press Revoke or Re-grant: each one is a device-signed DelegateSet.
7. **Lend ↗** opens the Lending Desk UI on :5175, a separate build.

**Optional live run** (spends about 5.05 XRP from the daily budget): `cd agent && .venv/bin/python demo.py --scripted`. Steps 1–3 appear as new teal ticker rows. At step 4 a Pending card appears above every tab; click **Approve on device**, and an amber row follows. Step 5 adds a red refusal.

## Prerequisites
- Docker Desktop running; Speculos container `speculos-xrp` up on 127.0.0.1:5000. If not:
  ```bash
  # From a directory that holds the Ledger XRP app ELF for Stax at apps/stax/app.elf (build LedgerHQ/app-xrp 2.8.1,
  # or copy ons/experiments/005-app-xrp-patch/app-xrp-2.8.2-lending-stax-api27.elf) and a test-only seed of your own in .seed:
  docker run -d --rm --name speculos-xrp -p 127.0.0.1:5000:5000 -p 127.0.0.1:9999:9999 -p 127.0.0.1:41000:41000 \
    -v "$PWD/apps:/apps:ro" ghcr.io/ledgerhq/speculos:latest --model stax --display headless \
    --api-port 5000 --apdu-port 9999 --vnc-port 41000 --vnc-password speculos --seed "$(cat .seed)" /apps/stax/app.elf
  ```
  Use `127.0.0.1:5000`, not `localhost:5000`. On macOS, `localhost:5000` reaches AirPlay (ControlCenter), which answers 403.
- Node 22, Python 3.12+.
- One-time only: `cd wallet && npm run setup` creates the hot wallet and funds it from the faucet. `cd agent && .venv/bin/python scripts/vet_merchant.py` vets the good merchant on the ledger. That script sends a CredentialCreate from the hot account and waits for the merchant's CredentialAccept. The credential stays on the ledger, so later boots do not need it. `allowedMerchants` in the runtime policy must stay `[]`.
- Demo-only setting: blind signing is ON in the Speculos XRP app, because the stock app shows DelegateSet as Unknown. To turn it off: gear (336,64) → toggle (345,136) → back (44,44). Never enable it on a real device.

## Before the wallet starts
Close any browser tab on the Ledger workshop app (http://localhost:5173). Its DMK session polls Speculos and corrupts the wallet's sign exchange: APDU replies cross and sign returns 6901. The Vite server itself can keep running. `up.sh` warns when :5173 is up.

## One command: start and stop
```bash
wallet/bin/up.sh      # or: cd wallet && npm run up
wallet/bin/down.sh    # or: cd wallet && npm run down
```
- **`up.sh`** checks that Speculos answers on 127.0.0.1:5000. If it does not, the script stops and points here. Then it starts each service that is not already healthy and waits on its health URL:

  | Service | Port | Health URL | Log |
  |---|---|---|---|
  | wallet, under `scripts/run.sh` (restarts on crash) | :7402 | `/health` | `wallet/data/server.log` |
  | good merchant | :8001 | `/health` | `agent/logs/good.log` |
  | rogue merchant | :8002 | `/health` | `agent/logs/rogue.log` |
  | dashboard | :5174 | `/` | `dashboard/dev.log` |

  It then waits for `deviceConnected` and prints the `GET /v1/status` summary: balances, device app, spent today, pending. Last it prints the on-ledger allowlist (accepted credentials and the Permissioned Domain). Each item prints one green ✓ or red ✗ line. The exit code is 1 if any line is red. Cold boot takes about 10 s.
- **`down.sh`** stops only our processes: the wallet's `run.sh` supervisor and child, the two merchants, and the dashboard Vite. A process is stopped only when both its command and its working directory are ours. Anything else on those ports is reported and left alone. It never touches Speculos (:5000), the workshop app (:5173), :8000, or the LEND ports (:5175, :7500 and the rest).
- **Wallet restart only:** kill the `node node_modules/.bin/tsx src/index.ts` child. `run.sh` restarts it after 2 s.

## Demo
1. `wallet/bin/up.sh`: all lines green.
2. Open http://localhost:5174. The home tab is Treasury: the live money-flow graph and ticker.
3. `cd agent && .venv/bin/python demo.py --scripted`:
   - Steps 1–3 are auto, signed by the hot key.
   - Step 4 holds. Click **Approve on device** on the Pending card, which shows above every tab. The wallet drives the Speculos taps.
   - Step 5 is refused with `merchant_not_credentialed`.
   - Expect `done: 5/5 steps matched`.
4. Optional extras:
   - Permissions tab: grant or revoke the agent's delegated Payment permission. The device signs it blind.
   - `demo.py --revoke-drill`.
   - Vet tab: the domain header.
   - Lend ↗ (:5175).

The daily budget is 100 XRP (`dailyBudgetDrops`). Each scripted run spends about 5.05 XRP. Spent-today resets at 00:00 local time on this Mac (America/New_York), so it is 0 again from midnight ET with no restart: `Audit.spentToday()` sums auto and approved rows since local midnight on every call.

## Useful checks
- `curl -s 127.0.0.1:7402/v1/status | jq`
- `curl -s 127.0.0.1:7402/v1/requests | jq '.[0:5]'`
- `curl -s 127.0.0.1:7402/v1/domain | jq`
- Emulator screen: `curl -s http://127.0.0.1:5000/screenshot -o /tmp/screen.png && open /tmp/screen.png`
- Explorer: `https://testnet.xrpl.org/transactions/<hash>`
