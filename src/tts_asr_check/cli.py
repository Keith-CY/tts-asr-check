"""Command line: ``tts-asr-check check|compare|readings|backends``."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from pathlib import Path

from . import __version__, align, zh
from .audio import AudioError
from .audio import load as load_audio
from .backends import REGISTRY, BackendError, default_pair, make
from .backends.base import label
from .report import Result, evaluate, to_json, to_markdown
from .script import Script, ScriptError, assign_audio
from .script import load as load_script
from .text import LANGS, guess_lang

EXIT_OK, EXIT_LISTEN, EXIT_ERROR = 0, 1, 2


def _err(msg: str) -> None:
    print(f"tts-asr-check: {msg}", file=sys.stderr)


def _lang(args, script: Script) -> str:
    lang = args.lang or script.lang or guess_lang(" ".join(ln.text for ln in script.lines))
    if lang not in LANGS:
        raise ScriptError(f"language {lang!r} is not supported (zh, en, ja)")
    return lang


def _readings(args, script: Script) -> dict[str, str]:
    out = dict(script.readings)
    for item in args.reading or []:
        key, sep, value = item.partition("=")
        if not sep or not key or not value:
            raise ScriptError(f"--reading takes CHARS=PINYIN, e.g. 缪=miù (got {item!r})")
        out[key] = value
    zh.parse_pinned(out)  # fail early on a bad reading
    return out


def _write(res: Result, args) -> int:
    report_json = json.dumps(to_json(res), ensure_ascii=False, indent=2)
    md = to_markdown(res, table=not args.brief)
    if args.json and args.json != "-":
        Path(args.json).write_text(report_json + "\n", encoding="utf-8")
    if args.markdown:
        Path(args.markdown).write_text(md, encoding="utf-8")
    print(report_json if args.json == "-" else md)
    c = res.counts()
    if args.fail_on == "never":
        return EXIT_OK
    bad = c["misread"] + (c["listen"] if args.fail_on == "listen" else 0)
    return EXIT_LISTEN if bad else EXIT_OK


def _heard_file(path: str, lines) -> tuple[dict[str, str], str]:
    """A transcript file: ``{"lines": {id: text}}``, ``{"text": "..."}``,
    a plain ``{id: text}`` object, or JSONL rows with ``id`` and ``text``."""
    p = Path(path)
    try:
        raw = p.read_text(encoding="utf-8-sig")
    except OSError as e:
        raise ScriptError(f"cannot read {p}: {e.strerror}") from None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        try:
            rows = [json.loads(r) for r in raw.splitlines() if r.strip()]
        except json.JSONDecodeError as e:
            raise ScriptError(f"{p}: {e}") from None
        data = {"lines": {str(r["id"]): r["text"] for r in rows}}
    if not isinstance(data, dict):
        raise ScriptError(f"{p}: expected a JSON object")
    name = " · ".join(str(data[k]) for k in ("backend", "model") if data.get(k)) or p.name
    if isinstance(data.get("lines"), dict):
        heard = {str(k): str(v) for k, v in data["lines"].items()}
    elif isinstance(data.get("text"), str):
        heard = dict(zip([ln.id for ln in lines], align.split([ln.text for ln in lines], data["text"])))
    else:
        heard = {str(k): str(v) for k, v in data.items() if isinstance(v, str)}
    missing = [ln.id for ln in lines if ln.id not in heard]
    if missing:
        _err(f"{p.name} has no text for line(s) {', '.join(missing[:10])}{' …' if len(missing) > 10 else ''}")
    return heard, name


def cmd_compare(args) -> int:
    script = load_script(args.script)
    lang = _lang(args, script)
    readings = _readings(args, script)
    heard_a, name_a = _heard_file(args.transcript_a, script.lines)
    heard_b, name_b = _heard_file(args.transcript_b, script.lines)
    rows = evaluate(script.lines, heard_a, heard_b, lang, readings)
    return _write(Result(str(script.path), lang, "transcripts", (name_a, name_b), rows), args)


def cmd_check(args) -> int:
    script = load_script(args.script)
    lang = _lang(args, script)
    readings = _readings(args, script)
    mode = assign_audio(script, args.audio)
    specs = args.asr or default_pair()
    if len(specs) != 2:
        raise ScriptError("give --asr exactly twice (two different recognisers), or not at all")
    for ln in script.lines:
        if not Path(ln.audio).is_file():
            raise ScriptError(f"line {ln.id}: no audio file {ln.audio}")

    if mode == "whole":
        clips = {"*": load_audio(script.lines[0].audio)}
    else:
        clips = {
            ln.id: load_audio(ln.audio, ln.start, ln.end, args.pad if ln.start is not None else 0.0)
            for ln in script.lines
        }

    heard, labels, saved = [], [], []
    for tag, spec in zip("AB", specs):
        t0 = time.time()
        _err(f"{tag}: loading {spec}")
        try:
            backend = make(spec)
        except BackendError:
            raise
        except Exception as e:  # a model that can't be found or loaded
            raise BackendError(f"{tag}: could not load {spec}: {type(e).__name__}: {e}") from None
        labels.append(label(backend))
        try:
            texts = {key: backend.transcribe(audio, lang) for key, audio in clips.items()}
        except Exception as e:
            raise BackendError(f"{tag}: {spec} failed while transcribing: {type(e).__name__}: {e}") from None
        if hasattr(backend, "close"):
            backend.close()
        _err(f"{tag}: {labels[-1]}, {len(clips)} clip(s) in {time.time() - t0:.1f} s")
        record = {"backend": backend.name, "model": labels[-1].split(" · ", 1)[-1]}
        if mode == "whole":
            record["text"] = texts["*"]
            texts = dict(zip([ln.id for ln in script.lines], align.split([ln.text for ln in script.lines], texts["*"])))
        record["lines"] = texts
        heard.append(texts)
        saved.append(record)

    if args.save_transcripts:
        d = Path(args.save_transcripts)
        d.mkdir(parents=True, exist_ok=True)
        for tag, record in zip("AB", saved):
            (d / f"{tag}.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    rows = evaluate(script.lines, heard[0], heard[1], lang, readings)
    return _write(Result(str(script.path), lang, mode, (labels[0], labels[1]), rows), args)


def cmd_readings(args) -> int:
    script = load_script(args.script)
    pinned = _readings(args, script)
    marked = 0
    for ln in script.lines:
        r = zh.readings(ln.text, zh.parse_pinned({**pinned, **ln.readings}))
        if not r:
            continue
        words = []
        for i in sorted(r):
            rd = r[i]
            say = zh.marks(rd.meant)
            if rd.guessed:
                marked += 1
                say = f"[{ln.text[i]} {say}? {'/'.join(sorted(zh.marks(o) for o in rd.options))}]"
            words.append(say)
        print(f"{ln.id}\t{ln.text}\n\t{' '.join(words)}")
    if marked:
        print(
            f"\n{marked} character(s) in [brackets] have several readings and nothing decides which;"
            " the check will flag them when a model hears another reading. Pin the meant reading with"
            ' --reading 字=pinyin or "readings" in the script.'
        )
    return EXIT_OK


def cmd_backends(args) -> int:
    print(f"default pair on this machine: {' + '.join(default_pair())}\n")
    needs = {
        "mlx-whisper": "mlx_whisper",
        "mlx-qwen3-asr": "mlx_audio",
        "faster-whisper": "faster_whisper",
        "transformers": "transformers",
    }
    for name, (_, _, model, what) in REGISTRY.items():
        ok = importlib.util.find_spec(needs[name]) is not None
        print(f"{name:<15} {'installed' if ok else 'not installed':<14} {model}\n{'':<15} {what}")
    return EXIT_OK


def _output_options(p: argparse.ArgumentParser) -> None:
    p.add_argument("--lang", choices=LANGS, help="language of the script (default: from the script)")
    p.add_argument(
        "--reading",
        action="append",
        metavar="CHARS=PINYIN",
        help="Chinese: the reading meant for a character or word, e.g. 缪=miù (repeatable)",
    )
    p.add_argument("--json", metavar="PATH", help="write the JSON report here ('-': print it instead of Markdown)")
    p.add_argument("--markdown", metavar="PATH", help="write the Markdown report here too")
    p.add_argument("--brief", action="store_true", help="leave the table of all lines out of the Markdown")
    p.add_argument(
        "--fail-on",
        choices=("listen", "misread", "never"),
        default="listen",
        help="exit 1 when any line is worth a listen (default), only on likely misreads, or never",
    )


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="tts-asr-check",
        description="Check narration audio against its script with two speech recognisers, line by line.",
    )
    ap.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("check", help="transcribe the audio with two models and compare with the script")
    p.add_argument("script", help="the script: .txt, .json, .jsonl, .srt or .vtt")
    p.add_argument("audio", nargs="*", help="one file per line, one folder, or one recording of the whole script")
    p.add_argument(
        "--asr",
        action="append",
        metavar="BACKEND[=MODEL]",
        help="a recogniser; give it twice (default: " + " and ".join(default_pair()) + ")",
    )
    p.add_argument(
        "--pad",
        type=float,
        default=0.15,
        metavar="SECONDS",
        help="widen timed lines by this much on each side (default 0.15)",
    )
    p.add_argument("--save-transcripts", metavar="DIR", help="keep what each model heard (A.json, B.json)")
    _output_options(p)
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("compare", help="compare saved transcripts with the script (no models)")
    p.add_argument("script")
    p.add_argument("transcript_a")
    p.add_argument("transcript_b")
    _output_options(p)
    p.set_defaults(func=cmd_compare)

    p = sub.add_parser("readings", help="Chinese: the reading each character will be checked against")
    p.add_argument("script")
    p.add_argument("--reading", action="append", metavar="CHARS=PINYIN")
    p.set_defaults(func=cmd_readings)

    p = sub.add_parser("backends", help="list the speech recognisers and whether they are installed")
    p.set_defaults(func=cmd_backends)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        return args.func(args)
    except (ScriptError, AudioError, BackendError, ValueError) as e:
        _err(str(e))
        return EXIT_ERROR
