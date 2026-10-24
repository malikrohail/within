#!/bin/sh
# Stops the Policy Wallet stack: wallet :7402 (and its run.sh supervisor), merchants :8001/:8002, dashboard :5174.
# A process is stopped only when its command and directory are ours; anything else on those ports is left alone.
. "$(dirname "$0")/lib.sh"
status=0

stop() { # label port dir pattern
  pid=$(listener "$2")
  if [ -z "$pid" ]; then ok "$1" "already down (:$2 free)"; return; fi
  if ! ours "$pid" "$3" "$4"; then bad "$1" ":$2 held by pid $pid ($(cmd_of "$pid" | cut -c1-80)), not ours: left running"; status=1; return; fi
  kill "$pid"
  i=0
  while [ -n "$(listener "$2")" ] && [ "$i" -lt 10 ]; do sleep 1; i=$((i + 1)); done
  if [ -n "$(listener "$2")" ]; then bad "$1" ":$2 still listening after 10 s"; status=1; else ok "$1" "stopped (pid $pid, :$2 free)"; fi
}

# Supervisor first, or it restarts the wallet 2 s after we stop it. Its trap stops the child too.
supervisors=$(wallet_supervisors)
if [ -n "$supervisors" ]; then
  kill $supervisors
  i=0
  while [ -n "$(listener 7402)" ] && [ "$i" -lt 10 ]; do sleep 1; i=$((i + 1)); done
  [ -z "$(listener 7402)" ] && ok wallet "stopped (supervisor $(echo $supervisors), :7402 free)"
fi
[ -z "$supervisors" ] || [ -n "$(listener 7402)" ] && stop wallet 7402 "$ROOT/wallet" "src/index.ts"
stop good 8001 "$ROOT/agent" "merchants.good"
stop rogue 8002 "$ROOT/agent" "merchants.rogue"
stop dashboard 5174 "$ROOT/dashboard" "vite"
exit $status
