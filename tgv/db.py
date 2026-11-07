"""SQLite storage. One file, no server; schema covers every stage.

Stage 1 writes: items, metric_snapshots, runs, alerts, api_usage.
Later stages write: productions, publications, post_metrics,
follower_snapshots, monetization_programs, revenue. Their tables exist now
so the dashboard and the schema stay stable.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from tgv.models import ContentItem, Metrics

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY,
    canonical_key TEXT NOT NULL UNIQUE,
    source TEXT NOT NULL,
    source_name TEXT NOT NULL,
    external_id TEXT,
    url TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    author TEXT DEFAULT '',
    published_at TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    language TEXT,
    country TEXT,
    media_type TEXT,
    license TEXT,
    duration_seconds INTEGER,
    is_official INTEGER NOT NULL DEFAULT 0,
    cluster_id INTEGER,
    relevance REAL,
    category TEXT,
    claim_status TEXT,
    modality TEXT,
    flags TEXT DEFAULT '[]',
    score REAL,
    score_breakdown TEXT DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'found'
        CHECK (status IN ('found','review','selected','rejected','in_production','produced','discarded'))
);
CREATE INDEX IF NOT EXISTS idx_items_score ON items(score DESC);
CREATE INDEX IF NOT EXISTS idx_items_cluster ON items(cluster_id);

CREATE TABLE IF NOT EXISTS metric_snapshots (
    id INTEGER PRIMARY KEY,
    item_id INTEGER NOT NULL REFERENCES items(id),
    captured_at TEXT NOT NULL,
    views INTEGER, likes INTEGER, comments INTEGER, shares INTEGER
);
CREATE INDEX IF NOT EXISTS idx_snap_item ON metric_snapshots(item_id, captured_at);

CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    source TEXT NOT NULL,
    status TEXT NOT NULL,
    fetched INTEGER DEFAULT 0,
    new_items INTEGER DEFAULT 0,
    error TEXT
);

CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY,
    created_at TEXT NOT NULL,
    level TEXT NOT NULL CHECK (level IN ('info','warning','error')),
    component TEXT NOT NULL,
    message TEXT NOT NULL,
    resolved INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS api_usage (
    day TEXT NOT NULL,
    api TEXT NOT NULL,
    units INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (day, api)
);

-- Stage 2-3: production and validation
CREATE TABLE IF NOT EXISTS productions (
    id INTEGER PRIMARY KEY,
    item_id INTEGER REFERENCES items(id),
    modality TEXT NOT NULL,
    format TEXT NOT NULL,            -- reel | carousel | image | story
    status TEXT NOT NULL,            -- draft | rendering | ready | review | approved | rejected | failed
    writer TEXT,
    script TEXT,                     -- ScriptDraft JSON
    validation TEXT,                 -- errors/warnings JSON
    caption TEXT,
    media_path TEXT,                 -- vertical video
    cover_path TEXT,
    carousel_dir TEXT,
    rights_basis TEXT,               -- licence / permission reference for modality A
    review_notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Stage 4: distribution
CREATE TABLE IF NOT EXISTS publications (
    id INTEGER PRIMARY KEY,
    production_id INTEGER REFERENCES productions(id),
    platform TEXT NOT NULL,          -- instagram | facebook | tiktok
    status TEXT NOT NULL,            -- scheduled | published | failed | test
    scheduled_for TEXT,
    published_at TEXT,
    platform_post_id TEXT,
    permalink TEXT,
    error TEXT
);

-- Stage 5: performance
CREATE TABLE IF NOT EXISTS post_metrics (
    id INTEGER PRIMARY KEY,
    publication_id INTEGER REFERENCES publications(id),
    captured_at TEXT NOT NULL,
    views INTEGER, reach INTEGER, likes INTEGER, comments INTEGER,
    shares INTEGER, saves INTEGER, watch_time_seconds INTEGER
);
CREATE TABLE IF NOT EXISTS follower_snapshots (
    platform TEXT NOT NULL,
    captured_at TEXT NOT NULL,
    followers INTEGER NOT NULL,
    PRIMARY KEY (platform, captured_at)
);

-- Stage 6: monetisation (only confirmed data; never estimates)
CREATE TABLE IF NOT EXISTS monetization_programs (
    platform TEXT NOT NULL,
    program TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('unknown','not_eligible','eligible','applied','active')),
    evidence TEXT,                   -- where the platform confirmed it
    checked_at TEXT,
    PRIMARY KEY (platform, program)
);
CREATE TABLE IF NOT EXISTS revenue (
    id INTEGER PRIMARY KEY,
    platform TEXT NOT NULL,
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    amount_cents INTEGER NOT NULL,
    currency TEXT NOT NULL,
    source TEXT NOT NULL,            -- 'platform_report' | 'payout' | 'sponsor_invoice'
    confirmed INTEGER NOT NULL DEFAULT 0
);
"""


def iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def parse_iso(text: str) -> datetime:
    return datetime.fromisoformat(text)


def connect(path: str | Path) -> sqlite3.Connection:
    if str(path) != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


def upsert_item(conn: sqlite3.Connection, key: str, item: ContentItem, now: datetime) -> tuple[int, bool]:
    """Insert a new item or refresh its mutable fields. Returns (id, is_new)."""
    row = conn.execute("SELECT id FROM items WHERE canonical_key = ?", (key,)).fetchone()
    if row:
        conn.execute(
            "UPDATE items SET last_seen_at = ?, title = ?, description = ?,"
            " license = COALESCE(?, license), language = COALESCE(language, ?) WHERE id = ?",
            (iso(now), item.title, item.description, item.license, item.language, row["id"]),
        )
        return row["id"], False
    cur = conn.execute(
        """INSERT INTO items (canonical_key, source, source_name, external_id, url, title,
            description, author, published_at, first_seen_at, last_seen_at, language, country,
            media_type, license, duration_seconds, is_official)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            key, item.source, item.source_name, item.external_id, item.url, item.title,
            item.description, item.author, iso(item.published_at), iso(now), iso(now),
            item.language, item.country, item.media_type, item.license,
            item.duration_seconds, int(item.is_official),
        ),
    )
    return cur.lastrowid, True


def add_snapshot(conn: sqlite3.Connection, item_id: int, m: Metrics) -> None:
    if all(v is None for v in (m.views, m.likes, m.comments, m.shares)):
        return
    conn.execute(
        "INSERT INTO metric_snapshots (item_id, captured_at, views, likes, comments, shares)"
        " VALUES (?,?,?,?,?,?)",
        (item_id, iso(m.captured_at), m.views, m.likes, m.comments, m.shares),
    )


def add_alert(conn: sqlite3.Connection, now: datetime, level: str, component: str, message: str) -> None:
    conn.execute(
        "INSERT INTO alerts (created_at, level, component, message) VALUES (?,?,?,?)",
        (iso(now), level, component, message),
    )


def add_usage(conn: sqlite3.Connection, now: datetime, api: str, units: int) -> None:
    conn.execute(
        "INSERT INTO api_usage (day, api, units) VALUES (?,?,?)"
        " ON CONFLICT(day, api) DO UPDATE SET units = units + excluded.units",
        (now.date().isoformat(), api, units),
    )


def usage_today(conn: sqlite3.Connection, now: datetime, api: str) -> int:
    row = conn.execute(
        "SELECT units FROM api_usage WHERE day = ? AND api = ?", (now.date().isoformat(), api)
    ).fetchone()
    return row["units"] if row else 0


def dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True)
