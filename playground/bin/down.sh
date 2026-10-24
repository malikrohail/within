#!/bin/sh
# Stops the playground: API :7510 and UI :5176, by the PID files up.sh wrote under playground/data/.
# A port held by a process that is not in our PID file is left alone. Never touches :7500 or :5175.
HERE=$(cd "$(dirname "$0")/.." && pwd)
DATA="$HERE/data"
status=0
if [ -t 1 ]; then GREEN=$(printf '\033[32m'); RED=$(printf '\033[31m'); OFF=$(printf '\033[0m'); fi
ok() { printf '%s✓ %-8s%s %s\n' "$GREEN" "$1" "$OFF" "$2"; }
bad() { printf '%s✗ %-8s%s %s\n' "$RED" "$1" "$OFF" "$2"; }
listener() { lsof -nP -tiTCP:"$1" -sTCP:LISTEN 2>/dev/null | head -1; }

stop() { # label port pidfile
  label=$1 port=$2 pidfile=$3
  pid=$(cat "$pidfile" 2>/dev/null)
  holder=$(listener "$port")
  if [ -z "$holder" ]; then ok "$label" "already down (:$port free)"; rm -f "$pidfile"; return; fi
  # vite forks: the listener may be a child of the PID we wrote. Accept the PID or any of its descendants.
  if [ -z "$pid" ] || { [ "$holder" != "$pid" ] && ! pgrep -P "$pid" 2>/dev/null | grep -qx "$holder"; }; then
    bad "$label" ":$port held by pid $holder, not from $pidfile: left running"; status=1; return
  fi
  kill "$pid" "$holder" 2>/dev/null
  i=0
  while [ -n "$(listener "$port")" ] && [ "$i" -lt 10 ]; do sleep 1; i=$((i + 1)); done
  if [ -n "$(listener "$port")" ]; then bad "$label" ":$port still listening after 10 s"; status=1; else ok "$label" "stopped (pid $pid, :$port free)"; rm -f "$pidfile"; fi
}

stop ui 5176 "$DATA/ui.pid"
stop api 7510 "$DATA/api.pid"
exit $status
