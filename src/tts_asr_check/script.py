"""Reading a script, and matching its lines to audio.

Formats:

* ``.txt``: one narration line per line of text; blank lines are skipped.
* ``.srt`` / ``.vtt``: subtitles; each cue is a line, with its timing.
* ``.json``: a list of strings, a list of line objects, or an object
  ``{"lang": "zh", "readings": {...}, "lines": [...]}``.
* ``.jsonl``: one line object (or string) per line.

A line object has ``text`` and optionally ``id``, ``audio`` (a path relative
to the script), ``start`` / ``end`` (seconds into the audio) and ``readings``
(``{"缪": "miù"}``, pinned Chinese readings for this line only).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

AUDIO_EXT = {".wav", ".flac", ".mp3", ".m4a", ".aac", ".ogg", ".opus", ".aiff", ".aif", ".caf", ".webm", ".mp4", ".mov"}


class ScriptError(ValueError):
    pass


@dataclass
class Line:
    id: str
    text: str
    audio: Path | None = None
    start: float | None = None
    end: float | None = None
    readings: dict[str, str] = field(default_factory=dict)


@dataclass
class Script:
    path: Path
    lines: list[Line]
    lang: str | None = None
    readings: dict[str, str] = field(default_factory=dict)


def _line(obj, n: int, base: Path) -> Line:
    if isinstance(obj, str):
        return Line(str(n), obj)
    if not isinstance(obj, dict) or not isinstance(obj.get("text"), str):
        raise ScriptError(f'line {n}: expected a string or an object with "text"')
    audio = obj.get("audio")
    return Line(
        id=str(obj.get("id", n)),
        text=obj["text"],
        audio=(base / audio) if audio else None,
        start=_seconds(obj.get("start")),
        end=_seconds(obj.get("end")),
        readings=dict(obj.get("readings") or {}),
    )


def _seconds(v) -> float | None:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    m = re.fullmatch(r"(?:(\d+):)?(\d+):(\d+(?:[.,]\d+)?)", str(v).strip())
    if not m:
        return float(v)
    h, mi, s = m.groups()
    return int(h or 0) * 3600 + int(mi) * 60 + float(s.replace(",", "."))


_CUE = re.compile(r"^\s*((?:\d+:)?\d+:\d+[.,]\d+)\s*-->\s*((?:\d+:)?\d+:\d+[.,]\d+)")


def _subtitles(raw: str) -> list[Line]:
    lines, n = [], 0
    blocks = re.split(r"\n\s*\n", raw.replace("\r\n", "\n").strip())
    for block in blocks:
        rows = block.split("\n")
        for i, row in enumerate(rows):
            m = _CUE.match(row)
            if m:
                text = " ".join(r.strip() for r in rows[i + 1 :] if r.strip())
                text = re.sub(r"<[^>]+>", "", text)
                if text:
                    n += 1
                    lines.append(Line(str(n), text, start=_seconds(m.group(1)), end=_seconds(m.group(2))))
                break
    return lines


def load(path: str | Path) -> Script:
    path = Path(path)
    try:
        raw = path.read_text(encoding="utf-8-sig")
    except OSError as e:
        raise ScriptError(f"cannot read {path}: {e.strerror}") from None
    base = path.parent
    suffix = path.suffix.lower()
    lang, readings = None, {}
    if suffix in (".srt", ".vtt"):
        lines = _subtitles(raw)
    elif suffix == ".json":
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ScriptError(f"{path}: {e}") from None
        if isinstance(data, dict):
            lang = data.get("lang")
            readings = dict(data.get("readings") or {})
            data = data.get("lines")
        if not isinstance(data, list):
            raise ScriptError(f"{path}: expected a list of lines")
        lines = [_line(obj, n, base) for n, obj in enumerate(data, 1)]
    elif suffix == ".jsonl":
        rows = [r for r in raw.splitlines() if r.strip()]
        try:
            lines = [_line(json.loads(r), n, base) for n, r in enumerate(rows, 1)]
        except json.JSONDecodeError as e:
            raise ScriptError(f"{path}: {e}") from None
    else:
        lines = [Line(str(n), t.strip()) for n, t in enumerate((r for r in raw.splitlines() if r.strip()), 1)]
    if not lines:
        raise ScriptError(f"{path}: no lines")
    ids = [ln.id for ln in lines]
    if len(set(ids)) != len(ids):
        raise ScriptError(f"{path}: line ids repeat")
    return Script(path, lines, lang, readings)


def assign_audio(script: Script, audio: list[str | Path]) -> str:
    """Give every line its audio. Returns the mode: ``lines`` (one file or
    one timed stretch per line) or ``whole`` (one untimed recording)."""
    lines = script.lines
    paths = [Path(a) for a in audio]
    have = [ln.audio is not None for ln in lines]
    if any(have):
        if not all(have):
            raise ScriptError("some lines name an audio file and some don't")
        if paths:
            raise ScriptError("the script names its audio files; don't pass audio as well")
        return "lines"
    if not paths:
        raise ScriptError('no audio: pass audio files, a folder, or put "audio" in the script\'s lines')
    if len(paths) == 1 and paths[0].is_dir():
        files = sorted(p for p in paths[0].iterdir() if p.suffix.lower() in AUDIO_EXT)
        by_stem = {p.stem: p for p in files}
        if all(ln.id in by_stem for ln in lines):
            for ln in lines:
                ln.audio = by_stem[ln.id]
            return "lines"
        if len(files) != len(lines):
            raise ScriptError(
                f"{paths[0]} has {len(files)} audio files for {len(lines)} lines, and their names are not the line ids"
            )
        paths = files
    if len(paths) == 1:
        timed = [ln.start is not None and ln.end is not None for ln in lines]
        for ln in lines:
            ln.audio = paths[0]
        if all(timed):
            return "lines"
        if any(timed):
            raise ScriptError("some lines have start/end times and some don't")
        return "whole"
    if len(paths) != len(lines):
        raise ScriptError(f"{len(paths)} audio files for {len(lines)} lines")
    for ln, p in zip(lines, paths):
        ln.audio = p
    return "lines"
