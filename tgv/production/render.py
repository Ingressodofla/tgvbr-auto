"""Vertical video template (1080x1920, 30 fps, H.264 High + AAC, -14 LUFS).

Layers, bottom to top:
1. Background: clips/images from the licensed media library (tgv/production/library.py),
   fitted between the bands over a blurred copy, or an animated brand gradient when
   there are none. Third-party footage is never pulled in automatically.
2. Black letterbox bands (top: status tag + headline box; bottom: logo + handle),
   matching the page's best-performing posts.
3. Status tag (OFICIAL / NOTÍCIA / RUMOR).
4. Headline per segment + word-chunk captions (ASS, animated pop-in).
5. Progress bar in the accent colour.
6. Logo watermark at the bottom (brand.logo_path).
"""
from __future__ import annotations

from pathlib import Path

from tgv.production.brand import Brand
from tgv.production.media import require, run

TOP_BAND = 0.20     # black band with the headline box (fraction of the height)
BOTTOM_BAND = 0.80  # black band with logo + handle starts here

STATUS_TAG = {"confirmed": ("OFICIAL", "official"), "reported": ("NOTÍCIA", "accent_2"),
              "unverified": ("RUMOR · NÃO CONFIRMADO", "rumor"), "not_a_claim": ("GTA VI", "accent_2")}


def _ffpath(path: str) -> str:
    """Path for use inside a filtergraph: forward slashes, drive colon escaped (C\\:/...)."""
    return Path(path).as_posix().replace(":", r"\:").replace("'", "")


def _ffcolor(hex_color: str) -> str:
    return "0x" + hex_color.lstrip("#")


def build_command(*, brand: Brand, audio: str, ass: str, out: str, seconds: float,
                  claim_status: str, visuals: list[tuple[str, str, float]] | None = None) -> list[str]:
    """Return the ffmpeg argv. Paths are relative to the working directory the caller uses.

    visuals: (path, kind, start) from the licensed media library; kind is "clip" or "image".
    Each one gets an equal share of the duration and is shown fitted between the bands over a
    blurred, darkened copy of itself (the usual vertical format for 16:9 trailers). Clip audio
    is never used: the only sound is our narration.
    """
    w, h, fps = brand.width, brand.height, brand.fps
    dur = f"{seconds:.3f}"
    inputs: list[str] = []
    graph: list[str] = []
    mid_h = int(h * (BOTTOM_BAND - TOP_BAND))

    if visuals:
        per = f"{seconds / len(visuals):.3f}"
        for i, (path, kind, start) in enumerate(visuals):
            if kind == "clip":
                inputs += ["-stream_loop", "-1", "-ss", f"{start:.3f}", "-t", per, "-i", path]
            else:
                inputs += ["-loop", "1", "-framerate", str(fps), "-t", per, "-i", path]
            graph.append(
                f"[{i}:v]fps={fps},split[a{i}][b{i}];"
                f"[a{i}]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},"
                f"gblur=sigma=40,eq=brightness=-0.25[bk{i}];"
                f"[b{i}]scale={w}:{mid_h}:force_original_aspect_ratio=decrease[fg{i}];"
                f"[bk{i}][fg{i}]overlay=x=(W-w)/2:y=(H-h)/2,trim=duration={per},setpts=PTS-STARTPTS,"
                f"setsar=1,format=yuv420p[bg{i}]"
            )
        graph.append("".join(f"[bg{i}]" for i in range(len(visuals))) + f"concat=n={len(visuals)}:v=1:a=0[bg]")
        audio_idx = len(visuals)
    else:
        c = brand.colors
        inputs += ["-f", "lavfi", "-i",
                   f"gradients=s={w}x{h}:r={fps}:d={dur}:speed=0.008:"
                   f"c0={_ffcolor(c['background_top'])}:c1={_ffcolor(c['background_bottom'])}:"
                   f"c2={_ffcolor(c['background_top'])}:nb_colors=3"]
        graph.append("[0:v]setsar=1[bg]")
        audio_idx = 1
    inputs += ["-i", audio]

    tag, tag_color = STATUS_TAG.get(claim_status, STATUS_TAG["not_a_claim"])
    body_font = _ffpath(brand.fonts["body"])
    fonts_dir = _ffpath(brand.fonts.get("fonts_dir", ""))
    label = brand.label().replace(":", r"\:").replace("'", "")
    tag_txt = tag.replace(":", r"\:")
    accent = _ffcolor(brand.color("accent"))
    top, bottom = int(h * TOP_BAND), int(h * BOTTOM_BAND)
    # Letterbox bands like the page's posts: headline box on top (ASS), logo + handle at the bottom.
    graph.append(
        f"[bg]drawbox=x=0:y=0:w=iw:h={top}:color=black:t=fill,"
        f"drawbox=x=0:y={bottom}:w=iw:h=ih-{bottom}:color=black:t=fill,"
        f"drawtext=fontfile='{body_font}':text='{tag_txt}':x=(w-tw)/2:y=48:fontsize=34:fontcolor=black:"
        f"box=1:boxcolor={_ffcolor(brand.color(tag_color))}:boxborderw=14,"
        f"drawtext=fontfile='{body_font}':text='{label}':x=(w-tw)/2:y={bottom + int((h - bottom) * 0.62)}:"
        f"fontsize=34:fontcolor=white,"
        f"subtitles=filename='{ass}':fontsdir='{fonts_dir}'[txt]"
    )
    graph.append(f"color=c={accent}:s={w}x10:r={fps}:d={dur}[bar]")
    graph.append(f"[txt][bar]overlay=x='-W+W*t/{dur}':y=H-10:shortest=1[v0]")
    last = "v0"
    if brand.logo_path and Path(brand.logo_path).exists():
        logo_idx = audio_idx + 1
        inputs += ["-i", brand.logo_path]
        graph.append(f"[{logo_idx}:v]scale=-1:{int((h - bottom) * 0.42)}[logo]")
        graph.append(f"[v0][logo]overlay=x=(W-w)/2:y={bottom + int((h - bottom) * 0.12)}[v1]")
        last = "v1"
    graph.append(f"[{audio_idx}:a]loudnorm=I={brand.video.get('loudness_lufs', -14)}:TP=-1.5:LRA=11,"
                 f"aresample=48000[a]")

    return [
        require("ffmpeg"), "-y", "-v", "error", *inputs,
        "-filter_complex", ";".join(graph),
        "-map", f"[{last}]", "-map", "[a]", "-t", dur,
        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-profile:v", "high",
        "-pix_fmt", "yuv420p", "-r", str(fps),
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-movflags", "+faststart", out,
    ]


def render(workdir: Path, **kw) -> Path:
    """Run ffmpeg inside workdir so the ASS/audio paths need no escaping."""
    import subprocess

    cmd = build_command(**kw)
    proc = subprocess.run(cmd, cwd=workdir, capture_output=True, text=True)
    if proc.returncode != 0:
        from tgv.production.media import MediaError

        raise MediaError("ffmpeg render failed:\n" + "\n".join(proc.stderr.strip().splitlines()[-15:]))
    return workdir / kw["out"]
