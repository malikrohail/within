#!/usr/bin/env python3
"""Generate XRPL 3.x test vectors (.json + .raw) for the app-xrp parser.

Usage: .venv/bin/python make_vectors.py app-xrp/tests/standalone/testcases

Writes one folder per transaction type, in the repo's existing style:
  <NN>-<slug>/<MM>-<name>.json   human-readable tx (OWN_ADDR / OWN_PUBKEY
                                  placeholders, like the existing vectors)
  <NN>-<slug>/<MM>-<name>.raw    xrpl-py binary encoding, i.e. what the host
                                  sends in the INS_SIGN APDU (no "STX\\0"
                                  prefix: the app adds it)
and three blind-sign vectors under blind-sign/.

The identity is the one every existing vector in app-xrp uses (Speculos
default seed, path 44'/144'/0'/0/0):
  rTooLkitCksh5mQa67eaa2JaWHDBnHkpy / 02B79D...9E67
Needs xrpl-py >= 5.2 (ships the XLS-65/66 definitions).
"""
import json
import sys
from pathlib import Path

from xrpl.core.binarycodec import encode

OWN_ADDR = "rTooLkitCksh5mQa67eaa2JaWHDBnHkpy"
OWN_PUBKEY = "02B79DA34F4551CA976B66AA78A55C43707EC2BB2BEC39F95BD53F24E2E45A9E67"
OTHER = "rPT1Sjq2YGrBMTttX4GZHjKu9dyfzbpAYe"  # borrower / destination
ISSUER = "rhub8VRN55s94qWKDv6jmDy1pUykJzF3wq"  # IOU issuer
H = lambda n: (f"{n:02X}" * 32)  # 32-byte id placeholder, e.g. H(0xA1)
MPT_ID = "000000F0" + "5E7C" * 10  # 4-byte sequence + 20-byte issuer
COMMON = {"Fee": "12", "Sequence": 7, "LastLedgerSequence": 6400000,
          "SigningPubKey": OWN_PUBKEY}

RIPPLE_EPOCH_2026_11_01 = 846806400  # 2026-11-01 00:00:00 UTC
RIPPLE_EPOCH_2026_12_01 = 849398400  # 2026-12-01 00:00:00 UTC


def tx(d):
    out = {"Account": OWN_ADDR, **COMMON, **d}
    return out


VECTORS = {
    "30-credential-create": {
        "01-basic": tx({
            "TransactionType": "CredentialCreate",
            "Subject": OTHER,
            "CredentialType": "4B5943",  # "KYC"
            "Expiration": RIPPLE_EPOCH_2026_12_01,
            "URI": "68747470733a2f2f6465736b2e6578616d706c652f6b7963",
        }),
    },
    "31-delegate-set": {
        "01-payment-trustset-granular": tx({
            "TransactionType": "DelegateSet",
            "Authorize": OTHER,
            "Permissions": [
                {"Permission": {"PermissionValue": "Payment"}},
                {"Permission": {"PermissionValue": "TrustSet"}},
                {"Permission": {"PermissionValue": "TrustlineAuthorize"}},
            ],
        }),
    },
    "32-vault-create": {
        "01-closed-ended-private": tx({
            "TransactionType": "VaultCreate",
            "Asset": {"currency": "XRP"},
            "AssetsMaximum": "1000000000",
            "WithdrawalPolicy": 1,
            "VaultKind": 1,
            "Scale": 6,
            "SubscriptionDate": RIPPLE_EPOCH_2026_11_01,
            "RedemptionDate": RIPPLE_EPOCH_2026_12_01,
            "DomainID": H(0xD0),
            "Data": "6167656e742d63617368207661756c74",  # "agent-cash vault"
            "Flags": 0x00010000,  # tfVaultPrivate
        }),
        "02-iou-asset": tx({
            "TransactionType": "VaultCreate",
            "Asset": {"currency": "USD", "issuer": ISSUER},
            "AssetsMaximum": "0",
            "WithdrawalPolicy": 1,
        }),
        "03-mpt-asset": tx({
            "TransactionType": "VaultCreate",
            "Asset": {"mpt_issuance_id": MPT_ID},
        }),
    },
    "33-vault-deposit": {
        "01-xrp": tx({
            "TransactionType": "VaultDeposit",
            "VaultID": H(0xA1),
            "Amount": "100000000",
        }),
        "02-iou": tx({
            "TransactionType": "VaultDeposit",
            "VaultID": H(0xA1),
            "Amount": {"currency": "USD", "issuer": ISSUER, "value": "2500.5"},
        }),
        "03-mpt": tx({
            "TransactionType": "VaultDeposit",
            "VaultID": H(0xA1),
            "Amount": {"mpt_issuance_id": MPT_ID, "value": "1000000"},
        }),
    },
    "34-vault-withdraw": {
        "01-destination-credentials": tx({
            "TransactionType": "VaultWithdraw",
            "VaultID": H(0xA1),
            "Amount": "50000000",
            "Destination": OTHER,
            "DestinationTag": 42,
            "CredentialIDs": [H(0xC1), H(0xC2)],
        }),
    },
    "35-loan-broker-set": {
        "01-basic": tx({
            "TransactionType": "LoanBrokerSet",
            "VaultID": H(0xA1),
            "ManagementFeeRate": 1000,  # 1 %
            "DebtMaximum": "0",
            "CoverRateMinimum": 10000,  # 10 %
            "CoverRateLiquidation": 50000,  # 50 %
            "Data": "6465736b2d62726f6b6572",  # "desk-broker"
        }),
    },
    "36-loan-set": {
        "01-first-signer": tx({
            "TransactionType": "LoanSet",
            "LoanBrokerID": H(0xB2),
            "Counterparty": OTHER,
            "PrincipalRequested": "100000000",
            "InterestRate": 500,  # 0.5 %
            "PaymentTotal": 12,
            "PaymentInterval": 2592000,
            "GracePeriod": 604800,
            "LoanOriginationFee": "100",
            "LoanServiceFee": "10",
            "Data": "6c725f30303136",  # "lr_0016"
        }),
        "02-all-fields": tx({
            "TransactionType": "LoanSet",
            "LoanBrokerID": H(0xB2),
            "Counterparty": OTHER,
            "PrincipalRequested": "2500.5",
            "InterestRate": 1250,
            "LateInterestRate": 2000,
            "CloseInterestRate": 300,
            "OverpaymentInterestRate": 100,
            "OverpaymentFee": 50,
            "PaymentTotal": 3,
            "PaymentInterval": 60,
            "GracePeriod": 60,
            "LoanOriginationFee": "1",
            "LoanServiceFee": "0.25",
            "LatePaymentFee": "5",
            "ClosePaymentFee": "2",
        }),
        "03-countersigned": tx({
            "TransactionType": "LoanSet",
            "LoanBrokerID": H(0xB2),
            "Counterparty": OTHER,
            "PrincipalRequested": "100000000",
            "InterestRate": 500,
            "PaymentTotal": 12,
            "PaymentInterval": 2592000,
            "GracePeriod": 604800,
            "TxnSignature": "30440220" + "11" * 32 + "0220" + "22" * 32,
            "CounterpartySignature": {
                "SigningPubKey": "ED" + "33" * 32,
                "TxnSignature": "44" * 64,
            },
        }),
    },
    "37-loan-pay": {
        "01-installment": tx({
            "TransactionType": "LoanPay",
            "LoanID": H(0xC3),
            "Amount": "9000000",
        }),
        "02-full-payment": tx({
            "TransactionType": "LoanPay",
            "LoanID": H(0xC3),
            "Amount": "95000000",
            "Flags": 0x00020000,  # tfLoanFullPayment
        }),
    },
    "38-loan-manage": {
        "01-default": tx({
            "TransactionType": "LoanManage",
            "LoanID": H(0xC3),
            "Flags": 0x00010000,  # tfLoanDefault
        }),
        "02-impair": tx({
            "TransactionType": "LoanManage",
            "LoanID": H(0xC3),
            "Flags": 0x00020000,  # tfLoanImpair
        }),
    },
}

# Must parse without error but end in the blind-signing flow.
BLIND = {
    "05-batch-two-payments": tx({
        "TransactionType": "Batch",
        "Flags": 0x00010000,  # tfAllOrNothing
        "RawTransactions": [
            {"RawTransaction": {
                "TransactionType": "Payment", "Account": OWN_ADDR,
                "Destination": OTHER, "Amount": "1000000", "Fee": "0",
                "Flags": 0x40000000, "Sequence": 8, "SigningPubKey": ""}},
            {"RawTransaction": {
                "TransactionType": "Payment", "Account": OWN_ADDR,
                "Destination": ISSUER, "Amount": "2000000", "Fee": "0",
                "Flags": 0x40000000, "Sequence": 9, "SigningPubKey": ""}},
        ],
    }),
    # A field whose data type (Hash160, 0x11) the parser has no reader for.
    # Before the patch this was the 0x680b path; now it blind-signs.
    "06-unknown-data-type": tx({
        "TransactionType": "Payment",
        "Destination": OTHER,
        "Amount": "1000000",
        "TakerPaysCurrency": "0000000000000000000000005553440000000000",
    }),
    # Named in general.c but deliberately not clear-signed.
    "07-mpt-issuance-create": tx({
        "TransactionType": "MPTokenIssuanceCreate",
        "AssetScale": 2,
        "MaximumAmount": "1000000000",
        "TransferFee": 100,
        "Flags": 0x00000020,  # tfMPTCanTransfer
    }),
}


def write(folder: Path, name: str, obj: dict):
    folder.mkdir(parents=True, exist_ok=True)
    raw = bytes.fromhex(encode(obj))
    (folder / f"{name}.raw").write_bytes(raw)
    shown = json.loads(json.dumps(obj).replace(OWN_ADDR, "OWN_ADDR")
                       .replace(OWN_PUBKEY, "OWN_PUBKEY"))
    (folder / f"{name}.json").write_text(json.dumps(shown, indent=2) + "\n")
    print(f"{folder.name}/{name}.raw  {len(raw)} bytes")


def main():
    root = Path(sys.argv[1])
    for folder, cases in VECTORS.items():
        for name, obj in cases.items():
            write(root / folder, name, obj)
    for name, obj in BLIND.items():
        write(root / "blind-sign", name, obj)


if __name__ == "__main__":
    main()
