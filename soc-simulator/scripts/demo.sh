#!/usr/bin/env bash
# Recorded-demo helper: bring stack up, then fire several inject-attack calls.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

docker compose up --build -d
echo "Waiting for services…"
sleep 10

BASE="${DEMO_API_BASE:-http://localhost/api}"
for i in 1 2 3 4 5; do
  echo "Inject $i/5 → POST $BASE/debug/inject-attack"
  curl -sS -X POST "$BASE/debug/inject-attack" | head -c 200 || true
  echo ""
  sleep 3
done

echo ""
echo "Open the dashboard: http://localhost/"
echo "(API base used: $BASE)"
