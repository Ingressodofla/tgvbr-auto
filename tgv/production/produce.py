"""Production orchestrator: one selected item -> script, narration, video, cover, carousel.

Every production ends in status 'review' (or 'failed'). Stage 3 adds the
approval rules; nothing here publishes anything.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from tgv import db
from tgv.production import graphics
from tgv.production.brand import Brand
from tgv.production.media import concat_wavs, duration
from tgv.production.render import render
from tgv.production.script import ScriptDraft, validate_script
from tgv.production.subtitles import build_ass, caption_cues


class ProductionBlocked(Exception):
    """The draft failed editorial validation; nothing was rendered."""


def _item(conn: sqlite3.Connection, item_id: int) -> dict:
    row = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    if not row:
        raise KeyError(f"item {item_id} not found")
    return dict(row)


def next_selected(conn: sqlite3.Connection, limit: int) -> list[int]:
    return [r["id"] for r in conn.execute(
        "SELECT id FROM items WHERE status = 'selected' ORDER BY score DESC LIMIT ?", (limit,))]


def produce(conn: sqlite3.Connection, item_id: int, *, writer, tts, brand: Brand, media_root: Path,
            now: datetime, make_video: bool = True, make_carousel: bool = True) -> dict:
    item = _item(conn, item_id)
    if item["modality"] not in ("B", "C"):
        raise ProductionBlocked(f"modality {item['modality']} needs a licence decision before production")
    if item["status"] not in ("selected", "found"):
        raise ProductionBlocked(f"item status is {item['status']}")

    workdir = media_root / f"item_{item_id}"
    workdir.mkdir(parents=True, exist_ok=True)
    stamp = db.iso(now)
    cur = conn.execute(
        "INSERT INTO productions (item_id, modality, format, status, writer, created_at, updated_at)"
        " VALUES (?,?,?,?,?,?,?)",
        (item_id, item["modality"], "reel", "draft", writer.name, stamp, stamp),
    )
    prod_id = cur.lastrowid
    conn.execute("UPDATE items SET status='in_production' WHERE id=?", (item_id,))
    conn.commit()

    def finish(status: str, **fields):
        fields.update(status=status, updated_at=db.iso(now))
        cols = ", ".join(f"{k} = ?" for k in fields)
        conn.execute(f"UPDATE productions SET {cols} WHERE id = ?", (*fields.values(), prod_id))
        conn.execute("UPDATE items SET status=? WHERE id=?",
                     # a failed production goes to the human queue instead of being retried forever
                     ("produced" if status == "review" else "review", item_id))
        conn.commit()

    try:
        draft: ScriptDraft = writer.write(item)
        check = validate_script(draft, item_url=item["url"], item_claim_status=item["claim_status"])
        (workdir / "script.json").write_text(draft.to_json(), encoding="utf-8")
        if not check.ok:
            finish("failed", script=draft.to_json(), validation=json.dumps(asdict(check), ensure_ascii=False),
                   review_notes="validation failed: " + "; ".join(check.errors))
            raise ProductionBlocked("; ".join(check.errors))

        result = {"production_id": prod_id, "script": str(workdir / "script.json"),
                  "warnings": check.warnings, "video": None, "cover": None, "carousel": []}
        result["cover"] = str(graphics.cover(draft, brand, workdir / "cover.jpg", item["source_name"]))
        if make_carousel:
            result["carousel"] = [str(p) for p in graphics.carousel(draft, brand, workdir / "carousel",
                                                                   item["source_name"])]
        if make_video:
            parts, timeline, t = [], [], 0.0
            for i, seg in enumerate(draft.segments):
                wav = workdir / f"voice_{i:02d}.wav"
                seconds = tts.synthesize(seg.narration, wav)
                parts.append(wav)
                timeline.append((seg.narration, seg.on_screen, t, t + seconds))
                t += seconds + 0.15  # matches the gap added by concat_wavs
            concat_wavs(parts, workdir / "narration.wav")
            total = duration(workdir / "narration.wav") + 0.6
            (workdir / "captions.ass").write_text(build_ass(caption_cues(timeline), brand), encoding="utf-8")
            render(workdir, brand=brand, audio="narration.wav", ass="captions.ass", out="video.mp4",
                   seconds=total, claim_status=draft.claim_status)
            result["video"] = str(workdir / "video.mp4")

        notes = list(draft.notes)
        if getattr(tts, "name", "") == "placeholder":
            notes.append("placeholder (silent) narration: preview only, not publishable")
        if brand.provisional:
            notes.append("provisional brand kit: replace before publishing")
        finish("review", script=draft.to_json(), validation=json.dumps(asdict(check), ensure_ascii=False),
               caption=draft.caption + "\n\n" + " ".join(f"#{h.lstrip('#')}" for h in draft.hashtags),
               media_path=result["video"], cover_path=result["cover"],
               carousel_dir=str(workdir / "carousel") if make_carousel else None,
               review_notes="; ".join(notes) or None)
        return result
    except ProductionBlocked:
        raise
    except Exception as exc:
        finish("failed", review_notes=f"{type(exc).__name__}: {exc}"[:1000])
        db.add_alert(conn, now, "error", "production", f"item {item_id}: {type(exc).__name__}: {exc}"[:500])
        conn.commit()
        raise
