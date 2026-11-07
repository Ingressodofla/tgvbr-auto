"""Synchronised captions as an ASS file (rendered by FFmpeg/libass).

Timing: every script segment is synthesised separately, so segment start/end
times are exact. Inside a segment, captions are split into short chunks
(<= 4 words) and timed proportionally to their character length, which keeps
them within a fraction of a second of the voice for TTS narration. If word-level
precision is ever needed (e.g. a human voice-over), align with faster-whisper
and pass the word times to build_ass() instead.
"""
from __future__ import annotations

from dataclasses import dataclass

from tgv.production.brand import Brand, hex_to_ass


@dataclass
class Cue:
    start: float
    end: float
    text: str
    style: str  # Caption | Headline | Tag


def chunk_words(text: str, max_words: int = 4, max_chars: int = 26) -> list[str]:
    words, chunks, cur = text.split(), [], []
    for w in words:
        candidate = " ".join(cur + [w])
        if cur and (len(cur) >= max_words or len(candidate) > max_chars):
            chunks.append(" ".join(cur))
            cur = [w]
        else:
            cur.append(w)
    if cur:
        chunks.append(" ".join(cur))
    return chunks


def caption_cues(segments: list[tuple[str, str, float, float]]) -> list[Cue]:
    """segments: (narration, on_screen, start, end) -> caption + headline cues."""
    cues: list[Cue] = []
    for narration, on_screen, start, end in segments:
        cues.append(Cue(start, end, on_screen.upper(), "Headline"))
        chunks = chunk_words(narration)
        total = sum(len(c) for c in chunks) or 1
        t = start
        for c in chunks:
            d = (end - start) * len(c) / total
            cues.append(Cue(t, t + d, c, "Caption"))
            t += d
    return cues


def headline_cues(on_screen: list[str], total: float) -> list[Cue]:
    """Clip format: no narration, the on-screen texts share the duration evenly."""
    texts = [t for t in on_screen if t.strip()] or [""]
    step = total / len(texts)
    return [Cue(i * step, (i + 1) * step, t.upper(), "Headline") for i, t in enumerate(texts)]


def timed_caption_cues(lines) -> list[Cue]:
    """Translated speech (objects with start/end/text) -> short caption chunks inside each line's time."""
    cues: list[Cue] = []
    for line in lines:
        chunks = chunk_words(line.text, max_words=6, max_chars=36)
        total = sum(len(c) for c in chunks) or 1
        t = line.start
        for c in chunks:
            d = (line.end - line.start) * len(c) / total
            cues.append(Cue(t, t + d, c, "Caption"))
            t += d
    return cues


def _ts(seconds: float) -> str:
    cs = int(round(max(0.0, seconds) * 100))
    h, rem = divmod(cs, 360000)
    m, rem = divmod(rem, 6000)
    s, cs = divmod(rem, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("{", "(").replace("}", ")").replace("\n", " ")


def build_ass(cues: list[Cue], brand: Brand) -> str:
    font = brand.fonts.get("family_for_captions", "Inter")
    white = hex_to_ass(brand.color("text"))
    accent = hex_to_ass(brand.color("accent"))
    black = hex_to_ass("#000000")
    shadow = hex_to_ass("#000000", alpha=0x60)
    w, h = brand.width, brand.height
    styles = [
        # Name, Font, Size, Primary, Secondary, Outline, Back, Bold, Italic, Underline, Strike,
        # ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
        # Caption sits just above the bottom black band; Headline is the yellow box (BorderStyle 3)
        # with black text inside the top band, like the page's covers.
        f"Style: Caption,{font},92,{white},{white},{black},{shadow},-1,0,0,0,100,100,0,0,1,7,3,2,90,90,{int(h * 0.20) + 50},1",
        f"Style: Headline,{font},68,{black},{black},{accent},{accent},-1,0,0,0,100,100,1,0,3,20,0,8,110,110,{int(h * 0.075)},1",
        f"Style: Tag,{font},44,{white},{white},{black},{shadow},-1,0,0,0,100,100,2,0,1,3,2,8,60,60,150,1",
    ]
    lines = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {w}", f"PlayResY: {h}",
        "WrapStyle: 0", "ScaledBorderAndShadow: yes", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, "
        "Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding",
        *styles, "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for c in cues:
        text = _escape(c.text)
        if c.style == "Caption":
            text = r"{\fad(60,40)\t(0,120,\fscx108\fscy108)\t(120,220,\fscx100\fscy100)}" + text
        elif c.style == "Headline":
            text = r"{\fad(150,150)}" + text
        lines.append(f"Dialogue: 0,{_ts(c.start)},{_ts(c.end)},{c.style},,0,0,0,,{text}")
    return "\n".join(lines) + "\n"
