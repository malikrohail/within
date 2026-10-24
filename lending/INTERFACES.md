# lending/INTERFACES.md — binding contract for the lending modules

This file defines names, shapes and signatures. All amounts are **XRP drops as decimal strings** in JSON (`"10000000"` = 10 XRP); counts/seconds are ints. Times in JSON are **unix seconds** (int); convert to/from ripple epoch only inside common.py (`ripple = unix - 946684800`). Network: devnet JSON-RPC `https://s.devnet.rippletest.net:51234/` only.

## 0. Constants (common.py exports them; nobody else hard-codes them)
```python
DEVNET_URL = "https://s.devnet.rippletest.net:51234/"
RIPPLE_EPOCH = 946684800
PAYMENT_INTERVAL = 90          # s, LoanSet.PaymentInterval (spec min 60; allowed 60..120)
GRACE_PERIOD = 60              # s, LoanSet.GracePeriod (60..PAYMENT_INTERVAL)
LOAN_SET_FEE = "30"            # drops; >= 2x base fee (base 10) -> safe margin
SUBSCRIPTION_HOURS = 4         # VaultCreate.SubscriptionDate = now + 4 h (deposits accepted until then)
REDEMPTION_HOURS = 8           # VaultCreate.RedemptionDate  = now + 8 h (hours out)
COVER_DEPOSIT_DROPS = "20000000"   # broker first-loss cover, 20 XRP
LOAN_BROKER = dict(management_fee_rate=1000, debt_maximum="0",   # 1 % ; 0 = no cap
                   cover_rate_minimum=10000, cover_rate_liquidation=100000)  # 10 %, 100 %; unit 1/100,000 (1/10 bps)
# Default cover hit = min(CoverAvailable, DebtTotal x CoverRateMinimum x CoverRateLiquidation) = 10 % of DebtTotal.
# The old liquidation 10000 gave 10 % x 10 % = 1 % (666,667 drops on ~66.7 XRP debt, BA9940D1); 100000 gives
# 20 -> 14 XRP on a 60 XRP default (A8DCC89330485B28AA960332DB87D2984C6AB1B2D268B95A80E6B1F628D6991E).
SETUP_DEPOSITS = {"depositorA": "20000000", "depositorB": "10000000"}  # bootstrap; demo adds 100/50 XRP
```
Rates on-chain are **1/10 basis points** (100000 = 100 %). policy.json `interestRateBps: 800` (8 % APR) -> `LoanSet.InterestRate = interestRateBps * 10 = 8000`.

## 1. Loan terms (used by desk, borrower, demo, tests)
- `paymentInterval = PAYMENT_INTERVAL` (90), `gracePeriod = GRACE_PERIOD` (60) for every loan.
- `paymentTotal = max(1, termSeconds // PAYMENT_INTERVAL)`. Demo uses `termSeconds = 270` -> 3 payments.
- `termSeconds` outside `[termSecondsMin, termSecondsMax]` -> HTTP 422 `term_out_of_range` (validation, not a decision; no record stored).
- `interestRate = policy.interestRateBps * 10`. No origination/service/late fees (fields omitted). Flags 0.
- `Fee = LOAN_SET_FEE`. `LastLedgerSequence = current + 60` (~3-4 min, covers `holdTimeoutSeconds` 120).
- First payment due = creation + 90 s; default allowed when `now >= nextPaymentDue + GRACE_PERIOD` (~150 s after creation).
- Installment amount = Loan `PeriodicPayment`, rounded **up** to whole drops (it is a Number, may be fractional).

## 2. lending/.env and lending/accounts.json
`.env` (only place seeds exist): `BROKER_SEED`, `DEPOSITOR_A_SEED`, `DEPOSITOR_B_SEED`, `BORROWER_SEED`, and `CUSTOMER_SEED` (written once by `demo.py --income`; accounts.json `accounts.customer`). Optional `DESK_URL=http://localhost:7500`.
`accounts.json` (written by setup.py, **no seeds, ever**):
```json
{
  "network": "devnet",
  "createdAt": 1761300000,
  "accounts": {"broker": "r...", "depositorA": "r...", "depositorB": "r...", "borrower": "r..."},
  "vaultId": "64HEX", "shareMptId": "48HEX", "loanBrokerId": "64HEX",
  "vaultKind": "closed", "subscriptionDate": 1761314400, "redemptionDate": 1761328800,
  "setupTx": {"vaultCreate": "HASH", "loanBrokerSet": "HASH", "coverDeposit": "HASH",
              "depositA": "HASH", "depositB": "HASH"}
}
```
Names in code: `"broker" | "depositorA" | "depositorB" | "borrower"` everywhere (wallet(), accounts keys, logs).

## 3. common.py public API
```python
client() -> JsonRpcClient                       # devnet only; asserts URL == DEVNET_URL
load_accounts() -> dict                         # parsed accounts.json; FileNotFoundError if setup not run
wallet(name: str) -> Wallet                     # seed from lending/.env (python-dotenv); never logs the seed
submit_and_wait(tx: Transaction, w: Wallet) -> dict
    # autofill+sign+submit_and_wait; returns
    # {"hash", "engineResult", "validated": bool, "ledgerIndex", "created": {LedgerEntryType: index, ...}}
    # "created" = meta.AffectedNodes CreatedNode LedgerEntryType -> LedgerIndex (Vault, LoanBroker, Loan, MPTokenIssuance)
    # never raises on tec*; raises only on transport errors / unsigned validation errors
build_loan_set(borrower_addr: str, loan_broker_id: str, broker_addr: str, principal_drops: str,
               term_seconds: int, interest_rate: int) -> LoanSet   # Account=borrower, Counterparty=broker, terms per §1
borrower_sign_loan_set(w_borrower: Wallet, tx: LoanSet) -> str     # autofill (Sequence, LastLedgerSequence) + sign -> blob hex
verify_loan_set_blob(blob: str, request: dict, accounts: dict, policy: dict) -> str | None
    # decode blob; None if Account==request.borrower, Counterparty==broker, LoanBrokerID, PrincipalRequested,
    # InterestRate, PaymentTotal, PaymentInterval, GracePeriod, Fee all match §1; else a reason string
    # then not already co-signed, signed, and signed by Account: derive_classic_address(SigningPubKey) == Account and
    # keypairs.is_valid_message(encode_for_signing(tx), TxnSignature, SigningPubKey); else "blob_mismatch:bad_signature"
    # (any decode/crypto error included, so a victim's pubkey + garbage signature is a 400, never a 500)
    # By design a borrower must sign with its master key: a regular-key signer (SigningPubKey derives to another
    # address) and a multisigned blob (empty SigningPubKey, Signers) are refused "blob_mismatch:bad_signature".
cosign_loan_set(w_broker: Wallet, blob: str) -> dict
    # sign_loan_set_by_counterparty(w_broker, blob) -> submit tx_blob -> wait
    # returns {"hash", "engineResult", "validated", "loanId"}   (loanId = created["Loan"] or None)
loan_pay(w_borrower: Wallet, loan_id: str, amount_drops: str | None = None) -> dict
    # amount None -> ceil(Loan.PeriodicPayment); returns submit_and_wait shape
loan_manage(w_broker: Wallet, loan_id: str, action: "impair"|"unimpair"|"default") -> dict
    # flags TF_LOAN_IMPAIR 0x20000 / TF_LOAN_UNIMPAIR 0x40000 / TF_LOAN_DEFAULT 0x10000
vault_state(vault_id: str, loan_broker_id: str) -> dict   # see below
list_loans(loan_broker_id: str) -> list[dict]             # see below
audit_append(record: dict) -> None   # appends one JSON line {"ts": unix, **record} to lending/data/audit.jsonl
                                     # (mkdir data/; gitignored). Callers pass {"event": str, ...}; never seeds/blobs.
```
`vault_state` reads `ledger_entry` for the Vault, the LoanBroker and the `mpt_issuance` of `ShareMPTID`. Ledger amounts are parsed with `int(Decimal(x))`. Returns:
```json
{"vaultId": "...", "loanBrokerId": "...", "shareMptId": "...",
 "assetsTotalDrops": "Vault.AssetsTotal", "assetsAvailableDrops": "Vault.AssetsAvailable",
 "loansOutstandingDrops": "AssetsTotal - AssetsAvailable", "debtTotalDrops": "LoanBroker.DebtTotal",
 "lossUnrealizedDrops": "Vault.LossUnrealized or 0", "coverDrops": "LoanBroker.CoverAvailable",
 "sharesTotal": "MPTokenIssuance.OutstandingAmount (string)",
 "utilizationPct": 0.0, "coverRatioPct": 100.0,
 "subscriptionDate": 0, "redemptionDate": 0, "ledgerIndex": 0}
```
- `utilizationPct = 100 * loansOutstanding / assetsTotal` (0.0 if assetsTotal == 0), float rounded to 2 dp.
- `coverRatioPct = 100 * cover / debtTotal`; `100.0` if debtTotal == 0. Float, 2 dp.
- If a live field name differs from the above, fix it inside common.py only; output keys stay.

`list_loans` = `account_objects` of the broker filtered `type=loan`, `LoanBrokerID == loan_broker_id`, newest first:
```json
{"loanId": "Loan index", "borrower": "Loan.Borrower", "principalDrops": "PrincipalOutstanding",
 "totalOutstandingDrops": "TotalValueOutstanding", "periodicPaymentDrops": "ceil(PeriodicPayment)",
 "interestRate": 8000, "paymentInterval": 90, "gracePeriod": 60,
 "nextPaymentDue": 1761300090, "paymentRemaining": 2, "startDate": 1761300000,
 "status": "active|impaired|defaulted|paid"}
```
`status`: Flags & 0x10000 (lsfLoanDefault) -> `defaulted`; Flags & 0x20000 (lsfLoanImpaired) -> `impaired`; `paymentRemaining == 0` -> `paid`; else `active`. (If the borrower's loans live under the borrower's owner dir instead, query both and dedupe by loanId.)

## 4. Underwriting: evidence.py + policy.py (LOCKED 09:10Z)
No bureaus, no LLM in the score. The **desk** builds the Evidence (the borrower cannot hand in its own facts); the borrower only declares purpose and existing debt.

### evidence.py
```python
build_evidence(borrower: str, declared: dict, client=None, now: int|None=None, window_days: int = 30) -> dict   # Evidence below
ledger_evidence(borrower: str, client, now: int, window_days: int) -> dict      # devnet only (account_tx paginated, account_objects, account_info)
bank_evidence(borrower: str) -> dict | None   # Plaid Sandbox iff PLAID_CLIENT_ID+PLAID_SECRET in lending/.env AND borrower == accounts.borrower, else None
```
Evidence (JSON-serialisable; amounts are drop strings; the UI renders it as-is):
```json
{"borrower": "r...", "asOf": 1761300000, "windowDays": 30,
 "ledger": {"accountExists": true, "accountAgeLedgers": 1234,
            "inboundPaymentCount": 24, "inboundVolumeDrops": "61000000", "distinctPayers": 5,
            "topPayerSharePct": 31.5, "activeDays": 21,
            "activeLoans": 0, "loanDebtDrops": "0", "loanPrincipalDrops": "0", "pastDefaults": 0,
            "hasAcceptedCredential": false, "sampleTxHashes": ["HASH", "..."],
            "memoDatedPayments": 24, "ledgerActiveDays": 1,
            "x402IncomeDrops": "61000000", "x402Payments": 24, "x402Payers": 5, "otherInboundDrops": "0"},
 "bank": null,
 "declared": {"purpose": "inventory", "principalDrops": "10000000", "termSeconds": 270, "existingDebtDrops": "5000000"}}
```
- Inbound payments = validated `Payment` txs with `Destination == borrower`, XRP, `delivered_amount` counted, from accounts other than the borrower, excluding LoanSet/Loan disbursements and faucet funding (the faucet account(s) are excluded by address; list them as a constant).
- "Day" of a payment = the `date` field of its invoice memo if present (MemoType hex("invoice"), MemoData hex(JSON {"invoice": "INV-…", "date": "YYYY-MM-DD"})), else the ledger close time. Reason: on devnet the 30-day history is written in one setup run; the memo carries the business date. Say this in notes/report; never fake ledger timestamps.
  Bound: the memo date counts only when |close date - memo date| <= `MEMO_DATE_TOLERANCE_DAYS` (env, read per call; unset = unlimited, the demo/setup-gate/test default; set 7 in production), else the close date counts. Ledger evidence also reports `memoDatedPayments` (payments dated by their memo) and `ledgerActiveDays` (active days by close date, memos ignored); the Why panel labels Active days "(from invoice memos, demo seed)" when the two day counts differ. Repro (upstream review case): 24 same-day payments backdated by memo score 87 auto unbounded, 69 hold at tolerance 7. No account-age rule is scored.
- x402 income (evidence only; `score()` never reads it): a counted inbound payment is x402 income
  when it carries a Memo of MemoType hex("invoice") or hex("x402") with parseable MemoData (UTF-8; JSON for invoice;
  blank = not x402). `x402IncomeDrops` + `otherInboundDrops` = `inboundVolumeDrops`; `x402Payments` counts them,
  `x402Payers` their distinct senders. The four keys are present (zero) on missing accounts and empty histories. The Why
  panel's On-chain history column opens with "x402 income: 61 XRP from 5 paying customers" (or "None").
- Window = invoice dates within the last `window_days` before `asOf`.
- activeLoans / loanDebtDrops / pastDefaults from Loan objects where `Borrower == borrower` (status per §3 flags).
  `loanPrincipalDrops` = sum of `PrincipalOutstanding` over the same open loans (`loanDebtDrops` is TotalValueOutstanding,
  principal + interest); policy.decide's `declared_debt_understated` compares against it.
- `bank` when connected: `{"connected": true, "institution": "ins_109508", "days": 90, "avgMonthlyInflowUsd": 0.0, "avgBalanceUsd": 0.0, "inflowOutflowRatio": 0.0, "nsfCount": 0}`; when not: `null` (UI: "bank data: not connected").

### policy.py (pure, no I/O)
```python
DEFAULT_POLICY: dict                       # exactly the spec default; policy.json mirrors it
load_policy(path="policy.json") -> dict ;  save_policy(policy, path="policy.json") -> dict   # validates keys == DEFAULT_POLICY keys
score_breakdown(evidence: dict) -> dict    # {"total": int, "weights": {"ledger": 60|90, "bank": 30|0, "declared": 10},
                                           #  "ledger": {"score": 0..100, "rules": [{"rule", "value", "points"}]},
                                           #  "bank": {...same...} | None, "declared": {...same...}, "capped": "past_default"|None}
score(evidence: dict) -> int               # == score_breakdown(evidence)["total"]
decide(request: dict, vault_state: dict, policy: dict) -> {"decision", "reason", "score", "breakdown"}   # request carries "evidence"
GOOD_SMALL, GOOD_LARGE, BAD: dict          # Evidence fixtures below; tests assert score == 85, 75, 20 exactly
```
**Weights** 60 / 30 / 10; bank `null` -> 90 / 0 / 10. `total = (wL*L + wB*B + wD*D + 50) // 100` (integer math, no float
rounding), then `min(total, 35)` if `pastDefaults > 0`. Thresholds are module constants. XRP = 1 000 000 drops.
- **L** ledger (max 100): `activeDays` (window 30) >=20: 20, >=10: 10 | `inboundVolumeDrops` >=50 XRP: 20, >=20 XRP: 10 | `distinctPayers` >=4: 15, >=2: 7; `topPayerSharePct` <=40: 10, <=70: 5 (0 if no payments) | `activeLoans == 0`: 10 | `pastDefaults == 0`: 10 | `hasAcceptedCredential`: 15
- **D** declared (max 100; V = LEDGER `inboundVolumeDrops`, never self-reported revenue): principal/V <=0.25: 40, <=1.0: 25 (V == 0 -> 0) | existingDebt/V: debt 0: 40, <=0.30: 25, <=1.0: 10 (V == 0 and debt > 0 -> 0); purpose in `{"inventory","payroll","equipment","receivables"}`: 10 | termSeconds <= 3600: 10. Anything unlisted scores 0.
Bank sub-score B (max 100, only when connected): avgMonthlyInflowUsd >=5000: 30, >=1000: 15; inflowOutflowRatio >=1.10: 30,
>=1.00: 15; avgBalanceUsd >=2000: 20, >=500: 10; nsfCount == 0: 20. Bank data is linked **only** to accounts.json `borrower`
(`bank_evidence(borrower)` returns None for any other address), so a fresh account never inherits the sandbox bank.
Fixtures (bank `null`; ledger fields not listed are `accountExists: true, accountAgeLedgers: 5000, loanDebtDrops: "0", loanPrincipalDrops: "0",
pastDefaults: 0, hasAcceptedCredential: false, sampleTxHashes: []`):
| fixture | ledger | declared | L | D | total |
|---|---|---|---|---|---|
| GOOD_SMALL (step 3) | activeDays 22, payments 24, volume 61 XRP, payers 5, top 31.5 %, activeLoans 0 | 10 XRP, debt 5 XRP, inventory, 270 s | 85 | 85 | **85** |
| GOOD_LARGE (step 4) | same, activeLoans 1, loanDebtDrops 10 XRP, loanPrincipalDrops 10 XRP | 60 XRP, debt 15 XRP, inventory, 270 s | 75 | 70 | **75** |
| BAD (step 5, fresh) | activeDays 0, payments 0, volume 0, payers 0, top 0, activeLoans 0, accountAgeLedgers 50 | 10 XRP, debt 30 XRP, inventory, 270 s | 20 | 20 | **20** |
Live devnet runs: demo.py asserts the **decision** (auto / hold / refuse score_too_low), not the exact score. Optional `--llm` credit memo (claude-sonnet-5-5) explains the breakdown; it is stored on the record as `memo` and never changes score or decision.
- decide order: declared `existingDebtDrops` + 10 drops < ledger `loanPrincipalDrops` (missing = 0) refuse
  `declared_debt_understated` (the borrower declared less debt than its open on-ledger loans; checked first, so the refusal
  names the lie rather than a score it also lowers; the desk's `batch_unfunded` refusal still comes before decide); then
  score<minScore refuse `score_too_low`; p>maxPrincipalDrops `over_max_principal`; utilization after loan > maxUtilizationPct `vault_utilization`; cover/(debtTotal+p) < minCoverRatioPct `cover_below_minimum`; p<=maxAuto and score>=minScoreAuto -> auto; else hold (`over_auto_limit` | `score_below_auto`). Term outside [termSecondsMin, termSecondsMax] is a 422 at the desk (not a decision).
- desk.create_request, after decide (policy.py unchanged): an `auto` whose evidence has `hasAcceptedCredential` false
  becomes hold `no_broker_credential` (a human can still approve it; refusals stay refusals). `hasAcceptedCredential` is
  true only for a Credential with Issuer = accounts.json `broker`, CredentialType = hex("kyb-borrower"), lsfAccepted set,
  and no Expiration or Expiration (Ripple time) after asOf. setup.py issues it (CredentialCreate broker->borrower +
  CredentialAccept) for the demo borrower, so the seeded borrower scores 99 (GOOD_SMALL 85, +15 on the ledger sub-score,
  about +14 total at 90% weight). When the credential counts, ledger evidence also carries `credentialIssuer` (the broker
  address) and `credentialType` ("kyb-borrower"); both are absent otherwise. The Why panel says "KYB credential
  kyb-borrower, issued by the broker rEH59…: +15 ledger points (about +14 on the score)", with the points taken from the
  breakdown's `hasAcceptedCredential` rule and the total as round(points x ledger weight / 100) (90 without bank, 60 with).
  The auto re-check after the second opinion re-decides on a fresh vault read but the request-time evidence snapshot,
  so the credential gate survives it.

## 5. Desk API (desk.py, FastAPI, port 7500, CORS allow origin `http://localhost:5175`)
The desk holds **only** the broker key. The borrower holds **only** the borrower key.
**Co-signature handoff (binding):** borrower.py builds the LoanSet with `Account=borrower, Counterparty=broker` (common.build_loan_set), signs it (`borrower_sign_loan_set`) and sends the blob in the request. The desk runs `verify_loan_set_blob`; on auto (or on approve) it adds the broker's `CounterpartySignature` (`cosign_loan_set`) and submits. The borrower signs one LoanSet at a time (sequence), and waits for that request to finish before its next tx.

Request body `POST /v1/loan-requests`:
`{"borrower": "r...", "principalDrops": "10000000", "termSeconds": 270, "purpose": "inventory", "declared": {"existingDebtDrops": "0"}, "signedLoanSet": "HEX blob"}` — the desk calls `evidence.build_evidence(borrower, declared)`; the record's `evidence` is the full Evidence and `breakdown` is `score_breakdown(evidence)`.
Loan-request record (every route returns this shape; `signedLoanSet` is never echoed):
```json
{"id": "lr_0001", "ts": 1761300000, "borrower": "r...", "principalDrops": "10000000", "termSeconds": 270,
 "purpose": "inventory", "evidence": {}, "breakdown": {}, "score": 85, "decision": "auto|hold|refuse",
 "status": "auto|held|approved|denied|refused|expired|failed", "reason": null,
 "loanId": "64HEX|null", "txHash": "HASH|null", "engineResult": "tesSUCCESS|null", "decidedBy": "policy|human|timeout", "memo": "str|null",
 "secondOpinion": {"recommendation": "agree|hold|deny", "memo": "str", "flags": ["str"]} | "off" | null, "secondOpinionMs": 7012,
 "policyHash": "16 hex", "blobKey": "rBorrower:Sequence|null", "loanSetHash": "64 HEX", "approvalTxHash": "64 HEX|null"}
```
`decidedBy` is also `"ledger"` when the approve was proven by a Ledger-signed testnet Payment (below).
- `policyHash` = `policy.policy_hash(policy)` = `sha256(json.dumps(policy, sort_keys=True, separators=(",",":")))[:16]`,
  stamped when the request is decided and never rewritten (records from before this field have none; the UI shows it only
  when present). Audit lines: `loan_request_decided` carries `policyHash`; `loan_request_approved` carries the record's
  `policyHash` and the approve re-check's `recheckPolicyHash` side by side; `policy_updated` carries the new `policyHash`.
  Provenance only: who may `PUT /v1/policy` is gated by the operator token below, not by this. `approve_blocked` and
  `auto_recheck_blocked` carry `policyHash` + `recheckPolicyHash` the same way.
  The final re-check before any co-sign (auto after the second opinion, approve after the testnet read) re-reads
  policy.json under the `PUT /v1/policy` lock inside the co-sign lock, so a tightening that completed in between holds or
  refuses the request; its hash is `recheckPolicyHash` on the record (auto: always; approve: when it co-signs) and on
  the audit line.
- **Operator token (auth.py):** env `DESK_TOKEN` (the desk loads it from `lending/.env` when the shell has none), header
  `X-Desk-Token`. Required on `POST .../approve`, `POST .../deny`, `GET .../signed-loan-set`, `POST /v1/loans/{loanId}/manage`,
  `POST /v1/broker/cover`, `POST /v1/broker/credentials`, `PUT /v1/policy`: env unset -> 503 `operator_token_unset` (fails closed), missing or wrong
  header -> 401 `operator_token_required`, nothing signed. `POST .../notes` needs it only from a non-loopback caller.
  Borrower `POST /v1/loan-requests` and every GET except `signed-loan-set` stay open. Callers: `demo.py desk_post`
  (shell or `lending/.env`), the UI (`VITE_DESK_TOKEN`).
- **Idempotency:** `blobKey` = `<Account>:<Sequence or TicketSequence>` of the signed LoanSet. A second POST with the same
  key returns the first record (200, no new record, no second co-sign); one that lands while the first is still being
  decided gets 409 `duplicate_in_progress`. Undecodable blobs have `blobKey: null` and are never deduplicated.
- **Pending cap:** `policy.maxPendingDrops` (drops string, `"0"` = no cap). A request whose principal plus every held,
  in-flight and still-being-decided request's principal exceeds it is `refused`, reason `pending_exposure_cap`, no tx.
  The cap is read at admission under the same lock `PUT /v1/policy` writes under. A held record whose
  `ts + holdTimeoutSeconds` has passed no longer counts, even before a GET sweeps it to `expired`.
- **Ledger approval:** `loanSetHash` = sha256 of the signed LoanSet blob bytes, uppercase hex. When env
  `DESK_APPROVER_ACCOUNT` is set (stage: `rUGeRsKjpnDVAi1uJYhAxWXbETC917VQ6B`), `GET /health` reports it as
  `approverAccount` and approve needs `{"approvalTxHash"}` (else 422 `approval_tx_required`): the desk reads that tx from
  testnet and requires validated + tesSUCCESS + Payment + `Account == approver` + no `Delegate` field + `SigningPubKey`
  = the approver's master key (or `== DESK_APPROVER_PUBKEY` when set) + `Memos[0]` MemoType `loan-approval` and
  MemoData `== loanSetHash`. Any mismatch -> 409 with the reason (`tx_lookup_failed:*`, `approval_not_validated`,
  `approval_not_success:*`, `approval_not_payment`, `approval_wrong_account`, `approval_delegated`,
  `approval_wrong_signer`, `approval_wrong_memo_type`, `approval_hash_mismatch`), audited `approve_blocked`, nothing
  signed. Pass -> `decidedBy: "ledger"`, `approvalTxHash` on the record. Unset -> token-only approve, `decidedBy: "human"`,
  `approverAccount: null`. The hold deadline is re-checked after the testnet read.
  Every approve stamps `approvedBy` (the approver account on the Ledger path, `"operator"` on token-only) and
  `approvedAt` (unix seconds) on the record and the `loan_request_approved` audit line; the UI card shows both.
  Optional second Memo `loan-terms` (wallet contract v1.7): when present its ASCII MemoData must equal
  `approve loan <principal XRP> to <borrower> <PaymentTotal> payments`, built from the STORED borrower-signed blob (never
  the request body; principal without trailing zeros, e.g. `3.333335`); mismatch -> 422 `terms_mismatch`, audited
  `approve_blocked`, nothing signed. Absent -> accepted as before (approval Payments signed before v1.7 still verify).
- **Restart reconcile (reconcile.py):** at startup (`reconcile_all`, node down =
  skipped with a log line) and inside approve before any co-sign, a `held` (or `auto` with no `txHash`) record that still
  holds its blob is checked against devnet: the borrower's Sequence already consumed by a validated tesSUCCESS LoanSet
  for THIS desk's LoanBrokerID carrying the stored blob's TxnSignature (F1: a LoanSet with another broker never matches) ->
  the record becomes `approved` (held) / stays `auto` with that `txHash` + `loanId`, reason `reconciled_after_restart`,
  approve answers 409 `already_landed:<hash>`; consumed by anything else -> `expired`, 409 `sequence_consumed`; the
  blob's LastLedgerSequence passed -> `expired`, 409 `blob_expired`. Blobs are dropped, audit event `reconciled`.
- second opinion (`second_opinion.review`, `desk.apply_second_opinion`): after `policy.decide` and before any co-sign, only on `auto` and `hold` (never on `refuse`, never in approve/deny or the approve re-check), the desk asks the model once with a 20 s timeout. `decision` stays the policy's; `status`/`reason` carry the effect: `auto` + `hold` -> `status: held`, `reason: "second_opinion_hold"`, no co-sign; `auto` or `hold` + `deny` -> `status: held`, `reason: "second_opinion_deny"` (never auto-denied); `hold` + `hold` -> stays held with its policy reason; `agree`, timeout, failure or schema mismatch (`secondOpinion: null`) -> no change. `memo` = the second opinion's memo when there is one. `secondOpinionMs` = wall time of the call (int), `null` on refuse (no call). A second-opinion hold is approved or denied like any held record. Audit event `second_opinion` `{id, ms, recommendation, flags, status, reason}`.
- **`SECOND_OPINION=off` (scripted runs only):** a shell switch read at desk start like `DESK_APPROVER_ACCOUNT=off`
  (the shell value wins; `lending/.env` leaves it on), logged once as `second opinion OFF (scripted run)`. While it is
  off `second_opinion.review` is never called, no `second_opinion` audit line is written, and every record decided
  meanwhile (auto, held and refused alike) stores `secondOpinion: "off"` with `secondOpinionMs: null`, so a reader can
  tell "off" from `null` ("model down / no usable answer"). The stage desk runs with it on.
- C1 gaps (security review 2): when the final re-check (auto path after the second opinion, approve path after the testnet
  read) blocks under a policy whose hash differs from the record's `policyHash`, the reason is `policy_changed_mid_flight`
  and the audit line keeps the rule that blocked as `recheckReason`. A policy.json that fails to load at the auto
  re-check holds the record (`recheck_unavailable: ...`), never a 500 with the id left in flight.
- Review 2 (fixes C2, C3): **C2** a `pending_exposure_cap` refusal is recorded (record + `loan_request_decided`)
  under the hash of the policy read at admission, the one that refused. **C3** a record stored before the auth change
  has no `blobKey`; `find_duplicate` derives it from the stored blob and writes it back, so an identical resubmit
  returns the first hold.
- auto: synchronous co-sign + submit -> 200, `status: auto`, `loanId`, `txHash`. Ledger failure -> `status: failed`, `reason` = engine result.
  `common.wait_for_tx` ends when the validated ledger passes the tx's LastLedgerSequence (current + 60); `WAIT_TIMEOUT_S`
  = 300 s is only a wall-clock backstop past that horizon. A tx that expired this way is `reason: "txnNotFound"` (or
  `not_validated`; `batch:` prefixed for the Batch) and the UI words it "Expired before validation". When the backstop
  fires while the ledger has not passed LastLedgerSequence, the reason is `timeout_waiting` (`batch:timeout_waiting`)
  and the UI words it "Timed out waiting for validation" (the tx may still apply). Clients
  (`borrower.POST_TIMEOUT_S`, demo `desk_post`) wait 2 x WAIT_TIMEOUT_S + 60 s: a working-capital POST or approve can
  run two serial waits.
- refuse: 200, `status: refused`, `reason` from §4, no tx.
- hold: 200 immediately, `status: held`. After `holdTimeoutSeconds` without approve/deny -> `expired` (lazy check on every read is fine).
- blob mismatch -> 400 `{"detail": "<verify reason>"}`, nothing stored.
Routes:
| route | body | returns |
|---|---|---|
| `POST /v1/loan-requests` | request body | record |
| `GET /v1/loan-requests` | — | `{"requests": [record, ...]}` newest first |
| `GET /v1/loan-requests/{id}` | — | record (404 unknown) |
| `POST /v1/loan-requests/{id}/approve` | `{}` or `{"approvalTxHash": "64 hex"}` (token) | record, `status: approved` + `loanId`, `txHash` (co-signs the stored blob) ; 409 if not held or the Ledger approval fails |
| `GET /v1/loan-requests/{id}/signed-loan-set` | — (token) | `{"id", "loanSetHash", "signedLoanSet"}` of a **held** request only (409 `not_held: <status>` otherwise), for the wallet's `POST /v1/lend/approve {loanSetBlob, loanSetHash}` |
| `POST /v1/loan-requests/{id}/deny` | `{"reason"?: str}` (token) | record, `status: denied` ; 409 if not held |
| `POST /v1/loan-requests/{id}/notes` | `{"from": str 1-40 chars, "text": str 1-500 chars}` | record; appends `{"from", "text", "ts"}` to the record's `notes` (append-only, persisted). 404 unknown id, 422 on bounds. Display only: notes never change status/decision/reason/score and no decision path reads them. Every record carries `"notes": [...]` (`[]` when none) |
| `POST /v1/loans/{loanId}/manage` | `{"action": "impair"|"unimpair"|"default"}` (token) | `{"loanId", "action", "hash", "engineResult"}` (broker key stays in desk); `default` adds `"coverBeforeDrops", "coverAfterDrops", "coverAbsorbedDrops"` (LoanBroker.CoverAvailable read from the validated ledger before and after; after/absorbed `null` if the after-read failed) and `"vaultLossDrops", "defaultAmountDrops"`; on tesSUCCESS the desk reads the default's tx meta (`find_default`) and its values replace the cover reads and fill the two loss fields (`null` if the meta read failed); it stores the default entry when the cover hit is known, with the loss fields only when the meta was read |
| `GET /v1/loans` | — | `{"loans": [list_loans item + "requestId": str|null + "default": default entry|null + "sweeps": [§9 record, oldest first]], "ledgerIndex": int}`; a defaulted loan with no stored entry is backfilled once from devnet (Loan.PreviousTxnID, else the LoanBroker pseudo-account's account_tx -> the LoanManage(default) meta) and cached; a failed backfill is `null` for that poll (never 503) and retried on the next; a stored entry without `vaultLossDrops` (written before those fields, or when the manage route could not read the meta) is re-read from the meta once: a hit replaces it, a miss stores both loss fields as `null`, a failure serves the stored entry and retries on the next poll |
| `POST /v1/loans/{loanId}/sweeps` | sweep record (§9), no token | the stored verified record (200, also on a duplicate); 422 `<reason>` when it does not verify, nothing stored |
| `POST /v1/broker/cover` | `{"amountDrops": "<integer string>"}` (token) | `{"hash", "engineResult", "coverBeforeDrops", "coverAfterDrops"}`: LoanBrokerCoverDeposit signed by the broker key in the desk. 422 `amount_out_of_range` unless 0 < amount <= 100 XRP (non-integer -> pydantic 422); 409 `cover_deposit_in_progress` while one runs; ledger failure -> 503 `ledger_unavailable: ...`, nothing claimed. `coverAfterDrops` null if the after-read failed. audit + desk_examples entry |
| `POST /v1/broker/credentials` | `{"subject": "r..."}` (token) | `{"hash", "engineResult"}`: CredentialCreate type hex(`kyb-borrower`) from the broker to `subject`, signed by the broker key in the desk (the subject then signs CredentialAccept itself). 409 `credential_exists` when this broker already issued that type to `subject` (accepted or not; same account_objects lookup as `setup.find_credential`), nothing signed; 422 on a non-classic or bad-checksum address (`invalid_subject` / pydantic 422); one lookup + create at a time; ledger failure -> 503 `ledger_unavailable: ...`. audit `broker_credential_create` + desk_examples entry |
| `GET /v1/vault` | — | `vault_state(...)` + `{"accounts": accounts.accounts, "setupTx": {...}, "policy": policy}` |
| `GET /v1/policy` / `PUT /v1/policy` | full policy object (PUT: token) | policy (PUT validates keys = DEFAULT_POLICY keys, fills an omitted `maxPendingDrops` with `"0"`, writes the validated dict to policy.json) |
| `GET /health` | — | `{"ok": true, "network": "devnet", "broker": "r...", "ledgerIndex": int, "approverAccount": "r...|null"}` |
Request records live in memory plus `lending/data/requests.json` (gitignored). Default entries live in `lending/data/defaults.json` (gitignored, atomic write): `{loanId: {"hash", "engineResult", "coverBeforeDrops", "coverAfterDrops", "coverAbsorbedDrops", "vaultLossDrops", "defaultAmountDrops", "ts"}}`. From the LoanManage(default) meta: cover = LoanBroker `PreviousFields.CoverAvailable - FinalFields.CoverAvailable`; `vaultLossDrops` (what depositors absorbed) = Vault `PreviousFields.AssetsTotal - FinalFields.AssetsTotal`; `defaultAmountDrops` = the Loan's `PreviousFields.PrincipalOutstanding`; cover + vault loss = default amount (9/9 run, tx 32B27095: 12,666,667 + 47,333,333 = 60,000,000). `null` loss fields = the meta could not be read or had no Vault/Loan node. Every decision and tx -> `audit_append`.
Tests inject a fake ledger: desk creates its ledger adapter via `desk.get_ledger()` (FastAPI dependency) returning an object with `vault_state`, `list_loans`, `cosign_loan_set`, `loan_manage`; tests override it.

## 6. borrower.py / demo.py
```python
# borrower.py
request_loan(principal_drops: str, term_seconds: int, purpose: str, existing_debt_drops: str, wallet=None, desk_url=DESK_URL) -> dict   # record; wallet defaults to common.wallet("borrower")
wait_for(request_id: str, statuses=("approved","denied","expired","failed"), timeout=180) -> dict
pay_installment(loan_id: str) -> dict   # common.loan_pay(borrower, loan_id)
```
demo.py `--scripted` (desk must be running): 1-2 `VaultDeposit` A 100 XRP / B 50 XRP (faucet top-up first if balance short); 3 seeded borrower 10 XRP -> auto; 4 same borrower 60 XRP -> held -> `POST /approve`; 5 a FRESH faucet account (seed in memory only, never written) declaring 30 XRP debt asks 10 XRP -> refused `score_too_low`; 6 `pay_installment(loan3)`; 7 wait until `now >= loan4.nextPaymentDue + GRACE_PERIOD + 5`, then `POST /v1/loans/{loan4}/manage {"action":"default"}`, then assert `GET /v1/loans` shows loan 4 `defaulted`. Prints `step N OK <hash>`; exit 0 iff 7/7.

demo.py `--income <xrp>` (§9): first line tells the operator to start `sweeper.py` and wait for
its `watching` line; refuses (exit 2, `start the sweeper first: .venv/bin/python sweeper.py`) unless
`data/sweeper_state.json` has a cursor for the current borrower and a sweeper process holds its lock; then ONE Payment
with an invoice memo from the `customer` role (faucet-created once, never the faucet or the borrower's creator) to the
borrower, prints `income <hash> <engineResult> ...`, polls `GET /v1/loans` up to 60 s and prints
`sweep LoanPay <hash> <engineResult> ...` when the desk has verified it. Exit 0 iff the sweep status is `repaid`.

Open risk: deposits only until SubscriptionDate (4 h). If LoanSet is rejected while that window is open, report the engine result and shorten the window; names stay.

## 7. Borrower history + rotation (setup.py, LOCKED design)
- `setup.py` seeds the borrower with a 30-day revenue history: 5 "customer" accounts (faucet-funded, seeds in-memory only), ~24 Payments to the borrower with invoice memos (§4), varying amounts (1-5 XRP), dates spread over the last 30 days with some days skipped. Must land in the GOOD_SMALL buckets: activeDays 20-25, volume 55-80 XRP, 5 payers, top payer <= 35 %; setup prints `score(build_evidence(borrower, GOOD_SMALL["declared"]))` and exits non-zero if it is not 85. Write customer addresses + count + first/last hash into accounts.json `history`.
- `setup.py --rotate-borrower`: fresh borrower account (new BORROWER_SEED in .env), re-seed history, update accounts.json. demo.py runs it as a preflight when the current borrower has `activeLoans > 0` or `pastDefaults > 0`, so every scripted run starts from the same evidence (a defaulted loan from the last run must not sink step 3).
- M3 smoke loan (`smoke_loan.py`) uses its own fresh faucet account (in-memory seed), never the demo borrower.

## 8. Working capital (design C — LOCKED by the spike, see EVIDENCE.md "Batch spike")
rippled rejects LoanSet (and VaultDeposit) as a Batch inner tx at preflight (`temINVALID_INNER_BATCH`). So a working-capital
draw is TWO borrower-signed blobs submitted in order by the desk: the co-signed LoanSet first, then a borrower-only
`Batch` (flag `tfAllOrNothing` 0x10000) whose two inner Payments move the loan proceeds on.

**Borrower side** (`lending/batch/working_capital.py`, used by borrower.py):
```python
build_working_capital_batch(w_borrower, loan_terms: dict, supplier: str, amount_drops: str, fee_drops: str,
                            invoice: str, broker: str) -> dict
# loan_terms = {"loanBrokerId","principalDrops","termSeconds","interestRate"}; returns
# {"signedLoanSet": HEX, "signedBatch": HEX, "loanSetSequence": N, "batchHash": H, "innerHashes": [h_supplier, h_fee]}
```
- LoanSet = `common.build_loan_set(...)`, Sequence N, Fee "30", LastLedgerSequence L = current + 60, signed by the borrower.
- Batch: Account=borrower, Sequence N+1, LastLedgerSequence L, Flags tfAllOrNothing, RawTransactions =
  [Payment borrower->supplier `amount_drops` + invoice memo (setup.invoice_memo), Payment borrower->broker `fee_drops`],
  inner Sequences N+2, N+3, inner Fee "0", SigningPubKey "", tfInnerBatchTxn; outer Fee from `autofill(..., signers_count=0)`.
  No BatchSigners (every inner is the borrower's). Signed by the borrower.
```python
verify_working_capital_batch(batch_blob: str, loan_blob: str, body: dict, accounts: dict) -> str | None
# None if OK, else "batch_mismatch:<what>" (not Batch | flags | account | sequence | inner count | destination | amount | memo | unsigned
#   | bad_signature: the outer TxnSignature must be Account's key over encode_for_signing(tx), same check as the LoanSet)
unfold_batch(batch_hash: str) -> dict   # GET /v1/batches/{hash} body, see below
```
**Desk ("the field on the request")** — no new POST route. `POST /v1/loan-requests` takes two OPTIONAL fields:
`"disbursement": {"supplier": "r...", "supplierDrops": "55000000", "feeDrops": "1000000", "invoice": "INV-..."}` and
`"signedBatch": "HEX"` (both or neither; one without the other -> 400 `batch_mismatch:missing`). Order: pydantic -> 422 term
-> 400 `blob_mismatch:*` (verify_loan_set_blob) -> 400 `batch_mismatch:*` -> 409 vault_in_subscription -> 503 ledger ->
**refuse `batch_unfunded` if supplierDrops + feeDrops > principalDrops (the policy layer: recorded decision, no tx)** ->
`policy.decide` exactly as §5. auto (or approve on a held record): `cosign_loan_set` -> if tesSUCCESS submit the stored
batch blob -> `unfold_batch`. LoanSet fails -> `failed`, batch never submitted. LoanSet ok but batch not tesSUCCESS ->
`failed`, reason `batch:<engine>`, loanId kept (the loan exists; the record says so).
Record = §5 record + `"kind": "working_capital"` and
```json
"batch": {"supplier": "r...", "supplierDrops": "55000000", "feeDrops": "1000000", "invoice": "INV-...",
          "hash": "H|null", "engineResult": "tesSUCCESS|null", "legs": [leg, leg] | []}
```
Plain loan records get `"kind": "loan"` (UI treats a missing kind as loan). Working-capital records are listed in
`GET /v1/loan-requests` with the rest; approve/deny use the same §5 routes. `signedBatch` is never echoed (private key
`_signedBatch`, dropped when the request finishes, same as `_signedLoanSet`).
`GET /v1/batches/{hash}` -> `{"hash","validated","engineResult","account","flags","legs":[{"index": 0, "type": "Payment",
"account","destination","amountDrops","hash","result": "tesSUCCESS|...|not_applied"}]}`; an inner hash the ledger
does not know = `not_applied` (all-or-nothing rolled it back). 404 when the outer hash is unknown.
desk_examples.jsonl gets the real bodies of the working-capital POST /v1/loan-requests (held, then approve; refused batch_unfunded) and GET /v1/batches/{hash}.

**Demo** (9 steps): step 8 = the seeded borrower draws 60 XRP working capital, 55 XRP to a supplier with an invoice memo +
1 XRP fee to the broker -> held (over auto cap) -> `POST /approve` -> LoanSet hash + one Batch hash with both legs tesSUCCESS.
Step 9 = failure drill, policy layer first, then the on-ledger proof as the headline:
(a) policy: the same request shape with supplierDrops 70 XRP against 60 XRP principal -> desk refuses `batch_unfunded`, no tx.
(b) ledger: a raw borrower-signed Batch (tfAllOrNothing) whose supplier leg exceeds the borrower's balance, plus the fee leg.
Read the validated balances of borrower, supplier and broker before and after, and print each one. Print supplier and broker
`unchanged`. Print borrower `unchanged apart from the <Fee>-drop Batch network fee`: the delta must equal the outer Fee exactly.
Also print the outer hash + engine result and that no inner applied (both inner hashes `not_applied`). Never print "vault unchanged".
Steps 8-9 must run BEFORE loan 4 is defaulted (a past default caps the borrower score at <= 35): run them inside step 7's
grace-period wait and print them as steps 8 and 9. Exit 0 iff 9/9.

## 9. Auto-repay sweeps
The borrower's `sweeper.py` (borrower key only, never the broker key) pays an installment from x402 income and
reports it. Trigger = money, not a memo: the sweeper keeps `unspentIncomeDrops` in `data/sweeper_state.json` (with the
`borrower` it belongs to; a rotation resets the state and pins the cursor at the tip), adds each new x402 income's
delivered drops once, pays a due loan only when `unspentIncomeDrops >= periodicPaymentDrops`, and subtracts what it
pays. One sweeper per state file: an exclusive `flock` on `data/sweeper_state.lock` for the process lifetime; a second
sweeper exits 3 `another sweeper holds the lock`. The floor check is `balance - installment - LoanPay fee >=
reserve + 2 XRP`. On every start, after its first sweep, it prints `sweeper: watching <borrower> from ledger N`.

`POST /v1/loans/{loanId}/sweeps` (no operator token; nothing in the body is trusted):
```json
{"incomeHash": "64 hex", "incomeDrops": "5000000", "payer": "r...", "loanId": "64 hex", "loanPayHash": "64 hex",
 "drops": "3333334", "engineResult": "tesSUCCESS", "ledgerIndex": 123 | null, "at": 1761300000}
```
Verification on devnet, before anything is stored: `loanId` in the body == the path; the Loan exists
(`ledger_entry`) and its `Borrower` is the borrower; `loanPayHash` is a validated `LoanPay` with `LoanID == loanId`,
`Account == Borrower`, `Amount == drops`, and on-ledger `TransactionResult == engineResult`; `incomeHash` is a validated
tesSUCCESS `Payment` from `payer` to the borrower, `delivered_amount == incomeDrops`, with an invoice/x402 memo
(`evidence._is_x402_income`), in a ledger no later than the LoanPay's (income `ledger_index` <= LoanPay `ledger_index`;
one income may back more than one sweep, so `incomeHash` need not be unique). Any mismatch -> 422 with the reason (`loan_id_mismatch`, `unknown_loan`,
`loan_pay_not_found`, `loan_pay_not_validated`, `not_loan_pay`, `wrong_loan_id`, `wrong_account`, `amount_mismatch`,
`engine_result_mismatch`, `income_not_found`, `income_not_validated`, `income_not_success`, `income_not_payment`,
`income_wrong_destination`, `income_payer_mismatch`, `income_amount_mismatch`, `income_no_x402_memo`,
`income_after_loan_pay`), nothing stored;
a ledger read failure -> 503. Stored record (`data/sweeps.json`, append-only, keyed by `loanPayHash` uppercased):
body fields + `"borrower"`, `"status": "repaid" | "failed: <engineResult>"`, `"ledgerIndex"` (from the ledger),
`"verifiedAt"`; `"at"` is the LoanPay's ledger close time (tx `date` + 946684800), never the body's `at`.
The re-check for a stored `loanPayHash` runs again under the write lock, so two racing POSTs store one record. A validated non-tesSUCCESS LoanPay verifies the same way and is stored as `failed: <code>` with 200, so
the sweeper stops retrying; the sweeper never re-pays it and the UI says "Automatic repayment failed: <code>", never
"repaid automatically". The sweeper POSTs only validated LoanPays (an unvalidated one can never verify) and retries
any non-2xx on its next sweep, so a duplicate `loanPayHash` answers 200 with the stored record (idempotent, no ledger
read; the stored record wins over the new body; under a different path loanId it is 422 `wrong_loan_id`). Audit `loan_swept`. `GET /v1/loans` carries each loan's `sweeps`; the UI's activity feed reads them from there.
Two x402 incomes in one sweep pay a loan at most once: each income's drops go into `unspentIncomeDrops`, so the
second income's money stays unspent and counts toward the next installment, while its hash is consumed and never
triggers a payment on its own later.
