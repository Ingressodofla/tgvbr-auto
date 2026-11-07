"""Stage 1 flow: DISCOVERY -> ANALYSIS -> SELECTION.

discover(): runs each enabled connector, isolates failures per source,
            stores items and metric snapshots, logs runs and alerts.
analyze():  recomputes clusters, classification and scores for the
            recent window (scores change as new snapshots arrive).
select():   marks the best item of each story for production, never more
            than one per cluster, never items that need human review.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta

from tgv import db
from tgv.classify import classify, needs_review
from tgv.dedup import assign_clusters, canonical_key
from tgv.models import ContentItem
from tgv.scoring import Snapshot, score
from tgv.sources.base import SourceNotConfigured
from tgv.sources.reddit import RedditConnector
from tgv.sources.rss import RssConnector
from tgv.sources.youtube import YouTubeSearchConnector
from tgv.textutil import detect_language


def build_connectors(config: dict) -> list:
    connectors: list = []
    for feed in config.get("rss", []):
        if feed.get("enabled") and feed.get("url"):
            connectors.append(RssConnector(
                feed["name"], feed["url"], official=feed.get("official", False),
                language=feed.get("language"), country=feed.get("country"),
            ))
    yt = config.get("youtube", {})
    if yt.get("enabled"):
        c = YouTubeSearchConnector(
            yt["queries"], region_codes=yt.get("region_codes"),
            relevance_language=yt.get("relevance_language", "en"),
            lookback_hours=yt.get("lookback_hours", 72), max_results=yt.get("max_results", 25),
        )
        c.daily_budget = yt.get("daily_unit_budget", c.daily_budget)
        connectors.append(c)
    rd = config.get("reddit", {})
    if rd.get("enabled"):
        connectors.append(RedditConnector(rd["subreddits"], listing=rd.get("listing", "hot")))
    return connectors


def ingest(conn: sqlite3.Connection, items: list[ContentItem], now: datetime) -> tuple[int, int]:
    new = 0
    for item in items:
        if not item.title.strip():
            continue
        if item.language is None:
            item.language = detect_language(f"{item.title} {item.description}")
        item_id, is_new = db.upsert_item(conn, canonical_key(item.url), item, now)
        new += is_new
        if item.metrics:
            db.add_snapshot(conn, item_id, item.metrics)
    return len(items), new


def discover(conn, config, http, now, only: set[str] | None = None, connectors=None) -> list[dict]:
    report = []
    for c in connectors if connectors is not None else build_connectors(config):
        if only and c.name not in only and getattr(c, "kind", "") not in only:
            continue
        run = {"source": c.name, "status": "ok", "fetched": 0, "new": 0, "error": None}
        if isinstance(c, YouTubeSearchConnector):
            c.budget_left = max(0, c.daily_budget - db.usage_today(conn, now, "youtube"))
        try:
            items = list(c.fetch(http, now))
            run["fetched"], run["new"] = ingest(conn, items, now)
        except SourceNotConfigured as exc:
            run["status"], run["error"] = "skipped", str(exc)
            db.add_alert(conn, now, "info", c.name, f"source skipped: {exc}")
        except Exception as exc:  # one broken source must not stop the others
            run["status"], run["error"] = "error", f"{type(exc).__name__}: {exc}"[:500]
            db.add_alert(conn, now, "error", c.name, run["error"])
        finally:
            if isinstance(c, YouTubeSearchConnector) and c.units_spent:
                db.add_usage(conn, now, "youtube", c.units_spent)
                if c.budget_left is not None and c.units_spent >= c.budget_left:
                    db.add_alert(conn, now, "warning", "youtube", "daily unit budget reached")
        conn.execute(
            "INSERT INTO runs (started_at, finished_at, source, status, fetched, new_items, error)"
            " VALUES (?,?,?,?,?,?,?)",
            (db.iso(now), db.iso(now), run["source"], run["status"], run["fetched"], run["new"], run["error"]),
        )
        conn.commit()
        report.append(run)
    return report


@dataclass
class _Row:
    id: int
    title: str
    published_at: datetime


def _row_to_item(r: sqlite3.Row) -> ContentItem:
    return ContentItem(
        source=r["source"], source_name=r["source_name"], external_id=r["external_id"] or "",
        url=r["url"], title=r["title"], published_at=db.parse_iso(r["published_at"]),
        author=r["author"] or "", description=r["description"] or "", language=r["language"],
        country=r["country"], media_type=r["media_type"] or "article", license=r["license"],
        is_official=bool(r["is_official"]), duration_seconds=r["duration_seconds"],
    )


def analyze(conn: sqlite3.Connection, config: dict, now: datetime) -> int:
    a = config.get("analysis", {})
    since = db.iso(now - timedelta(days=a.get("window_days", 7)))
    rows = conn.execute("SELECT * FROM items WHERE published_at >= ?", (since,)).fetchall()
    if not rows:
        return 0
    clusters = assign_clusters(
        [_Row(r["id"], r["title"], db.parse_iso(r["published_at"])) for r in rows],
        threshold=a.get("cluster_threshold", 0.5), window_hours=a.get("cluster_window_hours", 72),
    )
    sources_per_cluster: dict[int, set[str]] = {}
    for r in rows:
        sources_per_cluster.setdefault(clusters[r["id"]], set()).add(r["source_name"])

    snaps: dict[int, list[Snapshot]] = {}
    for s in conn.execute(
        "SELECT * FROM metric_snapshots WHERE item_id IN (SELECT id FROM items WHERE published_at >= ?)",
        (since,),
    ):
        snaps.setdefault(s["item_id"], []).append(Snapshot(
            db.parse_iso(s["captured_at"]), s["views"], s["likes"], s["comments"], s["shares"]))

    for r in rows:
        item = _row_to_item(r)
        c = classify(item)
        total, breakdown = score(
            published_at=item.published_at, now=now, relevance=c.relevance, category=c.category,
            language=item.language, country=item.country,
            cluster_sources=len(sources_per_cluster[clusters[r["id"]]]),
            snapshots=snaps.get(r["id"], []), weights=config.get("scoring") or None,
        )
        status = r["status"]
        if status == "found":
            if c.modality == "skip":
                status = "discarded"
            elif needs_review(c):
                status = "review"
        conn.execute(
            "UPDATE items SET cluster_id=?, relevance=?, category=?, claim_status=?, modality=?,"
            " flags=?, score=?, score_breakdown=?, status=? WHERE id=?",
            (clusters[r["id"]], c.relevance, c.category, c.claim_status, c.modality,
             db.dumps(c.flags), total, db.dumps(breakdown), status, r["id"]),
        )
    conn.commit()
    return len(rows)


def select(conn: sqlite3.Connection, config: dict, limit: int = 5) -> list[sqlite3.Row]:
    """Pick the top story leaders (one per cluster) that are safe to produce."""
    min_score = config.get("analysis", {}).get("min_score_to_select", 35)
    rows = conn.execute(
        """SELECT * FROM items i
           WHERE status = 'found' AND modality IN ('B','C') AND score >= ?
             AND NOT EXISTS (SELECT 1 FROM items j WHERE j.cluster_id = i.cluster_id
                             AND j.status IN ('selected','in_production','produced'))
           ORDER BY score DESC""",
        (min_score,),
    ).fetchall()
    chosen, seen = [], set()
    for r in rows:
        if r["cluster_id"] in seen:
            continue
        seen.add(r["cluster_id"])
        chosen.append(r)
        conn.execute("UPDATE items SET status='selected' WHERE id=?", (r["id"],))
        if len(chosen) >= limit:
            break
    conn.commit()
    return chosen


def ranking(conn: sqlite3.Connection, limit: int = 20, statuses=("found", "review", "selected")) -> list[sqlite3.Row]:
    marks = ",".join("?" * len(statuses))
    return conn.execute(
        f"""SELECT i.*, (SELECT COUNT(DISTINCT source_name) FROM items k WHERE k.cluster_id = i.cluster_id) AS coverage
            FROM items i WHERE status IN ({marks})
              AND i.id = (SELECT j.id FROM items j WHERE j.cluster_id = i.cluster_id ORDER BY j.score DESC, j.id LIMIT 1)
            ORDER BY score DESC LIMIT ?""",
        (*statuses, limit),
    ).fetchall()


def load_config(path) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)
