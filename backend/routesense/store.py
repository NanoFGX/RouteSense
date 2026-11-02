"""The rider's day, kept in one SQLite file.

The current day is stored as one JSON document (simple and enough for one rider),
and every outcome is also appended to an `outcomes` table: that log is what the
retraining script learns from once real deliveries replace the synthetic data.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from . import config


@contextmanager
def _db():
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH)
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        conn.execute(
            """CREATE TABLE IF NOT EXISTS outcomes (
                id INTEGER PRIMARY KEY AUTOINCREMENT, logged_at TEXT, day_id TEXT, stop_id TEXT,
                status TEXT, reason TEXT, minute REAL, attempt INTEGER, property_type TEXT,
                guardhouse INTEGER, cod INTEGER, cod_amount REAL, prior_failures INTEGER,
                tw_start INTEGER, tw_end INTEGER, replied INTEGER, simulated INTEGER)"""
        )
        yield conn
        conn.commit()
    finally:
        conn.close()


def load_day() -> dict | None:
    with _db() as conn:
        row = conn.execute("SELECT value FROM state WHERE key = 'day'").fetchone()
    return json.loads(row[0]) if row else None


def save_day(day: dict) -> None:
    with _db() as conn:
        conn.execute("INSERT OR REPLACE INTO state (key, value) VALUES ('day', ?)", (json.dumps(day),))


def log_outcome(day_id: str, stop: dict, status: str, reason: str | None, minute: float, simulated: bool = False) -> None:
    with _db() as conn:
        conn.execute(
            """INSERT INTO outcomes (logged_at, day_id, stop_id, status, reason, minute, attempt, property_type,
               guardhouse, cod, cod_amount, prior_failures, tw_start, tw_end, replied, simulated)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (datetime.now(timezone.utc).isoformat(timespec="seconds"), day_id, stop["id"], status, reason, minute,
             stop.get("attempts", 0), stop["property_type"], int(bool(stop.get("guardhouse"))), int(bool(stop.get("cod"))),
             float(stop.get("cod_amount") or 0), int(stop.get("prior_failures", 0)), stop["tw_start"], stop["tw_end"],
             int(bool(stop.get("reply"))), int(simulated)),
        )


def outcome_count() -> int:
    with _db() as conn:
        return conn.execute("SELECT COUNT(*) FROM outcomes").fetchone()[0]
