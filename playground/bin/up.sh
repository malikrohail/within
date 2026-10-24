#!/bin/sh
# Activates the playground: API :7510 (server.py) and UI :5176 (vite). Same shape as wallet/bin/up.sh.
# Never touches the desk :7500 or the stage UI :5175. PID files under playground/data/. Exits 1 on any failure.
HERE=$(cd "$(dirname "$0")/.." && pwd)
DATA="$HERE/data"
mkdir -p "$DATA"
status=0
if [ -t 1 ]; then GREEN=$(printf '\033[32m'); RED=$(printf '\033[31m'); OFF=$(printf '\033[0m'); fi
ok() { printf '%s✓ %-8s%s %s\n' "$GREEN" "$1" "$OFF" "$2"; }
bad() { printf '%s✗ %-8s%s %s\n' "$RED" "$1" "$OFF" "$2"; }
listener() { lsof -nP -tiTCP:"$1" -sTCP:LISTEN 2>/dev/null | head -1; }
wait_http() { i=0; while [ "$i" -lt "$2" ]; do curl -sf -m 2 -o /dev/null "$1" && return 0; sleep 1; i=$((i + 1)); done; return 1; }

[ -x "$HERE/.venv/bin/python" ] || { bad venv "playground/.venv missing: see playground/README.md"; exit 1; }
[ -d "$HERE/ui/node_modules" ] || { bad ui "playground/ui/node_modules missing: cd playground/ui && npm install"; exit 1; }
[ -f "$DATA/pool.json" ] || { bad pool "no pool yet: .venv/bin/python server.py --fund 10"; exit 1; }
curl -sf -m 3 -o /dev/null http://127.0.0.1:7500/health && ok desk "up on :7500 (not managed here)" || { bad desk "no desk on :7500: start lending first (cd lending && .venv/bin/python -m desk)"; exit 1; }

start() { # label port url dir pidfile log command...
  label=$1 port=$2 url=$3 dir=$4 pidfile=$5 log=$6
  shift 6
  if wait_http "$url" 1; then ok "$label" "already up on :$port"; return; fi
  if [ -n "$(listener "$port")" ]; then bad "$label" ":$port held by pid $(listener "$port") but not healthy: run playground/bin/down.sh"; status=1; return; fi
  (cd "$dir" && exec nohup "$@" >> "$log" 2>&1 < /dev/null) &
  echo $! > "$pidfile"
  if wait_http "$url" 45; then ok "$label" "started on :$port (pid $(cat "$pidfile"), log $log)"; else bad "$label" "no answer on $url after 45 s (log $log)"; status=1; fi
}

start api 7510 http://127.0.0.1:7510/health "$HERE" "$DATA/api.pid" "$DATA/api.log" .venv/bin/python server.py
start ui 5176 http://localhost:5176/ "$HERE/ui" "$DATA/ui.pid" "$DATA/ui.log" npm run dev
[ "$status" -eq 0 ] && echo "open http://localhost:5176/  (stage runbook: run playground/bin/down.sh before the stage)"
exit $status
