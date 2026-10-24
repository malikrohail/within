#!/usr/bin/env bash
# Docker-free build of the patched app-xrp for Ledger Stax, then the app's own ragger
# functional tests in Speculos. Verified 2026-10-24 on a Linux build host (Debian 13, x86_64, no sudo).
# Everything lands under $WORK; nothing is installed system-wide.
#
#   ./build_local.sh            # build + run the lending vectors (golden run, then verify)
#   ./build_local.sh full       # also run the whole standalone suite (about 4 min)
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
APP="$HERE/app-xrp"
WORK=${WORK:-$HERE/.work}
API_LEVEL=${API_LEVEL:-27}   # the Speculos wheel ships stax-api-level-shared-24..27
mkdir -p "$WORK" && cd "$WORK"

# 0. The app source: LedgerHQ/app-xrp at 7b5185f with patch/app-xrp-lending-fields.diff applied.
#    app-xrp/ is gitignored in this folder, so a fresh checkout of the repo has to prepare it.
if [ ! -f "$APP/Makefile" ]; then
  git clone -q https://github.com/LedgerHQ/app-xrp.git "$APP"
  git -C "$APP" checkout -q 7b5185ff09b4b3d15df242b156a6aaadfc99f555
  git -C "$APP" apply "$HERE/patch/app-xrp-lending-fields.diff"
fi

# 1. Python venv with Speculos (bundles its ARM launcher), ragger and the test requirements.
[ -x venv/bin/python ] || python3 -m venv venv
venv/bin/pip install -q 'speculos==0.27.1' 'ragger[speculos,ledgerwallet]==1.47.4' pillow -r "$APP/tests/standalone/requirements.txt"
chmod +x venv/lib/python3*/site-packages/speculos/resources/launcher

# 2. Static qemu-arm (Debian trixie moved the static binaries into qemu-user).
if [ ! -x qemu/bin/qemu-arm-static ]; then
  mkdir -p qemu/bin && curl -sSL -o qemu/qemu-user.deb \
    https://deb.debian.org/debian/pool/main/q/qemu/qemu-user_10.0.13+ds-0+deb13u1_amd64.deb
  dpkg -x qemu/qemu-user.deb qemu/u && ln -sf "$WORK/qemu/u/usr/bin/qemu-arm" qemu/bin/qemu-arm-static
fi

# 3. Compilers: Arm GNU 13.3 (sysroot + binutils) and clang 18 (the SDK's CC), plus the
#    libtinfo5 the clang tarball links against, unpacked from Debian's package.
if [ ! -x toolchain/arm/bin/arm-none-eabi-gcc ]; then
  mkdir -p toolchain/arm && curl -sSL https://developer.arm.com/-/media/Files/downloads/gnu/13.3.rel1/binrel/arm-gnu-toolchain-13.3.rel1-x86_64-arm-none-eabi.tar.xz | tar -xJ -C toolchain/arm --strip-components=1
fi
if [ ! -x toolchain/llvm/bin/clang ]; then
  mkdir -p toolchain/llvm && curl -sSL https://github.com/llvm/llvm-project/releases/download/llvmorg-18.1.8/clang+llvm-18.1.8-x86_64-linux-gnu-ubuntu-18.04.tar.xz | tar -xJ -C toolchain/llvm --strip-components=1
  mkdir -p toolchain/shim && curl -sSL -o toolchain/shim/libtinfo5.deb https://deb.debian.org/debian/pool/main/n/ncurses/libtinfo5_6.4-4_amd64.deb
  dpkg -x toolchain/shim/libtinfo5.deb toolchain/shim/x
  mkdir -p toolchain/bin
  for f in toolchain/llvm/bin/*; do t=$(basename "$f"); printf '#!/bin/sh\nexport LD_LIBRARY_PATH=%s/toolchain/shim/x/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}\nexec %s/%s "$@"\n' "$WORK" "$WORK" "$f" > "toolchain/bin/$t"; chmod +x "toolchain/bin/$t"; done
fi

# 4. Ledger secure SDK at the API level Speculos emulates for Stax.
[ -d "sdk$API_LEVEL" ] || git clone -q --depth 1 -b "API_LEVEL_$API_LEVEL" https://github.com/LedgerHQ/ledger-secure-sdk.git "sdk$API_LEVEL"

# 5. Build. The two trailing make errors about app.apdu / ledgerblue are the device-loading
#    packaging and do not matter for Speculos; app.elf is complete before them.
export PATH="$WORK/qemu/bin:$WORK/venv/bin:$WORK/toolchain/bin:$WORK/toolchain/arm/bin:$PATH"
( cd "$APP" && rm -rf build bin debug && BOLOS_SDK="$WORK/sdk$API_LEVEL" TARGET=stax make -j"$(nproc)" >/dev/null 2>&1 || true )
ls -l "$APP/build/stax/bin/app.elf"

# 6. Ragger functional tests in Speculos: golden run writes tests/standalone/snapshots/stax/<vector>/*.png
cd "$APP"
python -m pytest tests/standalone --device stax --golden_run -k "loan or vault or broker or credential or delegate or permissioned or blind or mpt or batch or domain" -q -p no:cacheprovider
python -m pytest tests/standalone --device stax -k "loan or vault or broker" -q -p no:cacheprovider
[ "${1:-}" = full ] && python -m pytest tests/standalone --device stax -q -p no:cacheprovider
echo "snapshots: $(find tests/standalone/snapshots/stax -path '*3[0-9]-*' -name '*.png' | wc -l) png under tests/standalone/snapshots/stax/3x-*"
