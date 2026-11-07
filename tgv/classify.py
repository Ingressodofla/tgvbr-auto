"""Editorial classification: relevance, claim status, category, modality, review flags.

Rules (see docs/COMPLIANCE.md):
- Only official Rockstar Games / Take-Two sources produce "confirmed" claims.
- Press coverage is "reported": it can be published as news with attribution.
- Rumour, leak or speculation wording makes a claim "unverified": it can only
  be covered as a rumour, clearly labelled, and always goes to human review.
- Reuse of third-party media (modality A) is never automatic: it needs a
  documented licence or permission for the intended use, monetisation included.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from tgv.models import ContentItem
from tgv.textutil import fold

_STRONG = re.compile(
    r"\bgta\s*-?\s*(?:6|vi)\b|grand theft auto\s*(?:6|vi)\b|#gta6\b|#gtavi\b", re.I
)
_WEAK = re.compile(r"\bleonida\b|\bvice city\b|\blucia\b.*\bjason\b|\bjason\b.*\blucia\b", re.I)
_GTA_ANY = re.compile(r"\bgta\b|grand theft auto", re.I)
_ROCKSTAR = re.compile(r"\brockstar\b", re.I)
_OTHER_GTA = re.compile(r"\bgta\s*-?\s*(?:5|v|iv|4|online|trilogy)\b", re.I)

_RUMOR = re.compile(
    r"\b(rumou?rs?|rumou?red|leak(?:s|ed)?|insiders?|reportedly|allegedly|unconfirmed|"
    r"speculat\w*|theory|theories|could be|might be|may have|claims?|"
    r"boatos?|vazamentos?|vazad[oa]s?|suposto|supostamente|teoria)\b",
    re.I,
)
_LEAK = re.compile(r"\b(leak(?:s|ed)?|vazamentos?|vazad[oa]s?|datamin\w*)\b", re.I)
_NEWS_HINT = re.compile(
    r"\b(announc\w*|confirm\w*|release date|delay\w*|trailer|pre-?orders?|price|"
    r"earnings|take-two|statement|official)\b",
    re.I,
)

REUSABLE_LICENSES = {"creativeCommon"}  # still needs human confirmation (footage inside may be Rockstar's)


@dataclass
class Classification:
    relevance: float
    category: str  # official_news | press_news | rumor | video_trend | community
    claim_status: str  # confirmed | reported | unverified | not_a_claim
    modality: str  # A_candidate | B | C | skip
    flags: list[str] = field(default_factory=list)


def relevance(text: str) -> float:
    if _STRONG.search(text):
        return 1.0
    if _WEAK.search(text) and (_GTA_ANY.search(text) or _ROCKSTAR.search(text)):
        return 0.6
    if _GTA_ANY.search(text) and not _OTHER_GTA.search(text):
        return 0.3
    return 0.0


def classify(item: ContentItem) -> Classification:
    text = f"{item.title}\n{item.description}"
    rel = relevance(text)
    flags: list[str] = []
    rumor = bool(_RUMOR.search(fold(item.title))) or bool(_RUMOR.search(fold(item.description[:400])))
    leak = bool(_LEAK.search(fold(text)))

    if item.is_official:
        category, claim = "official_news", "confirmed"
    elif rumor:
        category, claim = "rumor", "unverified"
    elif item.media_type == "article":
        category, claim = "press_news", "reported"
    elif item.source == "reddit":
        category, claim = "community", "not_a_claim"
    else:
        category, claim = "video_trend", "not_a_claim"

    if claim == "unverified":
        flags.append("unverified_claim")
    if leak:
        flags.append("leak_content")  # never reuse; covering it needs review
    if item.language == "pt" or item.country == "BR":
        flags.append("brazilian_source")

    if rel == 0.0:
        modality = "skip"
    elif category in ("official_news", "press_news") or (
        category == "rumor" and _NEWS_HINT.search(text)
    ):
        modality = "C"
    else:
        modality = "B"

    # Modality A is only ever a candidate, and only with a reusable licence.
    if item.license in REUSABLE_LICENSES and not leak and rel > 0:
        modality = "A_candidate"
        flags.append("license_review")
    if item.media_type in ("video", "short", "image") and modality != "A_candidate":
        flags.append("third_party_media")  # reference only, do not reupload

    return Classification(rel, category, claim, modality, flags)


def needs_review(c: Classification) -> bool:
    return any(f in c.flags for f in ("unverified_claim", "leak_content", "license_review"))
