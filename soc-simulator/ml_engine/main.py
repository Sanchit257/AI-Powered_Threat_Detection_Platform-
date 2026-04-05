"""Placeholder ML anomaly worker: reads Redis stream stub, pings Postgres."""

import os
import sys
import time

import psycopg
import redis

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
DATABASE_URL = os.environ.get("DATABASE_URL", "")
STREAM_KEY = "soc:logs"


def main() -> None:
    r = redis.from_url(REDIS_URL, decode_responses=True)
    r.ping()
    print("ml_engine: connected to Redis", file=sys.stderr)

    if DATABASE_URL:
        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        print("ml_engine: database reachable", file=sys.stderr)
    else:
        print("ml_engine: DATABASE_URL not set, skipping DB check", file=sys.stderr)

    print("ml_engine: idle worker (placeholder); Ctrl+C to stop", file=sys.stderr)
    while True:
        try:
            r.xlen(STREAM_KEY)
        except redis.RedisError as e:
            print(f"ml_engine: redis error {e}", file=sys.stderr)
        time.sleep(30)


if __name__ == "__main__":
    main()
