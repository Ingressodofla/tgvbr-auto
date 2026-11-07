"""FFmpeg / ffprobe helpers. All media work goes through these two binaries."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


class MediaError(Exception):
    pass


def require(binary: str) -> str:
    path = shutil.which(binary)
    if not path:
        raise MediaError(f"{binary} not found in PATH (install FFmpeg)")
    return path


def run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        tail = "\n".join(proc.stderr.strip().splitlines()[-12:])
        raise MediaError(f"{Path(cmd[0]).name} failed ({proc.returncode}):\n{tail}")


def probe(path: str | Path) -> dict:
    proc = subprocess.run(
        [require("ffprobe"), "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise MediaError(f"ffprobe failed on {path}: {proc.stderr.strip()}")
    return json.loads(proc.stdout)


def duration(path: str | Path) -> float:
    return float(probe(path)["format"]["duration"])


def concat_wavs(parts: list[Path], out: Path, gap_seconds: float = 0.15) -> None:
    """Join narration parts with a short pause, as 48 kHz mono WAV."""
    ffmpeg = require("ffmpeg")
    inputs, filters = [], []
    for i, p in enumerate(parts):
        inputs += ["-i", str(p)]
        filters.append(f"[{i}:a]aresample=48000,aformat=channel_layouts=mono,apad=pad_dur={gap_seconds}[a{i}]")
    joined = "".join(f"[a{i}]" for i in range(len(parts)))
    graph = ";".join(filters) + f";{joined}concat=n={len(parts)}:v=0:a=1[out]"
    run([ffmpeg, "-y", "-v", "error", *inputs, "-filter_complex", graph, "-map", "[out]", str(out)])
