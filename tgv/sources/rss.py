"""RSS 2.0 / Atom connector (news sites, Google News queries, YouTube channel feeds).

No credentials, no quota. YouTube channel feeds
(https://www.youtube.com/feeds/videos.xml?channel_id=...) include a public
view count in ``media:statistics``, so official channels can be followed
without spending YouTube Data API quota.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from tgv.models import ContentItem, Metrics
from tgv.textutil import strip_html

NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "media": "http://search.yahoo.com/mrss/",
    "yt": "http://www.youtube.com/xml/schemas/2015",
    "dc": "http://purl.org/dc/elements/1.1/",
}


def parse_date(text: str | None) -> datetime | None:
    if not text:
        return None
    text = text.strip()
    try:
        dt = parsedate_to_datetime(text)
    except (TypeError, ValueError):
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _text(el, path: str) -> str:
    found = el.find(path, NS)
    return (found.text or "").strip() if found is not None and found.text else ""


class RssConnector:
    kind = "rss"

    def __init__(self, name: str, url: str, *, official: bool = False,
                 language: str | None = None, country: str | None = None, max_items: int = 50):
        self.name = name
        self.url = url
        self.official = official
        self.language = language
        self.country = country
        self.max_items = max_items

    def fetch(self, http, now):
        return self.parse(http.get_text(self.url), now)

    def parse(self, xml_text: str, now: datetime) -> list[ContentItem]:
        root = ET.fromstring(xml_text.encode("utf-8") if isinstance(xml_text, str) else xml_text)
        if root.tag == f"{{{NS['atom']}}}feed":
            entries = [self._atom(e, now) for e in root.findall("atom:entry", NS)]
        else:
            entries = [self._rss(e) for e in root.iter("item")]
        items = [e for e in entries if e is not None]
        return items[: self.max_items]

    def _base(self, **kw) -> ContentItem:
        return ContentItem(
            source="rss", source_name=self.name, is_official=self.official,
            language=self.language, country=self.country, **kw,
        )

    def _rss(self, el) -> ContentItem | None:
        link = _text(el, "link")
        title = strip_html(_text(el, "title"))
        published = parse_date(_text(el, "pubDate") or _text(el, "dc:date"))
        if not link or not title or not published:
            return None
        return self._base(
            external_id=_text(el, "guid") or link, url=link, title=title,
            published_at=published, author=_text(el, "dc:creator") or _text(el, "author"),
            description=strip_html(_text(el, "description"))[:1000], media_type="article",
        )

    def _atom(self, el, now) -> ContentItem | None:
        link_el = el.find("atom:link[@rel='alternate']", NS)
        if link_el is None:
            link_el = el.find("atom:link", NS)
        link = link_el.get("href") if link_el is not None else ""
        title = strip_html(_text(el, "atom:title"))
        published = parse_date(_text(el, "atom:published") or _text(el, "atom:updated"))
        if not link or not title or not published:
            return None
        video_id = _text(el, "yt:videoId")
        metrics = None
        description = strip_html(_text(el, "atom:summary") or _text(el, "atom:content"))
        group = el.find("media:group", NS)
        if group is not None:
            description = description or _text(group, "media:description")
            stats = group.find("media:community/media:statistics", NS)
            rating = group.find("media:community/media:starRating", NS)
            if stats is not None and stats.get("views"):
                metrics = Metrics(
                    views=int(stats.get("views")),
                    likes=int(rating.get("count")) if rating is not None and rating.get("count") else None,
                    captured_at=now,
                )
        is_video = bool(video_id)
        return self._base(
            external_id=video_id or _text(el, "atom:id") or link, url=link, title=title,
            published_at=published, author=_text(el, "atom:author/atom:name"),
            description=description[:1000],
            media_type="short" if "/shorts/" in link else ("video" if is_video else "article"),
            metrics=metrics,
        )
