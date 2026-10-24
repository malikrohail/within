# Playground: "Be the agent"

A separate, flag-gated app: a visitor becomes a borrower agent on XRPL devnet and climbs five levels, each one a real
transaction they watch validate. API on :7510 (`server.py`, FastAPI), UI on :5176 (Vite + React). Nothing in
`lending/`, `wallet/` or `dashboard/` changes; the desk on :7500 and the stage UI on :5175 are only read from.

## Setup (once)

```sh
cd playground
python3 -m venv .venv && .venv/bin/pip install fastapi uvicorn xrpl-py==5.2.0 requests pytest httpx python-dotenv
(cd ui && npm install)
.venv/bin/python server.py --fund 10      # 10 pool accounts + 3 customer accounts from the devnet faucet -> data/pool.json
```

`data/` is gitignored and holds the seeds (pool + customers), sessions and per-session sweeper state. Nothing in it is
ever returned by the API or printed. The operator token is read from `lending/.env` server-side for the two
operator calls (broker credential, loan default) and never reaches the browser.

## Activate / shut down

```sh
playground/bin/up.sh      # needs the desk on :7500; starts API :7510 + UI :5176, PID files under data/
playground/bin/down.sh    # stage runbook pre-flight: stops both by their PID files, leaves :7500 / :5175 alone
```

Open http://localhost:5176/. A session claims one pool account (never-used accounts first; "start over" releases it,
and a released account keeps its history, so fund more for fresh ones).

## Levels

1. Get born: claim a pool account; score from the real `policy.score` over real evidence (24 at birth: ledger 20).
2. Earn: 5 XRP invoice payment from the next of three customers (same memo shape as `demo.py --income`); rescore.
   Offline ceiling for a fresh account: 61 without a credential, 75 with one (`minScoreAuto` is 70).
3. Get vetted: `POST :7500/v1/broker/credentials` (token server-side) then `CredentialAccept` with the session key.
   404/405/501 from the desk = "the broker is away", level skippable.
4. Borrow: 1 to 5 XRP (hard cap server-side), borrower-signed LoanSet via `borrower.build_request_body`, decision polled
   from the desk. The playground never calls approve or deny.
5. Repay or default: income + `sweeper.sweep_once` with the session key (state under `data/<session>/`), or a grace
   countdown then `POST /v1/loans/{id}/manage default` through the desk (token server-side).

## Gates

```sh
cd playground && .venv/bin/python -m pytest -q
cd playground/ui && npx tsc --noEmit -p . && npm run build
```
