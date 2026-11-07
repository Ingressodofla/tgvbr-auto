"""Opportunity score (0-100).

Each signal is normalised to 0..1 and combined with weights. Two weight sets
exist because articles have no public counters: video/post items are ranked
mostly by speed of growth, articles mostly by freshness and how many outlets
cover the same story. Weights live in config/sources.json ("scoring") so they
can be tuned with performance data later (stage 5).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

DEFAULT_WEIGHTS = {
    "with_metrics": {
        "velocity": 0.30, "growth": 0.15, "engagement": 0.10, "recency": 0.15,
        "coverage": 0.10, "authority": 0.05, "international": 0.15,
    },
    "without_metrics": {
        "recency": 0.35, "coverage": 0.25, "authority": 0.20, "international": 0.20,
    },
    "velocity_reference_per_hour": 50000,
    "recency_half_life_hours": 24,
}

AUTHORITY = {
    "official_news": 1.0, "press_news": 0.7, "rumor": 0.3,
    "video_trend": 0.5, "community": 0.4,
}


@dataclass
class Snapshot:
    captured_at: datetime
    views: Optional[int]
    likes: Optional[int] = None
    comments: Optional[int] = None
    shares: Optional[int] = None


def _log_norm(value: float, reference: float) -> float:
    if value <= 0:
        return 0.0
    return min(1.0, math.log10(1 + value) / math.log10(1 + reference))


def hours_between(a: datetime, b: datetime) -> float:
    return max((b - a).total_seconds() / 3600.0, 0.25)  # floor: 15 min avoids division blow-ups


def views_per_hour(published_at: datetime, snap: Snapshot) -> Optional[float]:
    if snap.views is None:
        return None
    return snap.views / hours_between(published_at, snap.captured_at)


def growth_per_hour(snapshots: list[Snapshot]) -> Optional[float]:
    with_views = [s for s in snapshots if s.views is not None]
    if len(with_views) < 2:
        return None
    with_views.sort(key=lambda s: s.captured_at)
    prev, last = with_views[-2], with_views[-1]
    return max(0.0, (last.views - prev.views) / hours_between(prev.captured_at, last.captured_at))


def engagement_rate(snap: Snapshot) -> Optional[float]:
    if not snap.views:
        return None
    interactions = sum(x or 0 for x in (snap.likes, snap.comments, snap.shares))
    return interactions / snap.views


def international_signal(language: Optional[str], country: Optional[str]) -> float:
    if country == "BR" or language == "pt":
        return 0.2  # the goal is to bring international content to Brazil first
    if language is None and country is None:
        return 0.7
    return 1.0


def score(
    *,
    published_at: datetime,
    now: datetime,
    relevance: float,
    category: str,
    language: Optional[str],
    country: Optional[str],
    cluster_sources: int,
    snapshots: list[Snapshot],
    weights: dict | None = None,
) -> tuple[float, dict]:
    w = {**DEFAULT_WEIGHTS, **(weights or {})}
    ref = w["velocity_reference_per_hour"]
    signals: dict[str, float] = {
        "recency": 0.5 ** (hours_between(published_at, now) / w["recency_half_life_hours"]),
        "coverage": min(1.0, max(0, cluster_sources - 1) / 4),
        "authority": AUTHORITY.get(category, 0.4),
        "international": international_signal(language, country),
    }
    latest = max(snapshots, key=lambda s: s.captured_at) if snapshots else None
    vph = views_per_hour(published_at, latest) if latest else None
    if vph is not None:
        signals["velocity"] = _log_norm(vph, ref)
        g = growth_per_hour(snapshots)
        signals["growth"] = _log_norm(g, ref) if g is not None else signals["velocity"]
        er = engagement_rate(latest)
        signals["engagement"] = min(1.0, (er or 0.0) / 0.10)
        table = w["with_metrics"]
    else:
        table = w["without_metrics"]
    total = sum(table[k] * signals[k] for k in table)
    final = round(100 * relevance * total, 2)
    breakdown = {k: round(v, 3) for k, v in signals.items()}
    breakdown["relevance"] = relevance
    if vph is not None:
        breakdown["views_per_hour"] = round(vph, 1)
    return final, breakdown
