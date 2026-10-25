"""Offline adversarial checks against committed public RPC fixtures; run with -I."""
import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
spec = importlib.util.spec_from_file_location('verifier', HERE / 'verify.py')
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)
A = '8AC151230EAF1AC6F9928CF3E5A5F25DF2DE6AC2454C76DD6136466987B7919C'
L = 'C9627B03199430510F43567C6A93A446116606AC4DA5FAE763BA8FAA6CDDDF13'


class VerifierTests(unittest.TestCase):
    def setUp(self):
        self.a = json.loads((ROOT / 'innovation/proof-of-concept/01-testnet-approval-payment.response.json').read_text())['result']
        self.l = json.loads((ROOT / 'innovation/proof-of-concept/02-devnet-loanset.response.json').read_text())['result']

    def run_pair(self):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            code = v.verify(self.a, self.l, A, L)
        return code, output.getvalue()

    def assert_error(self):
        with self.assertRaises(v.VerificationError), contextlib.redirect_stdout(io.StringIO()):
            v.verify(self.a, self.l, A, L)

    def test_positive_v1(self):
        self.assertEqual(self.run_pair()[0], 0)

    def test_positive_v2(self):
        def wrap(r):
            return {'tx_json': {k: x for k, x in r.items() if k not in v.NODE_FIELDS},
                    'hash': r['hash'], 'meta': r['meta'], 'validated': True, 'ledger_index': r['ledger_index']}
        self.a, self.l = wrap(self.a), wrap(self.l)
        self.a['tx_json']['DeliverMax'] = self.a['tx_json'].pop('Amount')
        self.assertEqual(self.run_pair()[0], 0)

    def test_unvalidated_and_tec(self):
        for value in (False, 'true', 1):
            with self.subTest(value=value):
                self.l['validated'] = value
                self.assert_error()
        self.l['validated'] = True
        self.l['meta']['TransactionResult'] = 'tecEXPIRED'
        self.assert_error()

    def test_wrong_hash_or_type(self):
        for key, val in [('hash', '0'*64), ('TransactionType', 'Payment')]:
            with self.subTest(key=key):
                old = self.l[key]; self.l[key] = val
                self.assert_error(); self.l[key] = old

    def test_missing_duplicate_and_bad_memos(self):
        original = copy.deepcopy(self.a['Memos'])
        for change in ('missing', 'duplicate', 'hex', 'utf8'):
            with self.subTest(change=change):
                self.a['Memos'] = copy.deepcopy(original)
                if change == 'missing': self.a['Memos'] = []
                elif change == 'duplicate': self.a['Memos'] += copy.deepcopy(original)
                elif change == 'hex': self.a['Memos'][0]['Memo']['MemoData'] = 'GG'
                else:
                    for row in self.a['Memos']:
                        if bytes.fromhex(row['Memo']['MemoType']) == b'loan-terms': row['Memo']['MemoData'] = 'FF'
                self.assert_error()

    def test_mismatch_digest_and_terms(self):
        for row in self.a['Memos']:
            name = bytes.fromhex(row['Memo']['MemoType'])
            if name == b'loan-approval': row['Memo']['MemoData'] = '00'*32
            elif name == b'loan-terms': row['Memo']['MemoData'] = b'wrong terms'.hex()
        code, output = self.run_pair()
        self.assertEqual(code, 1)
        self.assertIn('BINDING FAIL: digest_match, terms_match', output)

    def test_signatures_required_and_multisign_rejected(self):
        for key in ('CounterpartySignature', 'SigningPubKey', 'TxnSignature'):
            old = self.l.pop(key); self.assert_error(); self.l[key] = old
        self.l['Signers'] = []; self.assert_error()

    def test_unknown_field_not_silently_dropped(self):
        self.l['UnrecognizedFutureField'] = 42
        self.assert_error()

    def test_terms_decimal_exact(self):
        with contextlib.redirect_stdout(io.StringIO()):
            for raw, xrp in [('1000001', '1.000001'), ('15e10', '150000'), ('1234500', '1.2345')]:
                self.l['PrincipalRequested'] = raw
                self.assertIn('approve loan '+xrp+' XRP', v.derive_terms(self.l))
            for raw in ('NaN', 'Infinity', '-1', '0', '1.1', True, 'invalid'):
                self.l['PrincipalRequested'] = raw
                with self.assertRaises(v.VerificationError): v.derive_terms(self.l)

    def test_invalid_approval_amount(self):
        self.a['Amount'] = {'currency': 'USD', 'value': '1'}
        self.assert_error()

    def test_rpc_failure_is_error(self):
        with patch.object(v.urllib.request, 'urlopen', side_effect=TimeoutError), contextlib.redirect_stdout(io.StringIO()) as out:
            code = v.main(['--approval', A, '--loanset', L])
        self.assertEqual(code, 1)
        self.assertIn('BINDING ERROR:', out.getvalue())
        self.assertNotIn('BINDING FAIL:', out.getvalue())


if __name__ == '__main__':
    unittest.main(verbosity=2)
