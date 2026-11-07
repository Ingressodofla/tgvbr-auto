"""Text helpers: normalisation, tokenisation and a small language guesser."""
from __future__ import annotations

import html
import re
import unicodedata

_TAG_RE = re.compile(r"<[^>]+>")
_WORD_RE = re.compile(r"[a-z0-9]+")

STOPWORDS = {
    "en": {
        "the", "and", "is", "are", "of", "to", "in", "for", "on", "with", "this",
        "that", "it", "be", "was", "has", "have", "will", "you", "new", "from",
        "at", "by", "an", "a", "about", "what", "we", "how", "its", "out", "just",
    },
    "pt": {
        "o", "os", "as", "e", "de", "da", "do", "das", "dos", "que", "em", "no",
        "na", "nos", "um", "uma", "para", "com", "por", "mais", "foi", "sao",
        "esta", "voce", "novo", "nova", "sobre", "como", "ja", "tem", "vai", "nao",
    },
    "es": {
        "el", "los", "las", "y", "de", "del", "que", "en", "un", "una", "para",
        "con", "por", "mas", "es", "nuevo", "nueva", "sobre", "como", "ya",
        "tiene", "va", "no", "lo", "se",
    },
}


def strip_html(text: str) -> str:
    return html.unescape(_TAG_RE.sub(" ", text or "")).strip()


def fold(text: str) -> str:
    """Lowercase and remove accents."""
    nfkd = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


def tokens(text: str) -> list[str]:
    return _WORD_RE.findall(fold(text))


def detect_language(text: str) -> str | None:
    """Very small stopword vote between en, pt and es.

    Returns None when the text is too short to decide. It is a ranking hint,
    not a guarantee; declared metadata from the source always wins.
    """
    words = tokens(text)
    if len(words) < 4:
        return None
    votes = {lang: sum(1 for w in words if w in sw) for lang, sw in STOPWORDS.items()}
    best = max(votes, key=votes.get)
    ordered = sorted(votes.values(), reverse=True)
    if ordered[0] == 0 or ordered[0] == ordered[1]:
        return None
    return best
