# Shared by up.sh and down.sh. Our services: wallet :7402, merchants :8001/:8002, dashboard :5174.
# Never touched: Speculos :5000, the workshop app :5173, :8000, the lending desk ports (:5175, :7500, ...).
ROOT=$(cd "$(dirname "$0")/../.." && pwd)

if [ -t 1 ]; then GREEN=$(printf '\033[32m'); RED=$(printf '\033[31m'); YELLOW=$(printf '\033[33m'); OFF=$(printf '\033[0m'); fi
ok() { printf '%s✓ %-10s%s %s\n' "$GREEN" "$1" "$OFF" "$2"; }
bad() { printf '%s✗ %-10s%s %s\n' "$RED" "$1" "$OFF" "$2"; }
note() { printf '%s! %-10s%s %s\n' "$YELLOW" "$1" "$OFF" "$2"; }

# PID listening on a TCP port, or nothing.
listener() { lsof -nP -tiTCP:"$1" -sTCP:LISTEN 2>/dev/null | head -1; }
# Working directory of a PID.
cwd_of() { lsof -a -p "$1" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p'; }
cmd_of() { ps -o command= -p "$1" 2>/dev/null; }

# True when `pid` runs from `dir` (or a path under it) and its command contains `pattern`.
ours() {
  pid=$1 dir=$2 pattern=$3
  case "$(cmd_of "$pid")" in *"$pattern"*) ;; *) return 1 ;; esac
  case "$(cwd_of "$pid")" in "$dir"|"$dir"/*) return 0 ;; esac
  case "$(cmd_of "$pid")" in *"$dir"/*) return 0 ;; esac
  return 1
}

# Wallet supervisors: `sh scripts/run.sh` started from $ROOT/wallet.
wallet_supervisors() {
  for pid in $(pgrep -f "scripts/run.sh" 2>/dev/null); do
    [ "$(cwd_of "$pid")" = "$ROOT/wallet" ] && echo "$pid"
  done
}

# Polls `url` until it answers 2xx, for up to `secs` seconds.
wait_http() {
  url=$1 secs=$2 i=0
  while [ "$i" -lt "$secs" ]; do
    curl -sf -m 2 -o /dev/null "$url" && return 0
    sleep 1
    i=$((i + 1))
  done
  return 1
}
