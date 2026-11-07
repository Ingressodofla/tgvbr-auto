"""Plain data models shared by every module."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Metrics:
    """Public counters as reported by the source at capture time.

    ``None`` means the source does not expose the counter. It is never
    replaced by a guessed 0.
    """

    views: Optional[int] = None
    likes: Optional[int] = None
    comments: Optional[int] = None
    shares: Optional[int] = None
    captured_at: datetime = field(default_factory=utcnow)


@dataclass
class ContentItem:
    """One piece of content found by a source connector."""

    source: str  # youtube | rss | reddit | manual
    source_name: str  # e.g. "IGN", "r/GTA6", "YouTube: gta 6 trailer"
    external_id: str
    url: str
    title: str
    published_at: datetime  # timezone-aware UTC
    author: str = ""
    description: str = ""
    language: Optional[str] = None  # ISO 639-1, declared or detected
    country: Optional[str] = None  # ISO 3166-1 alpha-2, only if the source says so
    media_type: str = "article"  # article | video | short | post | image
    license: Optional[str] = None  # e.g. YouTube "creativeCommon"; None = unknown
    is_official: bool = False  # Rockstar Games / Take-Two owned source
    metrics: Optional[Metrics] = None
    duration_seconds: Optional[int] = None
