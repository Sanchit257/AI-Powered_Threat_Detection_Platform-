"""One-shot training from Postgres logs (or synthetic fallback). Run after DB seed."""

from __future__ import annotations

import os
import sys

import psycopg2
from dotenv import load_dotenv

from isolation_forest_model import IsolationForestDetector
from lstm_model import LSTMDetector
from training import train_and_save_models


def main() -> None:
    load_dotenv()
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        print("train_initial: DATABASE_URL required", file=sys.stderr)
        sys.exit(1)
    conn = psycopg2.connect(database_url)
    try:
        if_det = IsolationForestDetector()
        lstm_det = LSTMDetector()
        train_and_save_models(if_det, lstm_det, conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
