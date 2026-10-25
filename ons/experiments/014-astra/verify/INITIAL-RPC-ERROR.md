# Public-node verifier runs

Fresh read-only RPC calls; no cache. Recorded 2026-10-25T00:30:54.736468+00:00. Codec xrpl-py 5.2.0.

## PASS

```sh
lending/.venv/bin/python -I ons/experiments/014-astra/verify/verify.py --approval 8AC151230EAF1AC6F9928CF3E5A5F25DF2DE6AC2454C76DD6136466987B7919C --loanset C9627B03199430510F43567C6A93A446116606AC4DA5FAE763BA8FAA6CDDDF13
```

```text
codec: {"xrpl-py": "5.2.0"}
requested_hashes: {"approval": "8AC151230EAF1AC6F9928CF3E5A5F25DF2DE6AC2454C76DD6136466987B7919C", "loanset": "C9627B03199430510F43567C6A93A446116606AC4DA5FAE763BA8FAA6CDDDF13"}
rpc_request: {"method": "tx", "params": [{"api_version": 2, "binary": false, "transaction": "8AC151230EAF1AC6F9928CF3E5A5F25DF2DE6AC2454C76DD6136466987B7919C"}], "url": "https://s.altnet.rippletest.net:51234/"}
BINDING ERROR: RPC transport/JSON error: HTTPError
exit_code: 1
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
observed_approval: {"Account": "rUGeRsKjpnDVAi1uJYhAxWXbETC917VQ6B", "Amount": null, "Delegate": null, "Destination": "rUPNkALm4H4xefrVziYPxPARi1t6knrm7m", "SigningPubKey": "0250B6474EA8B26A489AB33E256EA546B94FF951C107CCF6C4E7BB31397BF93FF3"}
observed_loan: {"Account": "ra7Zr8ddy9tB88RaXL8B87YkqhEJG2vkAJ", "Counterparty": "rfWhYXgxaxmoaUcsNTnvHSqmFFWckQgyas", "LoanBrokerID": "073BFA96F424136CC87C17D31DA4A3FEACC8EC392011102AAFAD9CAE1A7BC74C", "SigningPubKey": "038368B6F1151E0CD559126AE13910B8B8D790652EB5CC0B5019A63D2E60792961"}
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
