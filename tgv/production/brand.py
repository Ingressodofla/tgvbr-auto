"""Brand kit loader. One config file drives every template, so the look stays consistent."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Brand:
    name: str
    colors: dict
    fonts: dict
    video: dict
    voice: dict
    handle: str = ""
    logo_path: str = ""
    provisional: bool = True
    hashtags: dict = field(default_factory=dict)
    extra: dict = field(default_factory=dict)

    @property
    def width(self) -> int:
        return int(self.video.get("width", 1080))

    @property
    def height(self) -> int:
        return int(self.video.get("height", 1920))

    @property
    def fps(self) -> int:
        return int(self.video.get("fps", 30))

    def color(self, key: str) -> str:
        return self.colors[key]

    def label(self) -> str:
        return self.handle or self.name


def _resolve(value: str, root: Path) -> str:
    if not value:
        return value
    p = Path(value)
    return str(p if p.is_absolute() else (root / p).resolve())


def load_brand(path: str | Path) -> Brand:
    """Load config/brand.json; relative paths are resolved from the repository root."""
    path = Path(path).resolve()
    root = path.parent.parent
    data = json.loads(path.read_text(encoding="utf-8"))
    fonts = dict(data["fonts"])
    for key in ("headline", "body", "fonts_dir"):
        fonts[key] = _resolve(fonts.get(key, ""), root)
    voice = dict(data.get("voice", {}))
    if voice.get("piper_model"):
        voice["piper_model"] = _resolve(voice["piper_model"], root)
    return Brand(
        name=data["name"], colors=data["colors"], fonts=fonts, video=data["video"],
        voice=voice, handle=data.get("handle", ""), logo_path=_resolve(data.get("logo_path", ""), root),
        provisional=bool(data.get("provisional", True)), hashtags=dict(data.get("hashtags", {})),
    )


def _tag(text: str) -> str:
    import unicodedata

    t = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return "".join(ch for ch in t.lower() if ch.isalnum() or ch == "_")


def final_hashtags(topic: list[str], brand: Brand) -> list[str]:
    """Topic tags from the writer first, then the page's fixed tags; lowercase, no '#', no duplicates."""
    always = [_tag(t) for t in brand.hashtags.get("always", [])]
    limit = int(brand.hashtags.get("max", 8))
    out: list[str] = []
    for t in [_tag(x) for x in topic][: max(0, limit - len(always))] + always:
        if t and t not in out:
            out.append(t)
    return out[:limit]


def hex_to_rgb(color: str) -> tuple[int, int, int]:
    c = color.lstrip("#")
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def hex_to_ass(color: str, alpha: int = 0) -> str:
    """#RRGGBB -> ASS &HAABBGGRR."""
    r, g, b = hex_to_rgb(color)
    return f"&H{alpha:02X}{b:02X}{g:02X}{r:02X}"
