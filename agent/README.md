# agent/: the paying agent and the demo merchants

Python. The agent buys API calls over x402 (HTTP 402 pay-per-call) and signs nothing itself: its x402 client hands every payment requirement to the wallet's `POST /v1/pay` and uses the signed blob the wallet returns. Two merchants serve the demo: a vetted one on :8001 and a rogue one on :8002 that never receives a Credential. XRPL testnet only.

The behaviour of the agent, the merchants and the five-purchase scripted run is specified in [docs/CONTRACT.md](../docs/CONTRACT.md).

## Setup

```sh
cd agent
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env     # merchant seeds are written here on first start; the file is gitignored
```

## Run

```sh
.venv/bin/python -m merchants.good      # :8001, accepts its Credential from the wallet's issuer
.venv/bin/python -m merchants.rogue     # :8002, never vetted
.venv/bin/python scripts/vet_merchant.py [--wallet http://localhost:7402] [--timeout 120]
.venv/bin/python demo.py --scripted [--wallet http://localhost:7402]
```

`wallet/bin/up.sh` starts both merchants with the wallet. `vet_merchant.py` runs once: it asks the wallet to issue an XRPL Credential to the good merchant (`POST /v1/merchants`), writes `CREDENTIAL_ISSUER` to `agent/.env`, and waits until the merchant has accepted the Credential on the ledger. The merchants need testnet faucet access the first time they start.

`demo.py --scripted` makes five purchases: three sign automatically on the hot key, one is held and then signed in the Speculos emulator after scripted taps, and one to the rogue merchant is refused before anything reaches the ledger. It exits 0 only when all five decisions match.

## Test

```sh
.venv/bin/pytest -q -m "not network"    # offline
.venv/bin/pytest -q                     # includes network tests
```
