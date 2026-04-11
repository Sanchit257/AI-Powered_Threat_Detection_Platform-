#!/usr/bin/env bash
# Seed Postgres, train ML models, push one batch of logs to Redis.
# Requires: stack running (`docker compose up -d`) and `.env` present.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  echo "Missing .env — copy .env.example to .env and configure it."
  exit 1
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

echo "Waiting for PostgreSQL (db container)..."
for _ in $(seq 1 90); do
  if docker compose exec -T db pg_isready -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" >/dev/null 2>&1; then
    echo "PostgreSQL is ready."
    break
  fi
  sleep 1
done

if ! docker compose exec -T db pg_isready -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" >/dev/null 2>&1; then
  echo "Timeout waiting for PostgreSQL. Is the stack up? (docker compose up -d)"
  exit 1
fi

echo "Applying SQL seeds..."
docker compose exec -T db psql -v ON_ERROR_STOP=1 -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" < "${ROOT}/db/seed_normal.sql"
docker compose exec -T db psql -v ON_ERROR_STOP=1 -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" < "${ROOT}/db/seed_attacks.sql"

echo "Training IsolationForest + LSTM from logs (train_initial.py)..."
docker compose run --rm ml_engine python train_initial.py

echo "Publishing one simulator batch to Redis..."
docker compose run --rm simulator python main.py --once

echo "Seed complete."
