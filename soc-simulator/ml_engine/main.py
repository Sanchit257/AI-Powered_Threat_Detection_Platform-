"""ML engine: consume logs:raw, score, write alerts, publish alerts:live."""

from __future__ import annotations

import json
import os
import random
import sys
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path as PathLib
from typing import Any

try:
    import redis  # type: ignore[import-not-found]
    import psycopg2  # type: ignore[import-not-found]
except ImportError as e:
    print(f"ml_engine: required package missing: {e}", file=sys.stderr)
    print("Install with: pip install redis==5.0.1 psycopg2-binary==2.9.9", file=sys.stderr)
    raise SystemExit(1) from e

from dotenv import load_dotenv
from psycopg2.extras import Json, RealDictCursor

from explanation_agent import get_explanation
from isolation_forest_model import IsolationForestDetector
from lstm_model import LSTMDetector, SEQ_LEN

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
DATABASE_URL = os.environ.get("DATABASE_URL", "")
STREAM_KEY = "logs:raw"
GROUP = "ml_engine"
ALERT_CHANNEL = "alerts:live"

ALERT_THRESHOLD = 6.0
IF_WEIGHT = 0.6
LSTM_WEIGHT = 0.4

BASE_DIR = PathLib(__file__).resolve().parent
MODEL_DIR = BASE_DIR / "models"
IF_PATH = MODEL_DIR / "iforest.joblib"
LSTM_PATH = MODEL_DIR / "lstm.pt"


def _parse_log_ts(ts: str) -> datetime:
    if not ts:
        return datetime.now(timezone.utc)
    s = ts.replace("Z", "+00:00") if ts.endswith("Z") else ts
    return datetime.fromisoformat(s)


def synthetic_normal_log(rng: random.Random) -> dict[str, Any]:
    port = rng.choice([80, 443, 22, 53, 21])
    proto = "UDP" if port == 53 else "TCP"
    et_map = {
        80: "http_request",
        443: "http_request",
        22: "ssh_login",
        53: "dns_query",
        21: "ftp_transfer",
    }
    bt = rng.randint(500, 40_000) if port != 53 else rng.randint(80, 400)
    ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "timestamp": ts,
        "source_ip": f"192.168.{rng.randint(0, 255)}.{rng.randint(1, 254)}",
        "destination_ip": f"10.0.{rng.randint(0, 5)}.{rng.randint(1, 200)}",
        "destination_port": port,
        "protocol": proto,
        "event_type": et_map[port],
        "bytes_transferred": bt,
        "username": rng.choice([None, None, "svc_account"]),
        "raw_message": f"synthetic normal {port} len={bt}",
    }


def build_training_corpus(rng: random.Random) -> tuple[list[dict], list[list[dict]]]:
    logs = [synthetic_normal_log(rng) for _ in range(500)]
    sequences: list[list[dict]] = []
    for _ in range(250):
        src = f"10.{rng.randint(0, 50)}.{rng.randint(0, 255)}.{rng.randint(1, 200)}"
        seq = []
        for __ in range(SEQ_LEN):
            e = synthetic_normal_log(rng)
            e["source_ip"] = src
            seq.append(e)
        sequences.append(seq)
    return logs, sequences


def ensure_models(if_det: IsolationForestDetector, lstm_det: LSTMDetector) -> None:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    rng = random.Random(42)
    corpus: tuple[list[dict], list[list[dict]]] | None = None

    def get_corpus() -> tuple[list[dict], list[list[dict]]]:
        nonlocal corpus
        if corpus is None:
            corpus = build_training_corpus(rng)
        return corpus

    if IF_PATH.exists():
        if_det.load(str(IF_PATH))
        print("ml_engine: loaded IsolationForest from disk", file=sys.stderr)
    else:
        logs, _ = get_corpus()
        if_det.train(logs)
        if_det.save(str(IF_PATH))
        print("ml_engine: trained IsolationForest on synthetic normals", file=sys.stderr)

    if LSTM_PATH.exists():
        lstm_det.load(str(LSTM_PATH))
        print("ml_engine: loaded LSTM from disk", file=sys.stderr)
    else:
        _, sequences = get_corpus()
        lstm_det.train(sequences)
        lstm_det.save(str(LSTM_PATH))
        print("ml_engine: trained LSTM autoencoder on synthetic sequences", file=sys.stderr)


def insert_alert(
    conn: Any,
    log: dict[str, Any],
    final_score: float,
    if_score: float,
    lstm_score: float | None,
    model_used: str,
    explanation: dict[str, Any],
) -> dict[str, Any] | None:
    sev = int(round(final_score))
    sev = max(0, min(10, sev))
    raw_context = {
        "log": log,
        "isolation_forest_score": if_score,
        "lstm_score": lstm_score,
        "final_score": final_score,
        "model_used": model_used,
    }
    ts = _parse_log_ts(str(log.get("timestamp") or ""))
    conf = explanation.get("confidence")
    try:
        conf_f = float(conf) if conf is not None else None
    except (TypeError, ValueError):
        conf_f = None
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO alerts (
                    log_id, timestamp, severity, anomaly_score, model_used, event_type,
                    source_ip, mitre_tactic, mitre_technique, technique_id, confidence,
                    recommended_action, explanation, raw_context, acknowledged
                ) VALUES (
                    NULL, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, FALSE
                )
                RETURNING *
                """,
                (
                    ts,
                    sev,
                    float(final_score),
                    model_used,
                    log.get("event_type"),
                    log.get("source_ip"),
                    explanation.get("mitre_tactic"),
                    explanation.get("mitre_technique"),
                    explanation.get("technique_id"),
                    conf_f,
                    explanation.get("recommended_action"),
                    explanation.get("explanation"),
                    Json(raw_context),
                ),
            )
            row = cur.fetchone()
            conn.commit()
            return dict(row) if row else None
    except Exception as e:
        conn.rollback()
        print(f"ml_engine: insert alert failed: {e}")
        return None


def main() -> None:
    load_dotenv()
    if not DATABASE_URL:
        print("ml_engine: DATABASE_URL required", file=sys.stderr)
        sys.exit(1)

    r = redis.from_url(REDIS_URL, decode_responses=True)
    r.ping()

    try:
        r.xgroup_create(STREAM_KEY, GROUP, id="0", mkstream=True)
    except redis.ResponseError as e:
        if "BUSYGROUP" not in str(e):
            raise

    if_det = IsolationForestDetector()
    lstm_det = LSTMDetector()
    ensure_models(if_det, lstm_det)

    conn = psycopg2.connect(DATABASE_URL)
    consumer = f"c_{os.getpid()}"
    windows: dict[str, deque[dict[str, Any]]] = defaultdict(lambda: deque(maxlen=SEQ_LEN))

    processed = 0
    batch_start = time.perf_counter()
    print("ml_engine: consuming stream", STREAM_KEY, file=sys.stderr)

    while True:
        try:
            resp = r.xreadgroup(
                GROUP,
                consumer,
                streams={STREAM_KEY: ">"},
                count=1,
                block=1000,
            )
        except redis.ResponseError as e:
            print(f"ml_engine: xreadgroup error {e}", file=sys.stderr)
            time.sleep(1)
            continue

        if not resp:
            continue

        for _stream, messages in resp:
            for msg_id, fields in messages:
                log: dict[str, Any] | None = None
                try:
                    raw = fields.get("data") or fields.get(b"data")
                    if isinstance(raw, bytes):
                        raw = raw.decode()
                    log = json.loads(raw)
                except (json.JSONDecodeError, TypeError) as e:
                    print(f"ml_engine: bad payload {msg_id}: {e}", file=sys.stderr)
                    log = None

                if log is None:
                    try:
                        r.xack(STREAM_KEY, GROUP, msg_id)
                    except redis.RedisError:
                        pass
                    continue

                src = str(log.get("source_ip") or "unknown")
                if_score = if_det.score(log)

                win = windows[src]
                win.append(log)
                lstm_score: float | None = None
                if len(win) == SEQ_LEN:
                    lstm_score = lstm_det.score(list(win))

                if lstm_score is None:
                    final_score = if_score
                    model_used = "isolation_forest"
                else:
                    final_score = IF_WEIGHT * if_score + LSTM_WEIGHT * lstm_score
                    model_used = "isolation_forest+lstm"

                if final_score >= ALERT_THRESHOLD:
                    alert_ctx = {
                        "log": log,
                        "isolation_forest_score": if_score,
                        "lstm_score": lstm_score,
                        "final_score": final_score,
                    }
                    expl = get_explanation(alert_ctx)
                    try:
                        row = insert_alert(
                            conn, log, final_score, if_score, lstm_score, model_used, expl
                        )
                    except Exception as e:
                        print(f"ml_engine: insert alert failed: {e}", file=sys.stderr)
                        row = None
                    if row:
                        try:
                            r.publish(ALERT_CHANNEL, json.dumps(row, default=str))
                        except redis.RedisError as e:
                            print(f"ml_engine: publish failed: {e}", file=sys.stderr)

                try:
                    r.xack(STREAM_KEY, GROUP, msg_id)
                except redis.RedisError:
                    pass

                processed += 1
                if processed % 100 == 0:
                    elapsed = time.perf_counter() - batch_start
                    rate = 100.0 / elapsed if elapsed > 0 else 0.0
                    print(f"ml_engine: processed {processed} events ({rate:.2f} ev/s)", flush=True)
                    batch_start = time.perf_counter()


if __name__ == "__main__":
    main()
