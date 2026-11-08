"""Loading audio as 16 kHz mono float32 with ffmpeg."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import numpy as np

RATE = 16000


class AudioError(RuntimeError):
    pass


def load(path: str | Path, start: float | None = None, end: float | None = None, pad: float = 0.0) -> np.ndarray:
    """The whole file, or the stretch from ``start`` to ``end`` seconds
    (widened by ``pad`` on each side)."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise AudioError("ffmpeg is needed to read audio; install it (macOS: brew install ffmpeg)")
    cmd = [ffmpeg, "-nostdin", "-v", "error"]
    if start is not None:
        s = max(0.0, start - pad)
        cmd += ["-ss", f"{s:.3f}"]
        if end is not None:
            cmd += ["-t", f"{max(0.0, end + pad - s):.3f}"]
    cmd += ["-i", str(path), "-f", "f32le", "-ac", "1", "-ar", str(RATE), "-"]
    p = subprocess.run(cmd, capture_output=True)
    if p.returncode:
        raise AudioError(f"ffmpeg could not read {path}: {p.stderr.decode(errors='replace').strip()}")
    return np.frombuffer(p.stdout, dtype=np.float32).copy()


def split_quiet(audio: np.ndarray, max_seconds: float) -> list[np.ndarray]:
    """Cut long audio into pieces of at most ``max_seconds``, at the quietest
    moment of the last few seconds before each limit."""
    limit = int(max_seconds * RATE)
    if len(audio) <= limit:
        return [audio]
    frame = RATE // 50  # 20 ms
    pieces, at = [], 0
    while len(audio) - at > limit:
        lo = at + int(limit * 0.7)
        window = audio[lo : at + limit]
        n = len(window) // frame
        energy = (window[: n * frame].reshape(n, frame) ** 2).mean(axis=1)
        cut = lo + int(np.argmin(energy)) * frame + frame // 2
        pieces.append(audio[at:cut])
        at = cut
    pieces.append(audio[at:])
    return pieces
