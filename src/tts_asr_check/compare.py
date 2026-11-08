"""Comparing a transcript with the script, and two transcripts with each other."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from difflib import SequenceMatcher

from . import ja, zh
from .numbers import is_number, spellings
from .text import Token, is_han, joined, tokenize

# Differences that mean the audio may not say what the script says.
KINDS = {
    "sound": "different syllable",
    "tone": "same syllable, different tone",
    "polyphone": "another reading of a character with several",
    "word": "different words",
    "missing": "not heard",
    "extra": "heard, not in the script",
}
# Differences in writing only; the sound is the same.
SAME_KINDS = {
    "homophone": "same sound, other characters",
    "number": "number written another way",
    "spelling": "spacing or kana spelling",
    "reading": "same reading",
}
_WORST = ("sound", "tone", "polyphone")


@dataclass
class Diff:
    kind: str
    script: str  # the script's wording at this spot ("" for extra)
    heard: str  # the transcript's wording at this spot ("" for missing)
    start: int  # span of script tokens, [start, end)
    end: int
    script_reading: str = ""
    heard_reading: str = ""
    options: list[str] = field(default_factory=list)  # readings a polyphonic character can have

    def as_dict(self) -> dict:
        d = asdict(self)
        return {k: v for k, v in d.items() if v not in ("", [])}


@dataclass
class Match:
    heard: str
    verdict: str  # exact | same | differs
    diffs: list[Diff] = field(default_factory=list)
    same: list[Diff] = field(default_factory=list)
    # Script characters with a pinned reading and several readings in use that
    # the transcript wrote back unchanged: which reading was heard can't be told.
    # (script token index, character)
    echoed: list[tuple[int, str]] = field(default_factory=list)

    def as_dict(self) -> dict:
        d = {
            "heard": self.heard,
            "verdict": self.verdict,
            "diffs": [d.as_dict() for d in self.diffs],
            "same": [d.as_dict() for d in self.same],
        }
        if self.echoed:
            d["echoed"] = [c for _, c in self.echoed]
        return d


def _span(text: str, toks: list[Token]) -> str:
    return text[toks[0].start : toks[-1].end] if toks else ""


def _nospace(tokens: list[str]) -> str:
    return "".join(tokens)


def _spelled_alike(s: list[str], h: list[str], lang: str) -> bool:
    if _nospace(s) == _nospace(h):
        return True
    hs = {_nospace(x) for x in spellings(h, lang)}
    return any(_nospace(x) in hs for x in spellings(s, lang))


class _Side:
    """One text, its tokens and (for Chinese) the reading of each character."""

    def __init__(self, text: str, lang: str, pinned: dict[str, list[str]] | None = None):
        self.text = text
        self.toks = tokenize(text)
        self.lang = lang
        self.readings = zh.readings(text, pinned) if lang == "zh" else {}

    def reading(self, tok: Token) -> zh.Reading | None:
        return self.readings.get(tok.start) if len(tok.text) == 1 and is_han(tok.text) else None


def _fresh_readings(tokens: list[str]) -> list[zh.Reading | None]:
    """Readings for a spelled-out number, which has no place in the original text."""
    text = "".join(tokens)
    r = zh.readings(text)
    out, at = [], 0
    for t in tokens:
        out.append(r.get(at) if len(t) == 1 else None)
        at += len(t)
    return out


def _unknown(ch: str, r: zh.Reading) -> str | None:
    """A transcript that wrote a pinned character with several readings could
    have heard any of them: show them all instead of the pinned one."""
    if r.pinned and zh.polyphonic(ch):
        return "/".join(zh.marks(o) for o in sorted(r.options))
    return None


def _zh_chunk(S: list[Token], H: list[Token], s: _Side, h: _Side, pair: bool):
    """Best reading match between two runs of characters.

    Returns ``(kinds, script_readings, heard_readings, options, as_written)``
    or None when the lengths never line up. ``kinds`` has one entry per
    character (None: same sound); ``as_written`` is False when the match
    needed a number spelled out, so the characters don't map to tokens.
    """
    s_texts, h_texts = [t.text for t in S], [t.text for t in H]
    s_opts = [(s_texts, [s.reading(t) for t in S], True)]
    h_opts = [(h_texts, [h.reading(t) for t in H], True)]
    if any(is_number(t) for t in s_texts):
        s_opts += [(sp, _fresh_readings(sp), False) for sp in spellings(s_texts, "zh")[1:]]
    if any(is_number(t) for t in h_texts):
        h_opts += [(sp, _fresh_readings(sp), False) for sp in spellings(h_texts, "zh")[1:]]
    best = None
    for st, sr, s_written in s_opts:
        for ht, hr, h_written in h_opts:
            if len(st) != len(ht) or None in sr or None in hr:
                continue
            kinds, s_say, h_say, opts = [], [], [], []
            for a, b, ra, rb in zip(st, ht, sr, hr):
                if a == b:
                    kind, x, y = None, ra.meant, ra.meant
                elif pair:
                    kind, x, y = zh.compare_heard(ra, rb)
                    x, y = _unknown(a, ra) or x, _unknown(b, rb) or y
                else:
                    kind, y = zh.compare_char(ra, rb)
                    x = ra.meant
                    if kind == "polyphone":
                        opts = sorted(zh.marks(o) for o in ra.options)
                kinds.append(kind)
                s_say.append(x if "/" in x else zh.marks(x))
                h_say.append(y if "/" in y else zh.marks(y))
            score = sum(k is not None for k in kinds)
            if best is None or score < best[0]:
                best = (score, (kinds, s_say, h_say, opts, s_written and h_written))
    return best[1] if best else None


def compare(
    script: str, heard: str, lang: str, pinned: dict[str, list[str]] | None = None, pair: bool = False
) -> Match:
    """What differs between ``script`` and ``heard``.

    With ``pair`` the two texts are both transcripts: a Chinese character
    counts as the same when the two share a likely reading.
    """
    # Pinned readings say how the script's characters are meant; a transcript
    # that writes the same character is read the same way.
    s = _Side(script, lang, pinned)
    h = _Side(heard, lang, pinned)
    sm = SequenceMatcher(None, [t.text for t in s.toks], [t.text for t in h.toks], autojunk=False)
    diffs: list[Diff] = []
    same: list[Diff] = []
    echoed: list[tuple[int, str]] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for i in range(i1, i2):
                r = s.reading(s.toks[i])
                if r is not None and r.pinned and zh.polyphonic(s.toks[i].text):
                    echoed.append((i, s.toks[i].text))
            continue
        S, H = s.toks[i1:i2], h.toks[j1:j2]
        d = Diff("", _span(script, S), _span(heard, H), i1, i2)
        if tag == "delete":
            d.kind = "missing"
            diffs.append(d)
            continue
        if tag == "insert":
            d.kind = "extra"
            diffs.append(d)
            continue
        st, ht = [t.text for t in S], [t.text for t in H]
        if _spelled_alike(st, ht, lang):
            d.kind = "number" if any(is_number(t) for t in st + ht) else "spelling"
            same.append(d)
            continue
        if lang == "zh":
            r = _zh_chunk(S, H, s, h, pair)
            if r is not None:
                kinds, s_say, h_say, d.options, as_written = r
                bad = [k for k, kind in enumerate(kinds) if kind is not None]
                if not bad:
                    d.kind = "homophone"
                    d.script_reading, d.heard_reading = " ".join(s_say), " ".join(h_say)
                    same.append(d)
                    continue
                d.kind = next(k for k in _WORST if k in kinds)
                lo, hi = (bad[0], bad[-1] + 1) if as_written else (0, len(kinds))
                if as_written:
                    # Only the characters that sound different, not their homophone neighbours.
                    d.script, d.heard = _span(script, S[lo:hi]), _span(heard, H[lo:hi])
                    d.start, d.end = i1 + lo, i1 + hi
                d.script_reading, d.heard_reading = " ".join(s_say[lo:hi]), " ".join(h_say[lo:hi])
                diffs.append(d)
                continue
        if lang == "ja" and ja.same_sound(joined(st), joined(ht)):
            d.kind = "reading"
            same.append(d)
            continue
        d.kind = "word"
        diffs.append(d)
    if diffs and lang == "ja" and ja.available():
        rs, rh = ja.reading(joined(s.toks)), ja.reading(joined(h.toks))
        if rs is not None and rs == rh:
            for d in diffs:
                d.kind = "reading"
            same += diffs
            diffs = []
    if diffs:
        verdict = "differs"
    elif same:
        verdict = "same"
    else:
        verdict = "exact"
    return Match(heard, verdict, diffs, same, [] if pair else echoed)


def _bounds(d: Diff) -> tuple[float, float]:
    return (d.start - 0.5, d.start + 0.5) if d.start == d.end else (d.start, d.end)


def overlap(a: Diff, b: Diff) -> bool:
    (a0, a1), (b0, b1) = _bounds(a), _bounds(b)
    return max(a0, b0) < min(a1, b1)


def status(a: Match, b: Match) -> str:
    """ok, listen (one model differs, or both in different places) or misread
    (both models differ from the script at the same place)."""
    if not a.diffs and not b.diffs:
        return "ok"
    if a.diffs and b.diffs and any(overlap(x, y) for x in a.diffs for y in b.diffs):
        return "misread"
    return "listen"


def both_heard(a: Match, b: Match, lang: str, pinned: dict[str, list[str]] | None = None) -> list[str]:
    """Places where both models heard the same thing (or, in Chinese, the same
    sound) instead of the script."""
    out = []
    for x in a.diffs:
        for y in b.diffs:
            if (x.start, x.end) != (y.start, y.end) or not x.heard or not y.heard:
                continue
            if compare(x.heard, y.heard, lang, pinned, pair=True).verdict == "differs":
                continue
            heard = x.heard if joined(tokenize(x.heard)) == joined(tokenize(y.heard)) else f"{x.heard} / {y.heard}"
            out.append(f"{heard} {x.heard_reading}".strip())
    return out


def unconfirmed(a: Match, b: Match) -> list[str]:
    """Pinned readings both models only wrote back: nothing confirms them."""
    both = {i for i, _ in a.echoed} & {i for i, _ in b.echoed}
    return [c for i, c in a.echoed if i in both]
