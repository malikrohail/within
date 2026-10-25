# Architecture

```
 demo agent (Python)            policy wallet (Node)                  XRPL testnet
 ───────────────────            ────────────────────                  ────────────
 x402_requests session   ──►    POST /v1/pay                           
   payment_header_factory       ├─ policy engine (code + policy.json)
                                ├─ auto  → hot key signs      ──────►  Payment (hot account)
                                ├─ hold  → DMK → Ledger/Speculos ──►  Payment (device account)
                                └─ refuse → 403
                                audit log (requests.jsonl)
        ▲                            ▲
        │ 402 / 200                  │ poll 1 s
 merchants (FastAPI, x402-xrpl)   dashboard (React)
 8001 good, 8002 rogue            approve-on-device / deny / policy editor
```

Three invariants:
1. The agent process never holds a signing key. It holds `http://localhost:7402`.
2. The decision is made in code from `policy.json` before any signing. Nothing the model says can change it.
3. Two accounts: a hot float for small spends, a device-held treasury for big ones. Blast radius is the float.
