"""Vertical video template (1080x1920, 30 fps, H.264 High + AAC, -14 LUFS).

Layers, bottom to top:
1. Background: the item's licensed/own images with a slow Ken Burns zoom, or
   an animated brand gradient when there are none (modality B/C default).
   Third-party footage is never pulled in automatically.
2. Dark vignette band behind the captions for legibility.
3. Brand bar (name/handle) and status tag (OFICIAL / NOTÍCIA / RUMOR).
4. Headline per segment + word-chunk captions (ASS, animated pop-in).
5. Progress bar in the accent colour.
6. Optional logo (brand.logo_path).
"""
from __future__ import annotations

from pathlib import Path

from tgv.production.brand import Brand
from tgv.production.media import require, run

STATUS_TAG = {"confirmed": ("OFICIAL", "official"), "reported": ("NOTÍCIA", "accent_2"),
              "unverified": ("RUMOR · NÃO CONFIRMADO", "rumor"), "not_a_claim": ("GTA VI", "accent_2")}


def _ffpath(path: str) -> str:
    """Path for use inside a filtergraph: forward slashes, drive colon escaped (C\\:/...)."""
    return Path(path).as_posix().replace(":", r"\:").replace("'", "")


def _ffcolor(hex_color: str) -> str:
    return "0x" + hex_color.lstrip("#")


def build_command(*, brand: Brand, audio: str, ass: str, out: str, seconds: float,
                  claim_status: str, images: list[str] | None = None) -> list[str]:
    """Return the ffmpeg argv. Paths are relative to the working directory the caller uses."""
    w, h, fps = brand.width, brand.height, brand.fps
    dur = f"{seconds:.3f}"
    inputs: list[str] = []
    graph: list[str] = []

    if images:
        per = seconds / len(images)
        frames = max(1, int(per * fps))
        for i, img in enumerate(images):
            inputs += ["-loop", "1", "-t", f"{per:.3f}", "-i", img]
            graph.append(
                f"[{i}:v]scale={w * 2}:{h * 2}:force_original_aspect_ratio=increase,crop={w * 2}:{h * 2},"
                f"zoompan=z='min(zoom+0.0008,1.12)':d={frames}:s={w}x{h}:fps={fps},"
                f"eq=brightness=-0.08:saturation=1.1,setsar=1[bg{i}]"
            )
        graph.append("".join(f"[bg{i}]" for i in range(len(images))) + f"concat=n={len(images)}:v=1:a=0[bg]")
        audio_idx = len(images)
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
    graph.append(
        f"[bg]drawbox=x=0:y=ih*0.58:w=iw:h=ih*0.30:color=black@0.35:t=fill,"
        f"drawbox=x=0:y=0:w=iw:h=120:color=black@0.55:t=fill,"
        f"drawtext=fontfile='{body_font}':text='{label}':x=60:y=38:fontsize=44:fontcolor=white,"
        f"drawtext=fontfile='{body_font}':text='{tag_txt}':x=w-tw-60:y=160:fontsize=40:fontcolor=black:"
        f"box=1:boxcolor={_ffcolor(brand.color(tag_color))}:boxborderw=18,"
        f"subtitles=filename='{ass}':fontsdir='{fonts_dir}'[txt]"
    )
    graph.append(f"color=c={accent}:s={w}x10:r={fps}:d={dur}[bar]")
    graph.append(f"[txt][bar]overlay=x='-W+W*t/{dur}':y=H-10:shortest=1[v0]")
    last = "v0"
    if brand.logo_path and Path(brand.logo_path).exists():
        logo_idx = audio_idx + 1
        inputs += ["-i", brand.logo_path]
        graph.append(f"[{logo_idx}:v]scale=-1:96[logo]")
        graph.append(f"[v0][logo]overlay=x=W-w-50:y=12[v1]")
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
