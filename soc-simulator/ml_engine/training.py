"""Train IsolationForest and LSTM from Postgres logs or synthetic corpus."""

from __future__ import annotations

import random
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor

from isolation_forest_model import IsolationForestDetector
from lstm_model import LSTMDetector, SEQ_LEN

MIN_LOGS_ISOLATION_FOREST = 50
MIN_SEQUENCES_LSTM = 20

BASE_DIR = Path(__file__).resolve().parent
MODEL_DIR = BASE_DIR / "models"
IF_SAVE_PATH = MODEL_DIR / "isolation_forest.joblib"
IF_LEGACY_PATH = MODEL_DIR / "iforest.joblib"
LSTM_SAVE_PATH = MODEL_DIR / "lstm.pt"


def resolve_existing_if_path() -> Path | None:
    if IF_SAVE_PATH.exists():
        return IF_SAVE_PATH
    if IF_LEGACY_PATH.exists():
        return IF_LEGACY_PATH
    return None


def pg_row_to_log(row: dict[str, Any]) -> dict[str, Any]:
    ts = row["timestamp"]
    if hasattr(ts, "isoformat"):
        ts_str = ts.isoformat()
    else:
        ts_str = str(ts)
    return {
        "timestamp": ts_str,
        "source_ip": row["source_ip"],
        "destination_ip": row.get("destination_ip"),
        "destination_port": row["destination_port"],
        "protocol": row.get("protocol") or "TCP",
        "event_type": row["event_type"],
        "bytes_transferred": int(row.get("bytes_transferred") or 0),
        "username": row.get("username"),
        "raw_message": row.get("raw_message") or "",
    }


def load_logs_from_db(conn: Any) -> list[dict[str, Any]]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT timestamp, source_ip, destination_ip, destination_port, protocol,
                   event_type, bytes_transferred, username, raw_message
            FROM logs
            ORDER BY timestamp ASC
            """
        )
        rows = cur.fetchall()
    return [pg_row_to_log(dict(r)) for r in rows]


def build_sequences_from_logs(
    logs: list[dict[str, Any]], seq_len: int = SEQ_LEN
) -> list[list[dict[str, Any]]]:
    by_ip: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for log in logs:
        ip = str(log.get("source_ip") or "unknown")
        by_ip[ip].append(log)
    sequences: list[list[dict[str, Any]]] = []
    for logs_ip in by_ip.values():
        if len(logs_ip) < seq_len:
            continue
        logs_ip.sort(key=lambda x: str(x.get("timestamp") or ""))
        for i in range(len(logs_ip) - seq_len + 1):
            sequences.append(logs_ip[i : i + seq_len])
    return sequences


def _synthetic_corpus(
    rng: random.Random,
) -> tuple[list[dict[str, Any]], list[list[dict[str, Any]]]]:
    from training_data import build_training_corpus

    return build_training_corpus(rng)


def train_and_save_models(
    if_det: IsolationForestDetector,
    lstm_det: LSTMDetector,
    conn: Any,
    rng: random.Random | None = None,
) -> None:
    """Train both models and save to models/isolation_forest.joblib and models/lstm.pt."""
    rng = rng or random.Random(42)
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    logs = load_logs_from_db(conn)
    synthetic_logs: list[dict[str, Any]] | None = None
    synthetic_sequences: list[list[dict[str, Any]]] | None = None

    if len(logs) < MIN_LOGS_ISOLATION_FOREST:
        print(
            f"ml_engine: only {len(logs)} logs in DB; using synthetic corpus for training",
            file=sys.stderr,
        )
        synthetic_logs, synthetic_sequences = _synthetic_corpus(rng)
        train_logs = synthetic_logs
    else:
        train_logs = logs

    if_det.train(train_logs)
    if_det.save(str(IF_SAVE_PATH))
    print(f"ml_engine: saved IsolationForest to {IF_SAVE_PATH}", file=sys.stderr)

    if synthetic_sequences is not None:
        sequences = synthetic_sequences
    else:
        sequences = build_sequences_from_logs(logs, SEQ_LEN)
        if len(sequences) < MIN_SEQUENCES_LSTM:
            print(
                "ml_engine: few LSTM sequences from DB; supplementing with synthetic",
                file=sys.stderr,
            )
            _, syn_seq = _synthetic_corpus(rng)
            sequences = sequences + syn_seq

    lstm_det.train(sequences)
    lstm_det.save(str(LSTM_SAVE_PATH))
    print(f"ml_engine: saved LSTM to {LSTM_SAVE_PATH}", file=sys.stderr)


def ensure_models_or_train(
    if_det: IsolationForestDetector,
    lstm_det: LSTMDetector,
    database_url: str,
) -> None:
    """Load models from disk if present; otherwise train from DB (or synthetic) and save."""
    if_p = resolve_existing_if_path()
    if if_p and LSTM_SAVE_PATH.exists():
        if_det.load(str(if_p))
        lstm_det.load(str(LSTM_SAVE_PATH))
        print(
            f"ml_engine: loaded IsolationForest from {if_p}, LSTM from {LSTM_SAVE_PATH}",
            file=sys.stderr,
        )
        return

    conn = psycopg2.connect(database_url)
    try:
        train_and_save_models(if_det, lstm_det, conn)
    finally:
        conn.close()
