"""Reddit connector (official OAuth API, application-only).

Reddit requires a registered app and an approved use case for API access;
commercial use needs a separate agreement with Reddit. This connector is
DISABLED in config until access is granted. Credentials come from
TGV_REDDIT_CLIENT_ID and TGV_REDDIT_CLIENT_SECRET (environment only).
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone

from tgv.models import ContentItem, Metrics
from tgv.sources.base import SourceNotConfigured, env

AUTH_URL = "https://www.reddit.com/api/v1/access_token"
API = "https://oauth.reddit.com"


class RedditConnector:
    kind = "reddit"

    def __init__(self, subreddits: list[str], *, listing: str = "hot", limit: int = 50):
        self.name = "reddit"
        self.subreddits = subreddits
        self.listing = listing
        self.limit = limit

    def _bearer(self, http) -> str:
        client_id, client_pw = env("TGV_REDDIT_CLIENT_ID"), env("TGV_REDDIT_CLIENT_SECRET")
        if not client_id or not client_pw:
            raise SourceNotConfigured("TGV_REDDIT_CLIENT_ID / TGV_REDDIT_CLIENT_SECRET are not set")
        basic = base64.b64encode(f"{client_id}:{client_pw}".encode()).decode()
        data = http.post_form(AUTH_URL, {"grant_type": "client_credentials"},
                              {"Authorization": f"Basic {basic}"})
        return data["access_token"]

    def fetch(self, http, now: datetime) -> list[ContentItem]:
        headers = {"Authorization": f"Bearer {self._bearer(http)}"}
        items = []
        for sub in self.subreddits:
            data = http.get_json(f"{API}/r/{sub}/{self.listing}", {"limit": self.limit, "raw_json": 1}, headers)
            for child in data.get("data", {}).get("children", []):
                item = self.to_item(child.get("data", {}), sub, now)
                if item:
                    items.append(item)
        return items

    @staticmethod
    def to_item(p: dict, sub: str, now: datetime) -> ContentItem | None:
        if not p.get("id") or p.get("stickied") or p.get("over_18"):
            return None
        return ContentItem(
            source="reddit", source_name=f"r/{sub}", external_id=p["id"],
            url=f"https://www.reddit.com{p.get('permalink', '')}", title=p.get("title", ""),
            published_at=datetime.fromtimestamp(p.get("created_utc", 0), tz=timezone.utc),
            author=p.get("author", ""), description=(p.get("selftext") or "")[:1000],
            media_type="video" if p.get("is_video") else ("image" if p.get("post_hint") == "image" else "post"),
            # Reddit exposes score (net votes) and comments; no public view count.
            metrics=Metrics(views=None, likes=p.get("score"), comments=p.get("num_comments"), captured_at=now),
        )
