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


# Layout mirrors the page's best-performing posts: black letterbox bands, a yellow
# rounded box with the black headline on top, a white sub-line, the visual in the
# middle and the logo as a small watermark at the bottom.
TOP_BAND = 0.30     # fraction of the height
BOTTOM_BAND = 0.80  # bottom band starts here


def _logo(brand: Brand, box):
    Image, _, _ = _pil()
    if not (brand.logo_path and Path(brand.logo_path).exists()):
        return None
    logo = Image.open(brand.logo_path).convert("RGBA")
    logo.thumbnail(box)
    return logo


def _frame(brand: Brand, size, claim_status: str, image: Path | None = None, faded_logo: bool = True):
    """Background (gradient + optional visual), letterbox bands, status pill and logo watermark."""
    Image, ImageDraw, ImageFont = _pil()
    w, h = size
    top, bottom = int(h * TOP_BAND), int(h * BOTTOM_BAND)
    img = _gradient(size, brand.color("background_top"), brand.color("background_bottom")).convert("RGBA")
    if image and Path(image).exists():
        from PIL import ImageEnhance, ImageFilter

        vis = Image.open(image).convert("RGBA")
        fill = max(w / vis.width, h / vis.height)
        back = vis.resize((int(vis.width * fill) + 1, int(vis.height * fill) + 1))
        left, upper = (back.width - w) // 2, (back.height - h) // 2
        back = back.crop((left, upper, left + w, upper + h)).filter(ImageFilter.GaussianBlur(40))
        img = ImageEnhance.Brightness(back).enhance(0.75)
        fit = min(w / vis.width, (bottom - top) / vis.height)
        front = vis.resize((int(vis.width * fit), int(vis.height * fit)))
        img.alpha_composite(front, ((w - front.width) // 2, top + (bottom - top - front.height) // 2))
    elif faded_logo:
        big = _logo(brand, (int(w * 0.62), int((bottom - top) * 0.78)))
        if big:
            faded = big.copy()
            faded.putalpha(faded.getchannel("A").point(lambda a: a * 30 // 100))
            img.alpha_composite(faded, ((w - big.width) // 2, top + (bottom - top - big.height) // 2))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, w, top], fill=(0, 0, 0))
    d.rectangle([0, bottom, w, h], fill=(0, 0, 0))

    tag, color_key = STATUS_TAG.get(claim_status, STATUS_TAG["not_a_claim"])
    tag_font = ImageFont.truetype(brand.fonts["body"], max(26, int(h * 0.018)))
    tw = d.textlength(tag, font=tag_font)
    ty = int(h * 0.025)
    pad = tag_font.size // 2
    d.rounded_rectangle([(w - tw) / 2 - pad * 2, ty, (w + tw) / 2 + pad * 2, ty + tag_font.size + pad * 2],
                        radius=tag_font.size, fill=brand.color(color_key))
    d.text((w / 2, ty + pad + tag_font.size / 2), tag, font=tag_font, fill="black", anchor="mm")

    mark = _logo(brand, (int(w * 0.16), int((h - bottom) * 0.42)))
    if mark:
        img.alpha_composite(mark, ((w - mark.width) // 2, bottom + int((h - bottom) * 0.12)))
    handle_font = ImageFont.truetype(brand.fonts["body"], max(24, int(h * 0.016)))
    d.text((w / 2, bottom + int((h - bottom) * 0.66)), brand.label(), font=handle_font,
           fill=(235, 235, 240), anchor="mm")
    return img, d


def _headline_box(d, brand: Brand, text: str, w: int, y: int, max_h: int) -> int:
    """Yellow rounded box with the black headline, centred. Returns the bottom y."""
    font, lines = _fit(d, text.upper(), brand.fonts["headline"], w - 200, 3, int(max_h * 0.34), 44)
    line_h = int(font.size * 1.12)
    widest = max(d.textlength(line, font=font) for line in lines)
    pad_x, pad_y = int(font.size * 0.45), int(font.size * 0.28)
    box_h = line_h * len(lines) + pad_y * 2
    d.rounded_rectangle([(w - widest) / 2 - pad_x, y, (w + widest) / 2 + pad_x, y + box_h],
                        radius=int(font.size * 0.35), fill=brand.color("accent"))
    ty = y + pad_y + line_h / 2
    for line in lines:
        d.text((w / 2, ty), line, font=font, fill="black", anchor="mm")
        ty += line_h
    return y + box_h


def cover(draft: ScriptDraft, brand: Brand, out: Path, source_name: str, size=(1080, 1920),
          image: Path | None = None) -> Path:
    _, _, ImageFont = _pil()
    img, d = _frame(brand, size, draft.claim_status, image)
    w, h = size
    top = int(h * TOP_BAND)
    y = int(h * 0.075)
    y = _headline_box(d, brand, draft.cover_text, w, y, top - y - int(h * 0.09))
    sub_font, sub_lines = _fit(d, draft.title.upper(), brand.fonts["body"], w - 160, 2, max(30, int(h * 0.024)), 26)
    y += int(sub_font.size * 0.9)
    for line in sub_lines:
        if y + sub_font.size > top - 8:
            break
        d.text((w / 2, y), line, font=sub_font, fill="white", anchor="mt")
        y += int(sub_font.size * 1.2)
    src_font = ImageFont.truetype(brand.fonts["body"], max(22, int(h * 0.014)))
    d.text((w / 2, int(h * BOTTOM_BAND) - 14), f"Fonte: {source_name}", font=src_font,
           fill="white", anchor="mb", stroke_width=3, stroke_fill="black")
    out.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(out, "JPEG", quality=92)
    return out


def carousel(draft: ScriptDraft, brand: Brand, out_dir: Path, source_name: str,
             image: Path | None = None) -> list[Path]:
    """Instagram carousel (4:5). Slide 1 = cover, then one slide per segment."""
    _, _, ImageFont = _pil()
    size = (1080, 1350)
    w, h = size
    top, bottom = int(h * TOP_BAND), int(h * BOTTOM_BAND)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = [cover(draft, brand, out_dir / "slide_01.jpg", source_name, size=size, image=image)]
    for i, seg in enumerate(draft.segments, start=2):
        img, d = _frame(brand, size, draft.claim_status, faded_logo=False)
        _headline_box(d, brand, seg.on_screen, w, int(h * 0.075), top - int(h * 0.11))
        bf, bl = _fit(d, seg.narration, brand.fonts["body"], w - 140, 8, 54, 34)
        line_h = int(bf.size * 1.3)
        y = top + (bottom - top - line_h * len(bl)) // 2
        for line in bl:
            d.text((70, y), line, font=bf, fill="white")
            y += line_h
        d.text((w / 2, bottom - 14), f"{i}/{len(draft.segments) + 1} · Fonte: {source_name}",
               font=ImageFont.truetype(brand.fonts["body"], 28), fill=(200, 200, 215), anchor="mb")
        p = out_dir / f"slide_{i:02d}.jpg"
        img.convert("RGB").save(p, "JPEG", quality=92)
        paths.append(p)
    return paths
