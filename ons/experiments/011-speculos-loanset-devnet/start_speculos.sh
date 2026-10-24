#!/bin/bash
# Starts the patched app-xrp (Stax, API level 27) in Speculos 0.27.1, headless, REST on :5001, APDU on :9998.
S=${SCRATCH:?set SCRATCH to the folder holding venv/ (speculos 0.27.1) and qemu/bin/qemu-arm-static, see ../005-app-xrp-patch/build_local.sh}
export PATH="$S/qemu/bin:$S/venv/bin:$PATH"
ELF="$(cd "$(dirname "$0")/.." && pwd)/005-app-xrp-patch/app-xrp-2.8.2-lending-stax-api27.elf"
exec speculos --model stax --display headless --api-port 5001 --apdu-port 9998 "$ELF"
