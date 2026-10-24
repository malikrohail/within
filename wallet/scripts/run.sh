#!/bin/sh
# Keeps the wallet up: restarts `npm start` whenever it exits. Ctrl-C (or SIGTERM) stops both.
cd "$(dirname "$0")/.." || exit 1
mkdir -p data
child=""
trap 'kill $child 2>/dev/null; exit 0' INT TERM
while :; do
  node_modules/.bin/tsx src/index.ts >> data/server.log 2>&1 &
  child=$!
  wait $child
  code=$?
  echo "$(date -u +%FT%TZ) wallet exited with code $code, restarting in 2 s" >> data/server.log
  sleep 2
done
