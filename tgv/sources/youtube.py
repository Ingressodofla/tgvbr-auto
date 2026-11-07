"""YouTube Data API v3 connector (official API, free with a daily quota).

Quota (default project allocation: 10,000 units/day; check your project in
Google Cloud console): search.list costs 100 units, videos.list costs 1 unit
per call (up to 50 ids). The connector tracks spent units in the database
and stops before the configured daily budget is exceeded.

Credential: environment variable TGV_YOUTUBE_API_KEY (an API key restricted
to the YouTube Data API in Google Cloud). Without it the source is skipped.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta

from tgv.models import ContentItem, Metrics
from tgv.sources.base import SourceNotConfigured, env
from tgv.sources.rss import parse_date

API = "https://www.googleapis.com/youtube/v3"
SEARCH_COST = 100
LIST_COST = 1
SHORT_MAX_SECONDS = 180  # Shorts can be up to 3 minutes; vertical format is not exposed by the API

_DURATION_RE = re.compile(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?")


def parse_duration(text: str | None) -> int | None:
    if not text:
        return None
    m = _DURATION_RE.fullmatch(text)
    if not m:
        return None
    d, h, mi, s = (int(x) if x else 0 for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + s


def _int(value) -> int | None:
    return int(value) if value not in (None, "") else None


class YouTubeSearchConnector:
    """Searches recent videos for each query, then reads statistics in batches."""

    kind = "youtube"

    def __init__(self, queries: list[str], *, region_codes: list[str] | None = None,
                 relevance_language: str = "en", lookback_hours: int = 72,
                 max_results: int = 25, order: str = "viewCount"):
        self.name = "youtube"
        self.queries = queries
        self.region_codes = region_codes or ["US"]
        self.relevance_language = relevance_language
        self.lookback_hours = lookback_hours
        self.max_results = max_results
        self.order = order
        self.units_spent = 0
        self.daily_budget = 6000
        self.budget_left: int | None = None  # set by the pipeline from api_usage

    def _key(self) -> str:
        key = env("TGV_YOUTUBE_API_KEY")
        if not key:
            raise SourceNotConfigured("TGV_YOUTUBE_API_KEY is not set")
        return key

    def _spend(self, units: int) -> bool:
        if self.budget_left is not None and self.units_spent + units > self.budget_left:
            return False
        self.units_spent += units
        return True

    def fetch(self, http, now: datetime) -> list[ContentItem]:
        key = self._key()
        after = (now - timedelta(hours=self.lookback_hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
        found: dict[str, str] = {}  # video id -> query label
        for query in self.queries:
            for region in self.region_codes:
                if not self._spend(SEARCH_COST):
                    break
                data = http.get_json(f"{API}/search", {
                    "part": "snippet", "q": query, "type": "video", "order": self.order,
                    "publishedAfter": after, "regionCode": region,
                    "relevanceLanguage": self.relevance_language,
                    "maxResults": self.max_results, "key": key,
                })
                for entry in data.get("items", []):
                    vid = entry.get("id", {}).get("videoId")
                    if vid:
                        found.setdefault(vid, f"YouTube: {query} [{region}]")
        return self.fetch_videos(http, now, found, key)

    def fetch_videos(self, http, now, ids_to_label: dict[str, str], key: str | None = None) -> list[ContentItem]:
        key = key or self._key()
        ids = list(ids_to_label)
        items: list[ContentItem] = []
        for start in range(0, len(ids), 50):
            if not self._spend(LIST_COST):
                break
            data = http.get_json(f"{API}/videos", {
                "part": "snippet,statistics,contentDetails,status",
                "id": ",".join(ids[start:start + 50]), "key": key,
            })
            for v in data.get("items", []):
                item = self.to_item(v, ids_to_label.get(v["id"], "YouTube"), now)
                if item:
                    items.append(item)
        return items

    @staticmethod
    def to_item(v: dict, label: str, now: datetime) -> ContentItem | None:
        sn, st = v.get("snippet", {}), v.get("statistics", {})
        published = parse_date(sn.get("publishedAt"))
        if not published:
            return None
        duration = parse_duration(v.get("contentDetails", {}).get("duration"))
        lang = sn.get("defaultAudioLanguage") or sn.get("defaultLanguage")
        return ContentItem(
            source="youtube", source_name=label, external_id=v["id"],
            url=f"https://www.youtube.com/watch?v={v['id']}", title=sn.get("title", ""),
            published_at=published, author=sn.get("channelTitle", ""),
            description=(sn.get("description") or "")[:1000],
            language=lang.split("-")[0].lower() if lang else None,
            media_type="short" if duration is not None and duration <= SHORT_MAX_SECONDS else "video",
            license=v.get("status", {}).get("license"),
            duration_seconds=duration,
            metrics=Metrics(
                views=_int(st.get("viewCount")), likes=_int(st.get("likeCount")),
                comments=_int(st.get("commentCount")), captured_at=now,
            ),
        )


def channel_for_handle(http, handle: str) -> dict | None:
    """Resolve a channel handle (e.g. @RockstarGames) to id and title. Costs 1 unit."""
    key = env("TGV_YOUTUBE_API_KEY")
    if not key:
        raise SourceNotConfigured("TGV_YOUTUBE_API_KEY is not set")
    data = http.get_json(f"{API}/channels", {"part": "snippet", "forHandle": handle, "key": key})
    items = data.get("items", [])
    if not items:
        return None
    ch = items[0]
    return {"id": ch["id"], "title": ch["snippet"]["title"], "country": ch["snippet"].get("country"),
            "feed": f"https://www.youtube.com/feeds/videos.xml?channel_id={ch['id']}"}
