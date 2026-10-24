# agent/

See ../docs/CONTRACT.md.

## Commands (run from agent/)

```bash
.venv/bin/python -m merchants.good      # :8001, auto-accepts its Credential from CREDENTIAL_ISSUER
.venv/bin/python -m merchants.rogue     # :8002, never vetted
.venv/bin/python scripts/vet_merchant.py [--wallet http://localhost:7402] [--timeout 120]
.venv/bin/python demo.py --scripted [--wallet http://localhost:7402]
.venv/bin/pytest -q
```

`vet_merchant.py` replaces `apply_allowlist.py`: it asks the wallet to issue an XRPL Credential to the good
merchant (`POST /v1/merchants`), writes `CREDENTIAL_ISSUER` to `agent/.env`, and waits until the merchant
has accepted it on the ledger.
