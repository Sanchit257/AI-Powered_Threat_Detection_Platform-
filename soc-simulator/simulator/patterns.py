"""Attack-pattern log generators; each function returns one log event dict."""

from __future__ import annotations

import random
from datetime import datetime, timezone

from faker import Faker


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def generate_port_scan_event(
    _faker: Faker,
    scanner_ip: str,
    target_ip: str,
    port: int,
    ts: datetime,
) -> dict:
    """Single probe in a port-scan burst; bytes near zero."""
    return {
        "timestamp": _iso(ts),
        "source_ip": scanner_ip,
        "destination_ip": target_ip,
        "destination_port": port,
        "protocol": "TCP",
        "event_type": "port_scan",
        "bytes_transferred": random.randint(0, 128),
        "username": None,
        "raw_message": f"SYN probe dst={target_ip}:{port} flags=SYN len=0",
    }


def generate_brute_force_ssh_event(
    _faker: Faker,
    attacker_ip: str,
    target_ip: str,
    username: str,
    ts: datetime,
) -> dict:
    """One failed SSH auth attempt as part of a brute-force sequence."""
    return {
        "timestamp": _iso(ts),
        "source_ip": attacker_ip,
        "destination_ip": target_ip,
        "destination_port": 22,
        "protocol": "TCP",
        "event_type": "brute_force",
        "bytes_transferred": random.randint(180, 900),
        "username": username,
        "raw_message": f"SSH auth failure user={username} from {attacker_ip} method=password",
    }


def generate_data_exfil_event(faker: Faker) -> dict:
    """Large outbound transfer to an unusual port."""
    unusual = random.choice([4444, 8081, 9999, 1337, 6667, 27100])
    nbytes = random.randint(52 * 1024 * 1024, 110 * 1024 * 1024)
    src = faker.ipv4_private()
    dst = faker.ipv4_public()
    user = random.choice([None, faker.user_name()])
    return {
        "timestamp": _iso(datetime.now(timezone.utc)),
        "source_ip": src,
        "destination_ip": dst,
        "destination_port": unusual,
        "protocol": "TCP",
        "event_type": "data_exfil",
        "bytes_transferred": nbytes,
        "username": user,
        "raw_message": (
            f"Sustained TLS upload {nbytes // (1024 * 1024)}MB to {dst}:{unusual} "
            f"from {src} (unusual service port)"
        ),
    }


def pick_scan_ports(count: int = 22) -> list[int]:
    """At least 20 distinct ports for a scan episode."""
    pool = list(range(1, 1024))
    random.shuffle(pool)
    return pool[: max(count, 22)]
