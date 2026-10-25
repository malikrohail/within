# Public-node verifier runs

Fresh read-only RPC calls; no cache. Recorded 2026-10-25T00:35:49.360796+00:00. Codec xrpl-py 5.2.0. CLI SHA256 `98854fd33daf6d11f36e54eb70fb6f0e60bce83b55bb862f65fd10a0edafc9f2`. Earlier attempts hit intermittent HTTP errors; initial output is retained in INITIAL-RPC-ERROR.md. These are fresh calls, not cached substitution.

## PASS

```sh
lending/.venv/bin/python -I ons/experiments/014-astra/verify/verify.py --approval 8AC151230EAF1AC6F9928CF3E5A5F25DF2DE6AC2454C76DD6136466987B7919C --loanset C9627B03199430510F43567C6A93A446116606AC4DA5FAE763BA8FAA6CDDDF13
```

```text
codec: {"xrpl-py": "5.2.0"}
requested_hashes: {"approval": "8AC151230EAF1AC6F9928CF3E5A5F25DF2DE6AC2454C76DD6136466987B7919C", "loanset": "C9627B03199430510F43567C6A93A446116606AC4DA5FAE763BA8FAA6CDDDF13"}
rpc_request: {"method": "tx", "params": [{"api_version": 2, "binary": false, "transaction": "8AC151230EAF1AC6F9928CF3E5A5F25DF2DE6AC2454C76DD6136466987B7919C"}], "url": "https://s.altnet.rippletest.net:51234/"}
rpc_request: {"method": "tx", "params": [{"api_version": 2, "binary": false, "transaction": "C9627B03199430510F43567C6A93A446116606AC4DA5FAE763BA8FAA6CDDDF13"}], "url": "https://s.devnet.rippletest.net:51234/"}
approval_checks: {"hash_matches_request": true, "tesSUCCESS": true, "transaction_type": true, "validated": true}
approval_ledger: 21797373
loanset_checks: {"hash_matches_request": true, "tesSUCCESS": true, "transaction_type": true, "validated": true}
loanset_ledger: 6389232
observed_approval: {"Account": "rUGeRsKjpnDVAi1uJYhAxWXbETC917VQ6B", "Amount_drops": "1", "Delegate": null, "Destination": "rUPNkALm4H4xefrVziYPxPARi1t6knrm7m", "SigningPubKey": "0250B6474EA8B26A489AB33E256EA546B94FF951C107CCF6C4E7BB31397BF93FF3"}
observed_loan: {"Account": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG", "Counterparty": "rEH59tesggzmgg42PeHvByQQ3kmUNhegVw", "LoanBrokerID": "F2DD425BB210EC95BEB8BC66F239CB761373B4817AECFF0C3127A1C68EA91368", "SigningPubKey": "ED4ECC320BDDC282D42094B81B3D41EFA309B3D06813C8795352B752338D6FBEE2"}
observed_approval_amount_drops: "1"
memo_loan_approval_hex: "70C795FCADB20C0FE1EC53F722817476B2738853C7F448E3254C5205F616E646"
memo_loan_terms_utf8: "approve loan 30 XRP to rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG 6 payments"
removed_fields: {"node_fields_allowlist": ["api_version", "close_time_iso", "ctid", "date", "hash", "inLedger", "ledger_current_index", "ledger_hash", "ledger_index", "meta", "status", "tx_json", "validated", "warnings"], "transaction_field": "CounterpartySignature"}
borrower_encoded_field_names: ["Account", "Counterparty", "Fee", "GracePeriod", "InterestRate", "LastLedgerSequence", "LoanBrokerID", "PaymentInterval", "PaymentTotal", "PrincipalRequested", "Sequence", "SigningPubKey", "TransactionType", "TxnSignature"]
canonical_borrower_blob_bytes: 240
canonical_borrower_blob_sha256: "70C795FCADB20C0FE1EC53F722817476B2738853C7F448E3254C5205F616E646"
terms_inputs: {"Account": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG", "PaymentTotal": 6, "PrincipalRequested_drops": "30000000", "asset_assumption": "XRP vault", "principal_XRP": "30"}
derived_loan_terms: "approve loan 30 XRP to rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG 6 payments"
binding_checks: {"digest_match": true, "terms_match": true}
authorization: "NOT VERIFIED: observed accounts are not pinned; public binding is not hardware/human/desk attestation"
BINDING PASS
exit_code: 0
```

## NEGATIVE

```sh
lending/.venv/bin/python -I ons/experiments/014-astra/verify/verify.py --approval 8AC151230EAF1AC6F9928CF3E5A5F25DF2DE6AC2454C76DD6136466987B7919C --loanset 0CE7AFEF47E0F092CFABBEB78DAD6848B1BE8E5338C5BFB9CCC0804A49B16243
```

```text
codec: {"xrpl-py": "5.2.0"}
requested_hashes: {"approval": "8AC151230EAF1AC6F9928CF3E5A5F25DF2DE6AC2454C76DD6136466987B7919C", "loanset": "0CE7AFEF47E0F092CFABBEB78DAD6848B1BE8E5338C5BFB9CCC0804A49B16243"}
rpc_request: {"method": "tx", "params": [{"api_version": 2, "binary": false, "transaction": "8AC151230EAF1AC6F9928CF3E5A5F25DF2DE6AC2454C76DD6136466987B7919C"}], "url": "https://s.altnet.rippletest.net:51234/"}
rpc_request: {"method": "tx", "params": [{"api_version": 2, "binary": false, "transaction": "0CE7AFEF47E0F092CFABBEB78DAD6848B1BE8E5338C5BFB9CCC0804A49B16243"}], "url": "https://s.devnet.rippletest.net:51234/"}
approval_checks: {"hash_matches_request": true, "tesSUCCESS": true, "transaction_type": true, "validated": true}
approval_ledger: 21797373
loanset_checks: {"hash_matches_request": true, "tesSUCCESS": true, "transaction_type": true, "validated": true}
loanset_ledger: 6389970
observed_approval: {"Account": "rUGeRsKjpnDVAi1uJYhAxWXbETC917VQ6B", "Amount_drops": "1", "Delegate": null, "Destination": "rUPNkALm4H4xefrVziYPxPARi1t6knrm7m", "SigningPubKey": "0250B6474EA8B26A489AB33E256EA546B94FF951C107CCF6C4E7BB31397BF93FF3"}
observed_loan: {"Account": "ra7Zr8ddy9tB88RaXL8B87YkqhEJG2vkAJ", "Counterparty": "rfWhYXgxaxmoaUcsNTnvHSqmFFWckQgyas", "LoanBrokerID": "073BFA96F424136CC87C17D31DA4A3FEACC8EC392011102AAFAD9CAE1A7BC74C", "SigningPubKey": "038368B6F1151E0CD559126AE13910B8B8D790652EB5CC0B5019A63D2E60792961"}
observed_approval_amount_drops: "1"
memo_loan_approval_hex: "70C795FCADB20C0FE1EC53F722817476B2738853C7F448E3254C5205F616E646"
memo_loan_terms_utf8: "approve loan 30 XRP to rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG 6 payments"
removed_fields: {"node_fields_allowlist": ["api_version", "close_time_iso", "ctid", "date", "hash", "inLedger", "ledger_current_index", "ledger_hash", "ledger_index", "meta", "status", "tx_json", "validated", "warnings"], "transaction_field": "CounterpartySignature"}
borrower_encoded_field_names: ["Account", "ClosePaymentFee", "Counterparty", "Fee", "GracePeriod", "InterestRate", "LastLedgerSequence", "LoanBrokerID", "LoanOriginationFee", "LoanServiceFee", "PaymentInterval", "PaymentTotal", "PrincipalRequested", "Sequence", "SigningPubKey", "TransactionType", "TxnSignature"]
canonical_borrower_blob_bytes: 285
canonical_borrower_blob_sha256: "C8687A3CB2C87E62B8373E7328313BBAE05491D40A9017DD7231CB279C69A78A"
terms_inputs: {"Account": "ra7Zr8ddy9tB88RaXL8B87YkqhEJG2vkAJ", "PaymentTotal": 3, "PrincipalRequested_drops": "10000000", "asset_assumption": "XRP vault", "principal_XRP": "10"}
derived_loan_terms: "approve loan 10 XRP to ra7Zr8ddy9tB88RaXL8B87YkqhEJG2vkAJ 3 payments"
binding_checks: {"digest_match": false, "terms_match": false}
authorization: "NOT VERIFIED: observed accounts are not pinned; public binding is not hardware/human/desk attestation"
BINDING FAIL: digest_match, terms_match
exit_code: 1
```

## Optional browser page — blocked by public-node CORS

The xrpl.js 5.3.0 UMD bundle loaded in isolated Chromium: encode=function, decode=function, LoanSet type encodes to120050. `verify.html` is an experimental direct-public-node implementation, **not a demonstrated live browser verifier**. Both attempts returned BINDING ERROR: Failed to fetch. Browser diagnostic:

```text
Origin null blocked by CORS: preflight response has no Access-Control-Allow-Origin.
https://s.altnet.rippletest.net:51234/ net::ERR_FAILED
BINDING ERROR: Failed to fetch
```

Read-only HTTP checks confirmed neither application/json nor text/plain responses supplied Access-Control-Allow-Origin in this environment, although the node returned validated data to Python. No proxy, CORS bypass, disabled browser protections or stage server was introduced. BROWSER-RESULT.json retains both browser ERROR outputs. Use the passing Python CLI for judging and recording; browser publishing is not a substitute for a CORS-compatible RPC service.
