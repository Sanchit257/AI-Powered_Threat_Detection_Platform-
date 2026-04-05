"""Synthetic SOC log generator: pushes JSON events to Redis."""

import argparse
import json
import os
import random
import sys
import time
import uuid

import redis

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
STREAM_KEY = "soc:logs"


def fake_event() -> dict:
    severities = ["low", "medium", "high", "critical"]
    sources = ["firewall", "ids", "endpoint", "proxy", "auth"]
    return {
        "id": str(uuid.uuid4()),
        "ts": time.time(),
        "source": random.choice(sources),
        "severity": random.choice(severities),
        "message": f"Synthetic alert {random.randint(1000, 9999)}",
    }


def emit_once(r: redis.Redis) -> None:
    payload = json.dumps(fake_event())
    r.xadd(STREAM_KEY, {"data": payload})
    print(f"Pushed 1 event to {STREAM_KEY}", file=sys.stderr)


def run_loop(r: redis.Redis, interval: float = 5.0) -> None:
    print(f"Simulator running; publishing to {STREAM_KEY} every {interval}s", file=sys.stderr)
    while True:
        emit_once(r)
        time.sleep(interval)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Emit a single event and exit")
    parser.add_argument("--interval", type=float, default=5.0, help="Seconds between events (loop mode)")
    args = parser.parse_args()

    r = redis.from_url(REDIS_URL, decode_responses=True)
    r.ping()

    if args.once:
        emit_once(r)
    else:
        run_loop(r, args.interval)


if __name__ == "__main__":
    main()
