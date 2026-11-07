"""Licensed media library: the only place visuals (trailer clips, screenshots) come from.

Every asset is registered in a JSON manifest with where it came from and on what
rights basis it may be used. Nothing is downloaded automatically: the owner adds
files obtained from official channels and registers them (see docs/COMPLIANCE.md).

Rights bases:
- own: footage/screens captured by the page itself.
- licensed: written licence or permission; `reference` is required.
- press_kit: publisher press/media kit; `reference` (terms URL) is required.
- rockstar_fan_policy: Rockstar/Take-Two material used under their fan policy
  (support.rockstargames.com, updated 2025-01-10). That policy covers
  NON-COMMERCIAL use only, so these assets are never commercial_ok and a
  production that uses them must not be monetised.
"""
from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

RIGHTS_BASES = {"own", "licensed", "press_kit", "rockstar_fan_policy"}
NON_COMMERCIAL_BASES = {"rockstar_fan_policy"}
NEEDS_REFERENCE = {"licensed", "press_kit"}
KINDS = {"clip", "image"}
BANNED_TAGS = {"leak", "vazamento", "leaked", "spoiler"}


class LibraryError(ValueError):
    pass


@dataclass
class Asset:
    file: str
    kind: str
    tags: list[str]
    source_url: str
    rights_basis: str
    credit: str
    commercial_ok: bool = False
    start: float = 0.0          # clips: where the usable part starts (seconds)
    duration: float = 30.0      # clips: how many seconds to use in the clip format
    mute: bool = False          # clips: never use this clip's audio (e.g. licensed music)
    reference: str = ""         # licence / terms / permission reference
    notes: str = ""
    extra: dict = field(default_factory=dict)


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    return " ".join(text.casefold().replace("-", " ").split())


def load_library(path: str | Path) -> list[Asset]:
    """Load and validate the manifest. Missing manifest = empty library. Invalid entries raise."""
    path = Path(path)
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    assets, errors = [], []
    for i, raw in enumerate(data.get("assets", [])):
        where = f"assets[{i}] ({raw.get('file', '?')})"
        basis = raw.get("rights_basis", "")
        kind = raw.get("kind", "")
        tags = [_norm(t) for t in raw.get("tags", []) if _norm(t)]
        if basis not in RIGHTS_BASES:
            errors.append(f"{where}: rights_basis must be one of {sorted(RIGHTS_BASES)}")
        if kind not in KINDS:
            errors.append(f"{where}: kind must be clip or image")
        if basis != "own" and not raw.get("source_url"):
            errors.append(f"{where}: source_url is required")
        if basis in NEEDS_REFERENCE and not raw.get("reference"):
            errors.append(f"{where}: reference is required for {basis}")
        if not raw.get("credit"):
            errors.append(f"{where}: credit is required (e.g. 'Rockstar Games')")
        if set(tags) & BANNED_TAGS:
            errors.append(f"{where}: leaked/spoiler material is never used")
        if not tags:
            errors.append(f"{where}: at least one tag is required")
        file = Path(raw.get("file", ""))
        if not file.is_absolute():
            file = path.parent / file
        commercial = bool(raw.get("commercial_ok", basis == "own")) and basis not in NON_COMMERCIAL_BASES
        assets.append(Asset(file=str(file), kind=kind, tags=tags, source_url=raw.get("source_url", ""),
                            rights_basis=basis, credit=raw.get("credit", ""), commercial_ok=commercial,
                            start=float(raw.get("start", 0) or 0),
                            duration=min(60.0, float(raw.get("duration", 30) or 30)),
                            mute=bool(raw.get("mute", False)), reference=raw.get("reference", ""),
                            notes=raw.get("notes", "")))
    if errors:
        raise LibraryError("media library invalid:\n" + "\n".join(errors))
    return assets


def select_assets(assets: list[Asset], text: str, limit: int = 4) -> list[Asset]:
    """Assets with at least one tag in the item text (title + description); more tag hits first,
    then clips before images. Files that are missing on disk are skipped."""
    hay = f" {_norm(text)} "
    scored = []
    for a in assets:
        if not Path(a.file).exists():
            continue
        hits = sum(1 for t in a.tags if f" {t} " in hay)
        if hits:
            scored.append((hits, a.kind == "clip", a))
    scored.sort(key=lambda s: (s[0], s[1]), reverse=True)
    return [a for _, _, a in scored[:limit]]


def rights_summary(assets: list[Asset]) -> tuple[str | None, bool]:
    """(rights_basis text for productions.rights_basis, commercial_ok for the whole production)."""
    if not assets:
        return None, True
    parts = sorted({f"{a.rights_basis}: {a.source_url or a.file}" for a in assets})
    return "; ".join(parts), all(a.commercial_ok for a in assets)


def credits(assets: list[Asset]) -> str:
    seen: list[str] = []
    for a in assets:
        if a.credit not in seen:
            seen.append(a.credit)
    return ", ".join(seen)
