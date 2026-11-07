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


def load_brand(path: str | Path) -> Brand:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return Brand(
        name=data["name"], colors=data["colors"], fonts=data["fonts"], video=data["video"],
        voice=data.get("voice", {}), handle=data.get("handle", ""), logo_path=data.get("logo_path", ""),
        provisional=bool(data.get("provisional", True)),
    )


def hex_to_rgb(color: str) -> tuple[int, int, int]:
    c = color.lstrip("#")
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def hex_to_ass(color: str, alpha: int = 0) -> str:
    """#RRGGBB -> ASS &HAABBGGRR."""
    r, g, b = hex_to_rgb(color)
    return f"&H{alpha:02X}{b:02X}{g:02X}{r:02X}"
