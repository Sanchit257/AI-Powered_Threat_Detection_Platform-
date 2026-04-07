"""
SOC log simulator: Faker-based events -> Redis Stream logs:raw (XADD) + Postgres logs table.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import redis
from dotenv import load_dotenv
from faker import Faker

try:
    import psycopg2
    from psycopg2.extensions import connection as PgConnection
except ImportError:  # pragma: no cover
    psycopg2 = None
    PgConnection = Any

from patterns import (
    generate_brute_force_ssh_event,
    generate_data_exfil_event,
    generate_port_scan_event,
    pick_scan_ports,
)

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
DATABASE_URL = os.environ.get("DATABASE_URL", "")
STREAM_KEY = "logs:raw"

ATTACK_SLEEP_BETWEEN_BURST_EVENTS = 0.02
MAIN_INTERVAL_SEC = 0.5



def _iso_ts(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def generate_normal_event(faker: Faker) -> dict:
    """Typical enterprise traffic on well-known ports (90% path)."""
    roll = random.random()
    if roll < 0.42:
        port = random.choice([80, 443])
        proto = "TCP"
        et = "http_request"
        dst = faker.ipv4_public()
        user = random.choice([None, faker.user_name(), None])
        b = random.randint(512, 48_000)
        path = random.choice(["/api/health", "/login", "/static/bundle.js", "/search?q=metrics"])
        msg = f"{random.choice(['GET', 'POST'])} {path} HTTP/1.1 -> 200 len={b}"
    elif roll < 0.72:
        port = 53
        proto = "UDP"
        et = "dns_query"
        dst = random.choice(["8.8.8.8", "1.1.1.1", "9.9.9.9"])
        user = None
        b = random.randint(64, 400)
        q = faker.domain_name() + "."
        msg = f"DNS {random.choice(['A', 'AAAA'])} {q} NOERROR"
    elif roll < 0.88:
        port = 22
        proto = "TCP"
        et = "ssh_login"
        dst = faker.ipv4_private()
        user = faker.user_name()
        b = random.randint(900, 8000)
        msg = f"SSH accepted publickey for {user} from {faker.ipv4_private()}"
    elif roll < 0.96:
        port = 21
        proto = "TCP"
        et = "ftp_transfer"
        dst = faker.ipv4_public()
        user = random.choice(["ftpuser", "anonymous", faker.user_name()])
        b = random.randint(2000, 400_000)
        msg = f"FTP STOR completed {b} bytes session={faker.uuid4()[:8]}"
    elif roll < 0.98:
        port = None
        proto = "ICMP"
        et = "port_scan"
        dst = faker.ipv4_public()
        user = None
        b = random.randint(0, 64)
        msg = f"ICMP type=8 echo request id={random.randint(1, 65535)} to {dst}"
    else:
        port = random.choice([8080, 8443])
        proto = "TCP"
        et = "http_request"
        dst = faker.ipv4_public()
        user = None
        b = random.randint(400, 9000)
        msg = f"GET /metrics/prometheus HTTP/1.1 -> 200 len={b} (alt-port {port})"

    return {
        "timestamp": _iso_ts(datetime.now(timezone.utc)),
        "source_ip": faker.ipv4_private(),
        "destination_ip": dst,
        "destination_port": port,
        "protocol": proto,
        "event_type": et,
        "bytes_transferred": b,
        "username": user,
        "raw_message": msg,
    }


def parse_ts_iso(ts: str) -> datetime:
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    return datetime.fromisoformat(ts)


def insert_log_pg(conn: PgConnection, event: dict) -> None:
    ts = parse_ts_iso(event["timestamp"])
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO logs (
                timestamp, source_ip, destination_ip, destination_port,
                protocol, event_type, bytes_transferred, username, raw_message
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                ts,
                event["source_ip"],
                event["destination_ip"],
                event["destination_port"],
                event["protocol"],
                event["event_type"],
                event["bytes_transferred"],
                event.get("username"),
                event["raw_message"],
            ),
        )
    conn.commit()


def emit_event(
    r: redis.Redis,
    pg: Optional[PgConnection],
    event: dict,
) -> None:
    payload = json.dumps(event, default=str)
    r.xadd(STREAM_KEY, {"data": payload})
    if pg is not None:
        insert_log_pg(pg, event)
    print(payload, flush=True)


def run_attack_episode(r: redis.Redis, pg: Optional[PgConnection], faker: Faker) -> None:
    kind = random.choice(["port_scan", "brute_force", "data_exfil"])
    if kind == "port_scan":
        scanner = faker.ipv4_private()
        target = faker.ipv4_private()
        base = datetime.now(timezone.utc)
        for i, port in enumerate(pick_scan_ports(22)):
            ts = base + timedelta(milliseconds=45 * i)
            ev = generate_port_scan_event(faker, scanner, target, port, ts)
            emit_event(r, pg, ev)
            time.sleep(ATTACK_SLEEP_BETWEEN_BURST_EVENTS)
    elif kind == "brute_force":
        attacker = faker.ipv4_public()
        target = faker.ipv4_private()
        base = datetime.now(timezone.utc)
        offsets = sorted(random.random() * 28 for _ in range(12))
        for off in offsets:
            ts = base + timedelta(seconds=off)
            user = faker.user_name()
            ev = generate_brute_force_ssh_event(faker, attacker, target, user, ts)
            emit_event(r, pg, ev)
            time.sleep(ATTACK_SLEEP_BETWEEN_BURST_EVENTS)
    else:
        ev = generate_data_exfil_event(faker)
        emit_event(r, pg, ev)


def connect_pg() -> Optional[PgConnection]:
    if not DATABASE_URL or psycopg2 is None:
        return None
    try:
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = False
        return conn
    except Exception as e:
        print(f"Postgres unavailable ({e}); continuing with Redis only", file=sys.stderr)
        return None


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Emit one normal event and exit")
    args = parser.parse_args()

    faker = Faker()
    r = redis.from_url(REDIS_URL, decode_responses=True)
    r.ping()
    pg = connect_pg()

    if args.once:
        ev = generate_normal_event(faker)
        emit_event(r, pg, ev)
        if pg:
            pg.close()
        return

    print(
        f"Simulator streaming to {STREAM_KEY} every {MAIN_INTERVAL_SEC}s "
        "(10% attack episodes; 90% normal)",
        file=sys.stderr,
    )
    try:
        while True:
            if random.random() < 0.10:
                run_attack_episode(r, pg, faker)
            else:
                ev = generate_normal_event(faker)
                emit_event(r, pg, ev)
            time.sleep(MAIN_INTERVAL_SEC)
    finally:
        if pg:
            pg.close()


if __name__ == "__main__":
    main()
