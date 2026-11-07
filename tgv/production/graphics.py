"""Covers (1080x1920) and carousel slides (1080x1350) with Pillow."""
from __future__ import annotations

from pathlib import Path

from tgv.production.brand import Brand, hex_to_rgb
from tgv.production.render import STATUS_TAG
from tgv.production.script import ScriptDraft


def _pil():
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Pillow not installed (pip install -r requirements.txt)") from exc
    return Image, ImageDraw, ImageFont


def _gradient(size, top, bottom):
    Image, _, _ = _pil()
    w, h = size
    t, b = hex_to_rgb(top), hex_to_rgb(bottom)
    column = Image.new("RGB", (1, h))
    column.putdata([tuple(int(t[i] + (b[i] - t[i]) * y / (h - 1)) for i in range(3)) for y in range(h)])
    return column.resize((w, h))


def _wrap(draw, text, font, max_width):
    words, lines, cur = text.split(), [], ""
    for wd in words:
        trial = f"{cur} {wd}".strip()
        if draw.textlength(trial, font=font) <= max_width or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    return lines


def _fit(draw, text, font_path, max_width, max_lines, start, minimum):
    _, _, ImageFont = _pil()
    size = start
    while size >= minimum:
        font = ImageFont.truetype(font_path, size)
        lines = _wrap(draw, text, font, max_width)
        if len(lines) <= max_lines:
            return font, lines
        size -= 6
    font = ImageFont.truetype(font_path, minimum)
    return font, _wrap(draw, text, font, max_width)[:max_lines]


def _frame(brand: Brand, size, claim_status: str):
    Image, ImageDraw, ImageFont = _pil()
    img = _gradient(size, brand.color("background_top"), brand.color("background_bottom"))
    d = ImageDraw.Draw(img)
    w, _ = size
    d.rectangle([0, 0, w, 110], fill=(0, 0, 0))
    d.text((60, 32), brand.label(), font=ImageFont.truetype(brand.fonts["body"], 44), fill="white")
    tag, color_key = STATUS_TAG.get(claim_status, STATUS_TAG["not_a_claim"])
    tag_font = ImageFont.truetype(brand.fonts["body"], 40)
    tw = d.textlength(tag, font=tag_font)
    d.rectangle([w - tw - 96, 150, w - 60, 218], fill=brand.color(color_key))
    d.text((w - tw - 78, 160), tag, font=tag_font, fill="black")
    d.rectangle([60, size[1] - 40, w - 60, size[1] - 30], fill=brand.color("accent"))
    if brand.logo_path and Path(brand.logo_path).exists():
        logo = Image.open(brand.logo_path).convert("RGBA")
        logo.thumbnail((200, 90))
        img.paste(logo, (w - logo.width - 40, 10), logo)
    return img, d


def cover(draft: ScriptDraft, brand: Brand, out: Path, source_name: str, size=(1080, 1920)) -> Path:
    _, _, ImageFont = _pil()
    img, d = _frame(brand, size, draft.claim_status)
    w, h = size
    font, lines = _fit(d, draft.cover_text.upper(), brand.fonts["headline"], w - 140, 4, 150, 80)
    line_h = int(font.size * 1.08)
    y = int(h * 0.36) - (line_h * len(lines)) // 2
    for line in lines:
        d.text((70, y), line, font=font, fill="white", stroke_width=4, stroke_fill="black")
        y += line_h
    d.rectangle([70, y + 20, 270, y + 34], fill=brand.color("accent"))
    sub_font, sub_lines = _fit(d, draft.title, brand.fonts["body"], w - 140, 4, 54, 40)
    y += 70
    for line in sub_lines:
        d.text((70, y), line, font=sub_font, fill=(230, 230, 240))
        y += int(sub_font.size * 1.25)
    d.text((70, h - 120), f"Fonte: {source_name}", font=ImageFont.truetype(brand.fonts["body"], 36),
           fill=(200, 200, 215))
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "JPEG", quality=92)
    return out


def carousel(draft: ScriptDraft, brand: Brand, out_dir: Path, source_name: str) -> list[Path]:
    """Instagram carousel (4:5). Slide 1 = cover, then one slide per segment."""
    _, _, ImageFont = _pil()
    size = (1080, 1350)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = [cover(draft, brand, out_dir / "slide_01.jpg", source_name, size=size)]
    for i, seg in enumerate(draft.segments, start=2):
        img, d = _frame(brand, size, draft.claim_status)
        w, h = size
        hf, hl = _fit(d, seg.on_screen.upper(), brand.fonts["headline"], w - 140, 2, 96, 60)
        y = 280
        for line in hl:
            d.text((70, y), line, font=hf, fill=brand.color("accent"))
            y += int(hf.size * 1.1)
        bf, bl = _fit(d, seg.narration, brand.fonts["body"], w - 140, 9, 54, 38)
        y += 40
        for line in bl:
            d.text((70, y), line, font=bf, fill="white")
            y += int(bf.size * 1.3)
        d.text((70, h - 110), f"{i}/{len(draft.segments) + 1} · Fonte: {source_name}",
               font=ImageFont.truetype(brand.fonts["body"], 32), fill=(200, 200, 215))
        p = out_dir / f"slide_{i:02d}.jpg"
        img.save(p, "JPEG", quality=92)
        paths.append(p)
    return paths
