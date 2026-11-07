"""Command line entry point: python -m tgv <command>."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from tgv import dashboard, db, pipeline
from tgv.models import utcnow
from tgv.sources.base import SourceNotConfigured, UrllibHttp
from tgv.sources.manual import load_csv
from tgv.sources.youtube import channel_for_handle

ROOT = Path(__file__).resolve().parent.parent


def _db_path(args) -> str:
    return args.db or os.environ.get("TGV_DB_PATH") or str(ROOT / "data" / "tgv.db")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="tgv", description="The Game Verse BR — content operation")
    p.add_argument("--db", help="SQLite path (default: $TGV_DB_PATH or data/tgv.db)")
    p.add_argument("--config", default=str(ROOT / "config" / "sources.json"))
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="create the database")
    d = sub.add_parser("discover", help="fetch from enabled sources")
    d.add_argument("--only", nargs="*", help="source kinds or names (rss, youtube, reddit, IGN...)")
    sub.add_parser("analyze", help="dedupe, classify and score recent items")
    s = sub.add_parser("select", help="mark the best stories for production")
    s.add_argument("--limit", type=int, default=5)
    r = sub.add_parser("rank", help="print the current ranking")
    r.add_argument("--limit", type=int, default=15)
    r.add_argument("--json", action="store_true")
    dash = sub.add_parser("dashboard", help="write the HTML dashboard")
    dash.add_argument("--out", default=str(ROOT / "out" / "dashboard.html"))
    run = sub.add_parser("run", help="discover + analyze + dashboard (the scheduled job)")
    run.add_argument("--out", default=str(ROOT / "out" / "dashboard.html"))
    imp = sub.add_parser("import-csv", help="import manually found links (TikTok, Instagram...)")
    imp.add_argument("path")
    pr = sub.add_parser("produce", help="produce script, video, cover and carousel for items")
    pr.add_argument("item_ids", nargs="*", type=int, help="item ids (default: best selected items)")
    pr.add_argument("--limit", type=int, default=3, help="how many selected items when no ids are given")
    pr.add_argument("--writer", choices=["claude", "template"], default="claude")
    pr.add_argument("--voice", choices=["piper", "placeholder"], default="piper")
    pr.add_argument("--no-video", action="store_true")
    pr.add_argument("--no-carousel", action="store_true")
    pr.add_argument("--brand", default=str(ROOT / "config" / "brand.json"))
    pr.add_argument("--media", default=os.environ.get("TGV_MEDIA_DIR") or str(ROOT / "media"))
    yc = sub.add_parser("youtube-channel", help="resolve a YouTube @handle to its channel id and feed")
    yc.add_argument("handle")

    args = p.parse_args(argv)
    now = utcnow()
    config = pipeline.load_config(args.config)
    conn = db.connect(_db_path(args))
    http = UrllibHttp()

    if args.cmd == "init":
        print(f"database ready: {_db_path(args)}")
    elif args.cmd in ("discover", "run"):
        only = set(args.only) if getattr(args, "only", None) else None
        for line in pipeline.discover(conn, config, http, now, only=only):
            print(f"{line['source']:<28} {line['status']:<8} fetched={line['fetched']:<4} new={line['new']:<4}"
                  f" {line['error'] or ''}")
        if args.cmd == "run":
            print(f"analyzed: {pipeline.analyze(conn, config, now)}")
            print(f"dashboard: {dashboard.write(conn, now, args.out)}")
    elif args.cmd == "analyze":
        print(f"analyzed: {pipeline.analyze(conn, config, now)}")
    elif args.cmd == "select":
        for row in pipeline.select(conn, config, args.limit):
            print(f"{row['score']:6.1f}  [{row['modality']}] {row['title']}  {row['url']}")
    elif args.cmd == "rank":
        rows = pipeline.ranking(conn, args.limit)
        if args.json:
            print(json.dumps([{k: row[k] for k in ("id", "score", "modality", "claim_status", "status",
                                                    "title", "url", "source_name", "coverage")}
                              for row in rows], ensure_ascii=False, indent=2))
        for row in rows if not args.json else []:
            print(f"{row['score']:6.1f}  {row['status']:<8} [{row['modality']}] {row['title'][:90]}"
                  f"  ({row['source_name']}, fontes={row['coverage']})")
    elif args.cmd == "dashboard":
        print(dashboard.write(conn, now, args.out))
    elif args.cmd == "import-csv":
        items, errors = load_csv(args.path, now)
        fetched, new = pipeline.ingest(conn, items, now)
        conn.commit()
        print(f"imported={fetched} new={new}")
        for e in errors:
            print(f"warning: {e}", file=sys.stderr)
    elif args.cmd == "produce":
        return _produce(args, conn, now)
    elif args.cmd == "youtube-channel":
        try:
            info = channel_for_handle(http, args.handle)
        except SourceNotConfigured as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        print(json.dumps(info, ensure_ascii=False, indent=2) if info else "channel not found")
    conn.close()
    return 0


def _produce(args, conn, now) -> int:
    from tgv.production.brand import load_brand
    from tgv.production.produce import ProductionBlocked, next_selected, produce
    from tgv.production.script import ClaudeScriptWriter, TemplateScriptWriter
    from tgv.production.tts import PiperTTS, PlaceholderTTS

    brand = load_brand(args.brand)
    writer = ClaudeScriptWriter() if args.writer == "claude" else TemplateScriptWriter()
    if args.voice == "piper":
        model = Path(brand.voice.get("piper_model", ""))
        tts = PiperTTS(model if model.is_absolute() else ROOT / model, brand.voice.get("length_scale", 1.0))
    else:
        tts = PlaceholderTTS()
    ids = args.item_ids or next_selected(conn, args.limit)
    if not ids:
        print("nothing selected; run: python -m tgv select")
        return 0
    failures = 0
    for item_id in ids:
        try:
            r = produce(conn, item_id, writer=writer, tts=tts, brand=brand, media_root=Path(args.media), now=now,
                        make_video=not args.no_video, make_carousel=not args.no_carousel)
            print(f"item {item_id}: review -> {r['video'] or r['cover']}")
            for w in r["warnings"]:
                print(f"  warning: {w}")
        except ProductionBlocked as exc:
            failures += 1
            print(f"item {item_id}: blocked ({exc})", file=sys.stderr)
        except Exception as exc:  # recorded as failed production + alert
            failures += 1
            print(f"item {item_id}: failed ({type(exc).__name__}: {exc})", file=sys.stderr)
    conn.close()
    return 1 if failures else 0
