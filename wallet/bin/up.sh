#!/bin/sh
# Cold-boots the Policy Wallet stack and waits on each service: Speculos must already be up on :5000
# (see docs/RUNBOOK.md); then wallet :7402, merchants :8001/:8002, dashboard :5174. A service that is
# already healthy is left as it is. Prints one line per service and the wallet status; exits 1 on any failure.
. "$(dirname "$0")/lib.sh"
status=0
mkdir -p "$ROOT/wallet/data" "$ROOT/agent/logs"

# 127.0.0.1, not localhost: on macOS localhost:5000 is AirPlay and answers 403.
if wait_http "http://127.0.0.1:5000/events?currentscreenonly=true" 3; then
  ok speculos "up on 127.0.0.1:5000 (not managed here)"
else
  bad speculos "not answering on 127.0.0.1:5000: start the speculos-xrp container (docs/RUNBOOK.md), then rerun"
  exit 1
fi
[ -n "$(listener 5173)" ] && note workshop ":5173 is running: keep its browser tab closed or signing fails with 6901"

start() { # label port health-url dir log command...
  label=$1 port=$2 url=$3 dir=$4 log=$5
  shift 5
  if wait_http "$url" 1; then ok "$label" "already up on :$port"; return; fi
  if [ -n "$(listener "$port")" ]; then bad "$label" ":$port held by pid $(listener "$port") but not healthy: run wallet/bin/down.sh"; status=1; return; fi
  # exec: no shell stays behind holding this script's stdout.
  (cd "$dir" && exec nohup "$@" >> "$log" 2>&1 < /dev/null) &
  if wait_http "$url" 45; then ok "$label" "started on :$port (log $log)"; else bad "$label" "no answer on $url after 45 s (log $log)"; status=1; fi
}

start wallet 7402 http://127.0.0.1:7402/health "$ROOT/wallet" "$ROOT/wallet/data/server.log" sh scripts/run.sh
start good 8001 http://127.0.0.1:8001/health "$ROOT/agent" "$ROOT/agent/logs/good.log" .venv/bin/python -m merchants.good
start rogue 8002 http://127.0.0.1:8002/health "$ROOT/agent" "$ROOT/agent/logs/rogue.log" .venv/bin/python -m merchants.rogue
start dashboard 5174 http://localhost:5174/ "$ROOT/dashboard" "$ROOT/dashboard/dev.log" npm run dev

# The wallet answers /health before the device session is open; wait for it.
i=0
while [ "$i" -lt 30 ]; do
  curl -sf -m 2 http://127.0.0.1:7402/v1/status | grep -q '"deviceConnected":true' && break
  sleep 1
  i=$((i + 1))
done
summary=$(curl -sf -m 5 http://127.0.0.1:7402/v1/status | python3 -c '
import json, sys
s = json.load(sys.stdin)
xrp = lambda d: "%g XRP" % (int(d) / 1e6) if d is not None else "?"
device = "connected " + str(s.get("deviceApp")) if s["deviceConnected"] else "NOT CONNECTED"
print("connected" if s["deviceConnected"] else "disconnected")
print("hot %s %s · device %s %s · %s · spent today %s · pending %s" % (
    s["hotAccount"], xrp(s["hotBalanceDrops"]), s["deviceAccount"], xrp(s["deviceBalanceDrops"]),
    device, xrp(s["spentTodayDrops"]), s["pending"]))
' 2>/dev/null)
if [ "$(echo "$summary" | head -1)" = connected ]; then
  ok device "$(echo "$summary" | tail -1)"
else
  bad device "$(echo "${summary:-no answer from /v1/status}" | tail -1)"
  status=1
fi
merchants=$(curl -sf -m 10 http://127.0.0.1:7402/v1/merchants | python3 -c 'import json,sys; print(sum(1 for m in json.load(sys.stdin) if m["accepted"]))' 2>/dev/null)
domain=$(curl -sf -m 10 http://127.0.0.1:7402/v1/domain | python3 -c 'import json,sys; d=json.load(sys.stdin)["domain"]; print(d["domainId"][:8] + "…" if d else "none")' 2>/dev/null)
if [ "${merchants:-0}" -gt 0 ]; then ok allowlist "$merchants accepted credential(s) · domain $domain"; else bad allowlist "no accepted merchant credential: run agent/scripts/vet_merchant.py"; status=1; fi
exit $status
