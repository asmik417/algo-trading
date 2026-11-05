"""SQLite persistence for profiles, suggestions, paper positions and reviews.

One file (config.DB_PATH). Every page and job opens its own short-lived
connection; SQLite handles the locking. The schema is created on first use
and is additive-only, so an older database keeps working.
"""
from __future__ import annotations

import os
import sqlite3

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS profiles (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    owner       TEXT,
    params_json TEXT NOT NULL,
    is_active   INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS suggestion_runs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id    INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    trading_day   TEXT NOT NULL,
    universe_size INTEGER,
    scored_size   INTEGER,
    passed_size   INTEGER,
    params_json   TEXT NOT NULL,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS suggestions (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id             INTEGER NOT NULL REFERENCES suggestion_runs(id) ON DELETE CASCADE,
    profile_id         INTEGER NOT NULL,
    symbol             TEXT NOT NULL,
    trading_day        TEXT NOT NULL,
    rank               INTEGER,
    score              REAL,
    stage              TEXT,
    signal             TEXT,
    price              REAL,
    entry_aggressive   REAL,
    entry_optimal      REAL,
    entry_conservative REAL,
    stop_loss          REAL,
    target             REAL,
    risk_reward        REAL,
    horizon_days       INTEGER,
    planned_exit_date  TEXT,
    timing_note        TEXT,
    exit_note          TEXT,
    positives_json     TEXT,
    risks_json         TEXT,
    payload_json       TEXT,
    narration_json     TEXT,
    created_at         TEXT NOT NULL,
    UNIQUE(run_id, symbol)
);

CREATE TABLE IF NOT EXISTS positions (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id         INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    suggestion_id      INTEGER REFERENCES suggestions(id) ON DELETE SET NULL,
    symbol             TEXT NOT NULL,
    opened_on          TEXT NOT NULL,
    entry_price        REAL NOT NULL,
    qty                INTEGER NOT NULL,
    invested           REAL NOT NULL,
    capital            REAL NOT NULL,
    target             REAL,
    stop_loss          REAL,
    original_exit_date TEXT,
    planned_exit_date  TEXT,
    status             TEXT NOT NULL DEFAULT 'open',   -- open | due | closed
    last_mark_date     TEXT,
    last_close         REAL,
    closed_on          TEXT,
    exit_price         REAL,
    pnl                REAL,
    pnl_pct            REAL,
    close_reason       TEXT,
    created_at         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS position_events (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    position_id   INTEGER NOT NULL REFERENCES positions(id) ON DELETE CASCADE,
    event_date    TEXT NOT NULL,
    event_type    TEXT NOT NULL,   -- open | extend | shorten | close | note | due
    old_exit_date TEXT,
    new_exit_date TEXT,
    reason        TEXT,
    price         REAL,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS position_marks (
    position_id INTEGER NOT NULL REFERENCES positions(id) ON DELETE CASCADE,
    mark_date   TEXT NOT NULL,
    close       REAL NOT NULL,
    value       REAL NOT NULL,
    pnl         REAL NOT NULL,
    pnl_pct     REAL NOT NULL,
    PRIMARY KEY (position_id, mark_date)
);

CREATE TABLE IF NOT EXISTS loss_reviews (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    position_id  INTEGER NOT NULL UNIQUE REFERENCES positions(id) ON DELETE CASCADE,
    reasons_json TEXT NOT NULL,
    mistakes     TEXT,
    lesson       TEXT,
    algo_change  TEXT,
    reviewed_on  TEXT NOT NULL,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS app_meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


def get_conn(path: str | None = None) -> sqlite3.Connection:
    path = path or config.DB_PATH
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.executescript(SCHEMA)
    return conn
