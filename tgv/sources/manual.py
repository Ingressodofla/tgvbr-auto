"""Manual CSV import: the documented fallback for TikTok and Instagram.

Neither platform offers a commercial API to discover other creators' trending
content (see docs/PLATFORM_LIMITS.md). Links found by a person (or exported
from an authorised monitoring tool) are imported here and then ranked with
everything else.

CSV columns (header required): url,title,platform,published_at[,author,views,
likes,comments,shares,language,country,license]
published_at: ISO 8601 (e.g. 2026-11-06T14:00:00Z).
"""
from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from tgv.models import ContentItem, Metrics
from tgv.sources.rss import parse_date

REQUIRED = ("url", "title", "platform", "published_at")


def _opt_int(row: dict, key: str) -> int | None:
    value = (row.get(key) or "").replace(".", "").replace(",", "").strip()
    return int(value) if value.isdigit() else None


def load_csv(path: str | Path, now: datetime) -> tuple[list[ContentItem], list[str]]:
    items, errors = [], []
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        missing = [c for c in REQUIRED if c not in (reader.fieldnames or [])]
        if missing:
            return [], [f"missing columns: {', '.join(missing)}"]
        for n, row in enumerate(reader, start=2):
            published = parse_date(row["published_at"])
            if not row["url"].strip() or not row["title"].strip() or not published:
                errors.append(f"line {n}: url, title and a valid published_at are required")
                continue
            platform = row["platform"].strip().lower()
            items.append(ContentItem(
                source="manual", source_name=f"manual:{platform}", external_id=row["url"].strip(),
                url=row["url"].strip(), title=row["title"].strip(), published_at=published,
                author=(row.get("author") or "").strip(),
                language=(row.get("language") or "").strip().lower() or None,
                country=(row.get("country") or "").strip().upper() or None,
                license=(row.get("license") or "").strip() or None,
                media_type="short" if platform in ("tiktok", "instagram", "shorts") else "video",
                metrics=Metrics(
                    views=_opt_int(row, "views"), likes=_opt_int(row, "likes"),
                    comments=_opt_int(row, "comments"), shares=_opt_int(row, "shares"),
                    captured_at=now,
                ),
            ))
    return items, errors
