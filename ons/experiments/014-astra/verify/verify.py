#!/usr/bin/env python3
"""Read-only public artifact binding verifier. Never signs or submits anything."""
import argparse
from decimal import Decimal, InvalidOperation
import hashlib
from importlib.metadata import version
import json
import re
import sys
import urllib.request
import urllib.error
from urllib.parse import urlsplit

CODEC_VERSION = '5.2.0'
TESTNET = 'https://s.altnet.rippletest.net:51234/'
DEVNET = 'https://s.devnet.rippletest.net:51234/'
NODE_FIELDS = frozenset(('hash', 'ledger_index', 'meta', 'validated', 'date', 'inLedger',
                         'ctid', 'ledger_hash', 'close_time_iso', 'status', 'tx_json',
                         'ledger_current_index', 'warnings', 'api_version'))


class VerificationError(Exception):
    """Unavailable or malformed evidence; not a demonstrated binding mismatch."""


def emit(label, value):
    print(f'{label}: {json.dumps(value, sort_keys=True, ensure_ascii=True)}')


def require(condition, reason):
    if not condition:
        raise VerificationError(reason)


def hash_arg(value):
    if not re.fullmatch(r'[0-9a-fA-F]{64}', value):
        raise argparse.ArgumentTypeError('transaction hash must be exactly 64 hex characters')
    return value.upper()


def endpoint(value):
    u = urlsplit(value)
    if u.scheme != 'https' or not u.hostname or u.username or u.password or u.query or u.fragment:
        raise argparse.ArgumentTypeError('RPC URL must be HTTPS without credentials, query or fragment')
    return value


def fetch_tx(url, tx_hash):
    # This is the only RPC method used. No stage imports, retries to other networks or cache.
    request = {'method': 'tx', 'params': [{'transaction': tx_hash, 'binary': False, 'api_version': 2}]}
    emit('rpc_request', {'url': url, **request})
    req = urllib.request.Request(url, json.dumps(request).encode(), {'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        raise VerificationError(f'RPC HTTP {exc.code}') from exc
    except Exception as exc:
        raise VerificationError(f'RPC transport/JSON error: {type(exc).__name__}') from exc
    require(isinstance(payload, dict) and isinstance(payload.get('result'), dict), 'RPC result object missing')
    result = payload['result']
    require(not result.get('error'), f'RPC error: {result.get("error")}')
    return result


def validate_tx(result, wanted_hash, wanted_type, label):
    require(isinstance(result, dict), f'{label}: result must be an object')
    meta = result.get('meta')
    require(isinstance(meta, dict), f'{label}: metadata object missing')
    tx = result.get('tx_json', result)
    require(isinstance(tx, dict), f'{label}: tx_json object missing')
    observed = result.get('hash', tx.get('hash'))
    checks = {'validated': result.get('validated') is True,
              'tesSUCCESS': meta.get('TransactionResult') == 'tesSUCCESS',
              'hash_matches_request': isinstance(observed, str) and observed.upper() == wanted_hash,
              'transaction_type': tx.get('TransactionType') == wanted_type}
    emit(label + '_checks', checks)
    emit(label + '_ledger', result.get('ledger_index'))
    require(all(checks.values()), f'{label}: transaction validation/type/hash check failed')
    if 'hash' in tx:
        require(isinstance(tx['hash'], str) and tx['hash'].upper() == wanted_hash,
                f'{label}: nested hash differs from request')
    return {k: v for k, v in tx.items() if k not in NODE_FIELDS}


def unhex(value, label):
    require(isinstance(value, str) and len(value) % 2 == 0 and re.fullmatch('[0-9A-Fa-f]*', value) is not None,
            f'{label}: malformed hex')
    return bytes.fromhex(value)


def memos(payment):
    rows = payment.get('Memos')
    require(isinstance(rows, list), 'approval: missing memos')
    found = {}
    for row in rows:
        require(isinstance(row, dict) and isinstance(row.get('Memo'), dict), 'approval: malformed memo object')
        memo = row['Memo']
        # Target types are compared as bytes; unrelated types need not be UTF-8.
        kind = unhex(memo.get('MemoType', ''), 'MemoType')
        if kind in (b'loan-approval', b'loan-terms'):
            require(kind not in found, f'approval: duplicate {kind.decode()} memo')
            found[kind] = unhex(memo.get('MemoData'), kind.decode())
    require(set(found) == {b'loan-approval', b'loan-terms'}, 'approval: missing required memo')
    require(len(found[b'loan-approval']) == 32, 'loan-approval: expected binary 32-byte SHA256 memo')
    try:
        terms = found[b'loan-terms'].decode('utf-8', errors='strict')
    except UnicodeError as exc:
        raise VerificationError('loan-terms: invalid UTF-8') from exc
    return found[b'loan-approval'].hex().upper(), terms


def derive_terms(loan):
    raw = loan.get('PrincipalRequested')
    require(isinstance(raw, (str, int)) and not isinstance(raw, bool), 'principal must be a decimal integer number of drops')
    try:
        drops = Decimal(raw)
    except InvalidOperation as exc:
        raise VerificationError('invalid principal') from exc
    require(drops.is_finite() and drops > 0 and drops == drops.to_integral_value() and drops <= Decimal('1e17'),
            'principal must be finite positive whole XRP drops within 1e17')
    # Integer divmod avoids Decimal context rounding and binary floating point.
    whole, frac = divmod(int(drops), 1_000_000)
    xrp = f'{whole}.{frac:06d}'.rstrip('0') if frac else str(whole)
    count = loan.get('PaymentTotal')
    require(type(count) is int and 0 < count <= 0xFFFFFFFF, 'invalid PaymentTotal')
    account = loan.get('Account')
    require(isinstance(account, str) and bool(account), 'missing borrower Account')
    emit('terms_inputs', {'PrincipalRequested_drops': str(raw), 'principal_XRP': xrp,
                          'Account': account, 'PaymentTotal': count, 'asset_assumption': 'XRP vault'})
    return f'approve loan {xrp} XRP to {account} {count} payments'


def verify(approval_result, loan_result, approval_hash, loan_hash):
    from xrpl.core.binarycodec import encode, decode
    payment = validate_tx(approval_result, approval_hash, 'Payment', 'approval')
    loan = validate_tx(loan_result, loan_hash, 'LoanSet', 'loanset')
    emit('observed_approval', {**{k: payment.get(k) for k in ('Account', 'SigningPubKey', 'Destination', 'Delegate')},
                               'Amount_drops': payment.get('Amount', payment.get('DeliverMax'))})
    emit('observed_loan', {k: loan.get(k) for k in ('Account', 'Counterparty', 'LoanBrokerID', 'SigningPubKey')})
    amount = payment.get('Amount', payment.get('DeliverMax'))
    emit('observed_approval_amount_drops', amount)
    require(isinstance(amount, str) and re.fullmatch(r'[0-9]+', amount) is not None and 0 < int(amount) <= 10**17,
            'approval: expected positive native XRP drop amount')
    require('Signers' not in loan, 'multisigned borrower unsupported')
    for key in ('SigningPubKey', 'TxnSignature'):
        require(bool(unhex(loan.get(key), 'borrower ' + key)), 'missing borrower ' + key)
    require(isinstance(loan.get('CounterpartySignature'), dict) and bool(loan['CounterpartySignature']),
            'LoanSet must have CounterpartySignature')
    for key in ('SigningPubKey', 'TxnSignature'):
        require(bool(unhex(loan['CounterpartySignature'].get(key), 'counterparty ' + key)), 'missing counterparty ' + key)
    memo_digest, memo_terms = memos(payment)
    emit('memo_loan_approval_hex', memo_digest)
    emit('memo_loan_terms_utf8', memo_terms)
    borrower = {k: v for k, v in loan.items() if k != 'CounterpartySignature'}
    emit('removed_fields', {'node_fields_allowlist': sorted(NODE_FIELDS), 'transaction_field': 'CounterpartySignature'})
    emit('borrower_encoded_field_names', sorted(borrower))
    try:
        blob = encode(borrower)
        decoded = decode(blob)
        require(set(decoded) == set(borrower), 'codec omitted a transaction field; unsupported schema')
    except VerificationError:
        raise
    except Exception as exc:
        raise VerificationError(f'canonical codec error: {type(exc).__name__}') from exc
    digest = hashlib.sha256(bytes.fromhex(blob)).hexdigest().upper()
    emit('canonical_borrower_blob_bytes', len(blob) // 2)
    emit('canonical_borrower_blob_sha256', digest)
    derived = derive_terms(decoded)
    emit('derived_loan_terms', derived)
    checks = {'digest_match': digest == memo_digest, 'terms_match': derived == memo_terms}
    emit('binding_checks', checks)
    emit('authorization', 'NOT VERIFIED: observed accounts are not pinned; public binding is not hardware/human/desk attestation')
    if all(checks.values()):
        print('BINDING PASS')
        return 0
    reasons = [key for key, value in checks.items() if not value]
    print('BINDING FAIL: ' + ', '.join(reasons))
    return 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--approval', required=True, type=hash_arg)
    parser.add_argument('--loanset', required=True, type=hash_arg)
    parser.add_argument('--testnet-url', type=endpoint, default=TESTNET, help='public TESTNET HTTPS endpoint only; caller must verify network (never mainnet/local services)')
    parser.add_argument('--devnet-url', type=endpoint, default=DEVNET, help='public DEVNET HTTPS endpoint only; caller must verify network (never mainnet/local services)')
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 1
    try:
        installed = version('xrpl-py')
        require(installed == CODEC_VERSION, f'xrpl-py must be {CODEC_VERSION}, found {installed}')
        emit('codec', {'xrpl-py': installed})
        emit('requested_hashes', {'approval': args.approval, 'loanset': args.loanset})
        return verify(fetch_tx(args.testnet_url, args.approval), fetch_tx(args.devnet_url, args.loanset), args.approval, args.loanset)
    except Exception as exc:
        message = str(exc) if isinstance(exc, VerificationError) else type(exc).__name__
        print('BINDING ERROR: ' + message)
        return 1


if __name__ == '__main__':
    sys.exit(main())
