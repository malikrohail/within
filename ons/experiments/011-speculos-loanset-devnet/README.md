# 011 - The patched XRP app in Speculos shows the lending fields and signs a LoanSet and a LoanPay that validate on devnet

Written 2026-10-24 (evening EDT) on a Linux build host. Follows experiment 005 (the app-xrp patch) and answers
Ledger's "if it runs and looks good on Speculos" with two public devnet hashes instead of screenshots alone.

## What it proves

The patched XRP app (`../005-app-xrp-patch/app-xrp-2.8.2-lending-stax-api27.elf`, Stax, API level 27) running in
Speculos 0.27.1 reviews an XLS-66 `LoanSet` field by field, signs it as the borrower (`Account`), and that transaction,
after the broker adds its `CounterpartySignature` with a software key, validates `tesSUCCESS` on XRPL devnet. The
device then signs a `LoanPay` on its own and that validates too. See `RESULT.md` for the hashes and the honest list.

## Files

| Path | What |
|---|---|
| `run.py` | the whole run: device public key over APDU, fresh close-ended vault + loan broker (software keys from `../.secrets/001.json`), LoanSet built with xrpl-py 5.2.0, serialized bytes sent to the app (chunked SIGN APDUs, the app adds the `STX\0` prefix), review pages driven and screenshotted over the Speculos REST API, DER signature put into `TxnSignature`, broker counter-signs, submit, then LoanPay signed by the device alone |
| `start_speculos.sh` | starts the patched app headless on REST :5001 / APDU :9998 (needs the scratch toolchain from `../005-app-xrp-patch/build_local.sh`) |
| `run-log.json` | every step's result, hash, explorer link, the device account and public key, the device-signed LoanSet tx_json before the counterparty signature |
| `logs/01-run.log` | raw stdout of the run (force-added, the root `.gitignore` ignores `*.log`) |
| `screens/` | one PNG per review page: `loan-set-01..06` (home, 2 of 5, 3 of 5, 4 of 5, Hold to sign, Transaction signed), `loan-pay-01..05` |
| `screens/stax-loanset-loanpay.gif` | the nine review and result pages above as a captioned 2.2 s-per-frame GIF (built from the PNGs with Pillow, no re-run) |
| `RESULT.md` | outcome, verification from the public node, what was not proven |

## How to run again

```bash
SCRATCH=<folder with venv/ and qemu/bin/>  ./ons/experiments/011-speculos-loanset-devnet/start_speculos.sh &   # patched app on :5001
$SCRATCH/venv/bin/python ons/experiments/011-speculos-loanset-devnet/run.py                                   # ~3 min, mostly the 60 s subscription window
```

Devnet only. The device account is the Speculos default seed at `44'/144'/0'/0/0` (`ra7Zr8ddy9tB88RaXL8B87YkqhEJG2vkAJ`),
funded by the devnet faucet. The depositor and broker seeds are read from `../.secrets/001.json` and never printed.

Create ons/experiments/.secrets/001.json yourself with funded devnet depositor and broker seeds (the keys run.py reads are `depositor` and `broker`); it is gitignored and not part of this repository.
