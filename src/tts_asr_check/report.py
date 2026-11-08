"""Putting the comparisons together, and writing them out as Markdown or JSON."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import __version__, zh
from .compare import KINDS, Diff, Match, both_heard, compare, status, unconfirmed
from .script import Line

STATUS_WORDS = {"ok": "ok", "listen": "worth a listen", "misread": "likely misread"}
VERDICT_WORDS = {"exact": "exact", "same": "same sound", "differs": "differs"}


@dataclass
class LineResult:
    line: Line
    a: Match
    b: Match
    ab: Match
    status: str
    both: list[str] = field(default_factory=list)
    unconfirmed: list[str] = field(default_factory=list)


@dataclass
class Result:
    script: str
    lang: str
    mode: str
    labels: tuple[str, str]
    lines: list[LineResult]

    def counts(self) -> dict[str, int]:
        c = {"lines": len(self.lines), "ok": 0, "listen": 0, "misread": 0}
        for r in self.lines:
            c[r.status] += 1
        return c


def evaluate(
    lines: list[Line],
    heard_a: dict[str, str],
    heard_b: dict[str, str],
    lang: str,
    readings: dict[str, str] | None = None,
) -> list[LineResult]:
    out = []
    for ln in lines:
        pinned = zh.parse_pinned({**(readings or {}), **ln.readings}) if lang == "zh" else None
        a = compare(ln.text, heard_a.get(ln.id, ""), lang, pinned)
        b = compare(ln.text, heard_b.get(ln.id, ""), lang, pinned)
        ab = compare(a.heard, b.heard, lang, pinned, pair=True)
        out.append(LineResult(ln, a, b, ab, status(a, b), both_heard(a, b, lang, pinned), unconfirmed(a, b)))
    return out


# --- JSON ------------------------------------------------------------------


def to_json(res: Result) -> dict:
    lines = []
    for r in res.lines:
        ln = r.line
        row = {"id": ln.id, "script": ln.text, "status": r.status}
        if ln.audio is not None:
            row["audio"] = str(ln.audio)
        if ln.start is not None:
            row["start"], row["end"] = ln.start, ln.end
        row["A"] = r.a.as_dict()
        row["B"] = r.b.as_dict()
        row["A_vs_B"] = r.ab.as_dict()
        if r.both:
            row["both_heard"] = r.both
        if r.unconfirmed:
            row["unconfirmed"] = r.unconfirmed
        lines.append(row)
    return {
        "tool": "tts-asr-check",
        "version": __version__,
        "script": res.script,
        "lang": res.lang,
        "mode": res.mode,
        "models": {"A": res.labels[0], "B": res.labels[1]},
        "summary": res.counts(),
        "lines": lines,
    }


# --- Markdown --------------------------------------------------------------


def _say(text: str, reading: str) -> str:
    return f"{text} {reading}" if reading else text


def describe(d: Diff) -> str:
    if d.kind == "missing":
        return f"{d.script}: not heard"
    if d.kind == "extra":
        return f"+ {d.heard}: heard, not in the script"
    what = KINDS[d.kind]
    if d.kind == "polyphone":
        chars = "".join(c for c in d.script if not c.isspace())
        what = f"another reading of {chars} ({', '.join(d.options)}); pin the one meant with --reading"
    return f"{_say(d.script, d.script_reading)} → {_say(d.heard, d.heard_reading)}: {what}"


def _pair_lines(m: Match) -> list[str]:
    if m.verdict == "exact":
        return ["agree"]
    if m.verdict == "same":
        return ["agree in sound"]
    out = []
    for d in m.diffs:
        a = _say(d.script, d.script_reading) or "(nothing)"
        b = _say(d.heard, d.heard_reading) or "(nothing)"
        out.append(f"A {a} · B {b}")
    return out


def _cell(m: Match) -> str:
    if m.verdict != "differs":
        return VERDICT_WORDS[m.verdict]
    parts = []
    for d in m.diffs[:3]:
        if d.kind == "missing":
            parts.append(f"−{d.script}")
        elif d.kind == "extra":
            parts.append(f"+{d.heard}")
        else:
            parts.append(f"{d.script}→{d.heard}")
    more = f" (+{len(m.diffs) - 3})" if len(m.diffs) > 3 else ""
    return ", ".join(parts).replace("|", "\\|") + more


def _short(s: str, n: int = 28) -> str:
    s = " ".join(s.split())
    return (s[: n - 1] + "…" if len(s) > n else s).replace("|", "\\|")


def to_markdown(res: Result, table: bool = True) -> str:
    c = res.counts()
    out = [
        "# Narration check",
        "",
        f"- Script: {Path(res.script).name} ({c['lines']} lines, {res.lang})",
        f"- A: {res.labels[0]}",
        f"- B: {res.labels[1]}",
        f"- Result: {c['misread']} likely misread · {c['listen']} worth a listen · {c['ok']} ok",
        "",
    ]
    sections = (
        ("misread", "Likely misread", "Both models differ from the script at the same place."),
        ("listen", "Worth a listen", "One model differs from the script, or both do in different places."),
    )
    for key, title, blurb in sections:
        rows = [r for r in res.lines if r.status == key]
        if not rows:
            continue
        out += [f"## {title}", "", blurb, ""]
        for r in rows:
            ln = r.line
            where = ""
            if ln.audio is not None:
                where = f" · {Path(ln.audio).name}"
                if ln.start is not None:
                    where += f" {ln.start:.2f}–{ln.end:.2f} s"
            out += [f"### Line {ln.id}{where}", "", f"- Script: {ln.text}"]
            for tag, m in (("A", r.a), ("B", r.b)):
                heard = m.heard if m.heard.strip() else "(nothing)"
                out.append(f"- {tag} heard: {heard}")
                out += [f"  - {describe(d)}" for d in m.diffs]
                for ch in dict.fromkeys(c for _, c in m.echoed):
                    out.append(f"  - {ch}: written as in the script, which doesn't show which reading was heard")
            if r.both:
                out.append(f"- Both heard: {', '.join(r.both)}")
            pair = _pair_lines(r.ab)
            if len(pair) == 1 and not pair[0].startswith("A "):
                out.append(f"- A and B: {pair[0]}")
            else:
                out.append("- A and B differ:")
                out += [f"  - {p}" for p in pair]
            out.append("")
    echoed = [r for r in res.lines if r.unconfirmed]
    if echoed:
        out += [
            "## Pinned readings not confirmed",
            "",
            "Both models wrote these characters back as written. They have more than one reading,"
            " so the transcripts can't show which one was said.",
            "",
        ]
        out += [f"- Line {r.line.id}: {'、'.join(dict.fromkeys(r.unconfirmed))}" for r in echoed]
        out.append("")
    if table:
        out += ["## All lines", "", "| Line | Result | A | B | Script |", "|---|---|---|---|---|"]
        for r in res.lines:
            out.append(
                f"| {r.line.id} | {STATUS_WORDS[r.status]} | {_cell(r.a)} | {_cell(r.b)} | {_short(r.line.text)} |"
            )
        out.append("")
    return "\n".join(out)
