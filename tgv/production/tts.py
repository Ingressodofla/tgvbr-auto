"""Narration engines.

PiperTTS: local, free, offline neural TTS (https://github.com/OHF-Voice/piper1-gpl).
  Voice files are downloaded once (e.g. pt_BR-faber-medium.onnx + .onnx.json)
  and their path goes in config/brand.json -> voice.piper_model.
  Licence note: piper-tts 1.x is GPL-3.0; it is used as a separate command-line
  program, and each voice model has its own licence (check the voice's MODEL_CARD).
PlaceholderTTS: silent audio with a realistic duration. For tests and for
  previewing layout/timing without a voice installed. Never for publication.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from tgv.production.media import MediaError, duration, require, run
from tgv.production.script import WORDS_PER_SECOND


class PiperTTS:
    name = "piper"

    def __init__(self, model_path: str | Path, length_scale: float = 1.0, python: str = sys.executable):
        self.model_path = Path(model_path)
        self.length_scale = length_scale
        self.python = python

    def check(self) -> None:
        if not self.model_path.is_file():
            raise MediaError(
                f"Piper voice not found: {self.model_path}. Download pt_BR-faber-medium.onnx and "
                ".onnx.json (see docs/PRODUCTION.md) and set voice.piper_model in config/brand.json."
            )

    def synthesize(self, text: str, out_wav: Path) -> float:
        self.check()
        proc = subprocess.run(
            [self.python, "-m", "piper", "-m", str(self.model_path), "-f", str(out_wav),
             "--length-scale", str(self.length_scale)],
            input=text, capture_output=True, text=True,
        )
        if proc.returncode != 0:
            raise MediaError(f"piper failed: {proc.stderr.strip()[-500:]}")
        return duration(out_wav)


class PlaceholderTTS:
    name = "placeholder"

    def synthesize(self, text: str, out_wav: Path) -> float:
        seconds = max(1.0, len(text.split()) / WORDS_PER_SECOND)
        run([require("ffmpeg"), "-y", "-v", "error", "-f", "lavfi",
             "-i", "anullsrc=r=48000:cl=mono", "-t", f"{seconds:.2f}", str(out_wav)])
        return duration(out_wav)
