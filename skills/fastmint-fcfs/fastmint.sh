#!/usr/bin/env bash
# fastmint launcher. Runs from the skill directory, with the macOS CA bundle for Node TLS when present.
#   ./fastmint.sh bench [--live|--ca]
#   ./fastmint.sh recon <url> [--contract 0x..]
#   ./fastmint.sh fire  --to 0x.. (--data 0x.. | --sig ".." --args '[..]') --start HH:MM [--dry] ...
#   ./fastmint.sh logs            tail the latest run log
#   ./fastmint.sh locks           list execute locks (delete one only on the user's explicit new command)
set -euo pipefail
cd "$(dirname "$0")"
# local secrets (premium RPC keys etc.): .env is git-ignored and excluded from the zip
if [ -f ./.env ]; then set -a; . ./.env; set +a; fi
CA="${FASTMINT_CA:-$HOME/.config/certs/system-ca.pem}"
if [ -z "${NODE_EXTRA_CA_CERTS:-}" ] && [ -f "$CA" ]; then export NODE_EXTRA_CA_CERTS="$CA"; fi
cmd="${1:-help}"; shift || true
case "$cmd" in
  bench) exec node bench.js "$@" ;;
  recon) exec node recon.js "$@" ;;
  fire)  exec node fire.js "$@" ;;
  logs)  f=$(ls -t runs/*.log 2>/dev/null | head -1); [ -n "$f" ] && { echo "== $f"; tail -n "${1:-60}" "$f"; } || echo "no logs" ;;
  locks) ls -la runs/lock_*.json 2>/dev/null || echo "no locks" ;;
  *) sed -n '2,8p' "$0" ;;
esac
