"""Duplicate detection.

Two levels:
1. Same URL: canonical keys collapse tracking parameters and the many URL
   shapes of YouTube and Reddit, so the same video or post is stored once.
2. Same story: different outlets covering one event are grouped in a cluster
   by title similarity inside a time window. The cluster size is a trend
   signal (coverage), and only the best item of a cluster is worked on.
"""
from __future__ import annotations

import re
from datetime import timedelta
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from tgv.textutil import STOPWORDS, tokens

_TRACKING_PREFIXES = ("utm_", "mc_")
_TRACKING_NAMES = {"fbclid", "gclid", "igshid", "si", "feature", "ref", "ref_src"}
_YT_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
_REDDIT_RE = re.compile(r"/comments/([a-z0-9]+)", re.I)

# Words every GTA VI headline shares; they carry no information for clustering.
_GENERIC = {"gta", "6", "vi", "grand", "theft", "auto", "rockstar", "games", "game"}
_STOP = set().union(*STOPWORDS.values()) | _GENERIC


def canonical_key(url: str) -> str:
    parts = urlsplit(url.strip())
    host = parts.netloc.lower()
    for prefix in ("www.", "m.", "old.", "new."):
        if host.startswith(prefix):
            host = host[len(prefix):]
    path = parts.path.rstrip("/")

    if host in ("youtube.com", "youtu.be", "youtube-nocookie.com"):
        video_id = None
        if host == "youtu.be":
            video_id = path.lstrip("/").split("/")[0]
        elif path == "/watch":
            video_id = dict(parse_qsl(parts.query)).get("v")
        elif path.startswith(("/shorts/", "/embed/", "/live/")):
            video_id = path.split("/")[2]
        if video_id and _YT_ID_RE.match(video_id):
            return f"youtube:{video_id}"

    if host.endswith("reddit.com") or host == "redd.it":
        if host == "redd.it":
            return f"reddit:{path.lstrip('/').lower()}"
        m = _REDDIT_RE.search(path)
        if m:
            return f"reddit:{m.group(1).lower()}"

    query = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=False)
        if not k.lower().startswith(_TRACKING_PREFIXES) and k.lower() not in _TRACKING_NAMES
    ]
    query.sort()
    return urlunsplit(("https", host, path, urlencode(query), ""))


def title_signature(title: str) -> frozenset[str]:
    return frozenset(t for t in tokens(title) if t not in _STOP and len(t) > 1)


def similarity(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def assign_clusters(items, threshold: float = 0.5, window_hours: int = 72):
    """Group items (objects with ``id``, ``title``, ``published_at``) into stories.

    Returns {item_id: cluster_id}; the cluster id is the id of the oldest item.
    Titles with fewer than 3 informative words only cluster on an exact match.
    """
    ordered = sorted(items, key=lambda i: (i.published_at, i.id))
    clusters: list[tuple[int, frozenset[str], object]] = []  # (cluster_id, sig, first_item)
    result: dict[int, int] = {}
    window = timedelta(hours=window_hours)
    for item in ordered:
        sig = title_signature(item.title)
        chosen = None
        for cluster_id, csig, first in clusters:
            if abs(item.published_at - first.published_at) > window:
                continue
            short = min(len(sig), len(csig)) < 3
            if (short and sig == csig and sig) or (not short and similarity(sig, csig) >= threshold):
                chosen = cluster_id
                break
        if chosen is None:
            chosen = item.id
            clusters.append((item.id, sig, item))
        result[item.id] = chosen
    return result
