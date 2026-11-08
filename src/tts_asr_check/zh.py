"""Chinese readings with pypinyin.

The script's characters get the reading meant in context (pypinyin's phrase
dictionary, or a reading the user pinned). A transcript's characters count
with their reading in context and their most common reading: a recogniser
that heard dá writes 答, not 打 (which can be read dá, but rarely is).

Readings are kept as pypinyin ``TONE3`` strings (``miu4``, ``lv4``, ``zi5``)
and shown with tone marks (``miù``).
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from functools import lru_cache

from pypinyin import Style, pinyin
from pypinyin.constants import PHRASES_DICT

from .text import is_han

_MARKS = {
    "a": "āáǎà",
    "e": "ēéěè",
    "i": "īíǐì",
    "o": "ōóǒò",
    "u": "ūúǔù",
    "v": "ǖǘǚǜ",
}
_UNMARK = {m: (base, n + 1) for base, ms in _MARKS.items() for n, m in enumerate(ms)}


@dataclass(frozen=True)
class Reading:
    meant: str  # TONE3, e.g. "miu4": the reading in context (or pinned)
    options: frozenset[str]  # every reading the character has
    guessed: bool  # several readings in common use, and no phrase or pinned reading decides it
    likely: frozenset[str] = frozenset()  # the reading in context and the character's most common one
    pinned: bool = False  # the reading was given by the user


def to_tone3(s: str) -> str:
    """``miù``, ``miu4``, ``lü4``, ``lv4`` or ``zi`` → ``miu4``, ``lv4``, ``zi5``."""
    s = s.strip().lower().replace("ü", "v").replace("u:", "v")
    tone = 5
    base = ""
    for ch in s:
        if ch in _UNMARK:
            b, tone = _UNMARK[ch]
            base += b
        else:
            base += ch
    m = re.fullmatch(r"([a-z]+)([1-5])?", base)
    if not m:
        raise ValueError(f"not a pinyin syllable: {s!r}")
    return m.group(1) + (m.group(2) or str(tone))


def marks(tone3: str) -> str:
    """``miu4`` → ``miù``; ``lv4`` → ``lǜ``; ``zi5`` → ``zi``."""
    m = re.fullmatch(r"([a-z]+)([1-5])", tone3)
    if not m:
        return tone3.replace("v", "ü")
    base, tone = m.group(1), int(m.group(2))
    if tone == 5:
        return base.replace("v", "ü")
    if "a" in base:
        i = base.index("a")
    elif "e" in base:
        i = base.index("e")
    elif "ou" in base:
        i = base.index("o")
    else:
        i = max(base.rfind(v) for v in "iouv")
    out = base[:i] + _MARKS[base[i]][tone - 1] + base[i + 1 :]
    return out.replace("v", "ü")


def toneless(tone3: str) -> str:
    return tone3.rstrip("12345")


@lru_cache(maxsize=4096)
def options(ch: str) -> tuple[str, ...]:
    """Every reading pypinyin knows for one character, most common first."""
    r = pinyin(ch, style=Style.TONE3, heteronym=True, neutral_tone_with_five=True, errors="ignore")
    return tuple(r[0]) if r else ()


@lru_cache(maxsize=1)
def _phrase_counts() -> dict[str, Counter]:
    """How often each reading of a character appears in pypinyin's phrases."""
    counts: dict[str, Counter] = defaultdict(Counter)
    for phrase, rs in PHRASES_DICT.items():
        if len(phrase) == len(rs):
            for c, r in zip(phrase, rs):
                try:
                    counts[c][to_tone3(r[0])] += 1
                except ValueError:
                    pass
    return counts


@lru_cache(maxsize=4096)
def polyphonic(ch: str) -> bool:
    """Whether a character has more than one reading in common use.

    pypinyin lists rare and archaic readings too (它 tuó); a reading counts
    when it appears in at least 2 of pypinyin's phrases and 1% of the
    character's phrases. A neutral tone next to a toned reading of the same
    syllable (子 zi / zǐ) is not a second reading.
    """
    if len(options(ch)) < 2:
        return False
    counts = _phrase_counts().get(ch)
    if not counts:
        return True  # no data: assume it can go either way
    toned = {toneless(r) for r in counts if not r.endswith("5")}
    kept = {r: n for r, n in counts.items() if not (r.endswith("5") and toneless(r) in toned)}
    total = sum(kept.values())
    return sum(1 for n in kept.values() if n >= 2 and n >= 0.01 * total) >= 2


def _covered_by_phrase(run: str, k: int) -> bool:
    for size in range(2, 9):
        for start in range(max(0, k - size + 1), min(k, len(run) - size) + 1):
            if run[start : start + size] in PHRASES_DICT:
                return True
    return False


def parse_pinned(pinned: dict[str, str]) -> dict[str, list[str]]:
    """``{"缪": "miù", "行长": "hang2 zhang3"}`` → TONE3 lists, one per character."""
    out = {}
    for key, value in pinned.items():
        sylls = [to_tone3(p) for p in re.split(r"[\s,']+", value.strip()) if p]
        chars = [c for c in key if is_han(c)]
        if len(sylls) != len(chars):
            raise ValueError(f"reading {value!r} has {len(sylls)} syllables for {len(chars)} characters in {key!r}")
        out["".join(chars)] = sylls
    return out


def readings(text: str, pinned: dict[str, list[str]] | None = None) -> dict[int, Reading]:
    """The reading of each Han character in ``text``, by its index."""
    out: dict[int, Reading] = {}
    for m in re.finditer(r"[^\W\d_a-zA-Z]+", text):
        idx = [m.start() + j for j, c in enumerate(m.group()) if is_han(c)]
        run = "".join(text[i] for i in idx)
        if not run:
            continue
        guess = pinyin(run, style=Style.TONE3, neutral_tone_with_five=True, errors="ignore")
        if len(guess) == len(run):
            meant = [g[0] for g in guess]
        else:  # a character pypinyin doesn't know: compare it by its shape only
            meant = [(options(c) or ("?" + c,))[0] for c in run]
        fixed = [False] * len(run)
        for key, sylls in (pinned or {}).items():
            start = run.find(key)
            while start >= 0:
                for j, syl in enumerate(sylls):
                    meant[start + j] = syl
                    fixed[start + j] = True
                start = run.find(key, start + 1)
        for j, (i, c) in enumerate(zip(idx, run)):
            opts = frozenset(options(c)) | {meant[j]}
            likely = {meant[j]} | set(options(c)[:1])
            guessed = not fixed[j] and not meant[j].endswith("5") and polyphonic(c) and not _covered_by_phrase(run, j)
            out[i] = Reading(meant[j], opts, guessed, frozenset(likely), fixed[j])
    return out


def compare_char(script: Reading, heard: Reading) -> tuple[str | None, str]:
    """How one heard character relates to one script character.

    Returns ``(kind, heard_reading)``. ``kind`` is ``None`` when the heard
    character can be read the way the script means it; otherwise ``tone``
    (same syllable, other tone), ``polyphone`` (the script's character has
    several readings, none was pinned, and the recogniser heard one of the
    others) or ``sound`` (another syllable).
    """
    if script.meant in heard.likely:
        return None, script.meant
    # Particles said with a neutral tone (的 地 得 着 了) are one sound written
    # several ways; which one a recogniser writes is spelling, not hearing.
    neutral = {r for r in script.options if r.endswith("5")} & heard.likely
    if neutral:
        return None, sorted(neutral)[0]
    if script.meant.endswith("5") and script.meant in heard.options:
        return None, script.meant
    if script.guessed:
        both = sorted(script.options & heard.likely)
        if both:
            return "polyphone", both[0]
    same = sorted(r for r in heard.likely if toneless(r) == toneless(script.meant))
    if same:
        return "tone", same[0]
    return "sound", heard.meant


def compare_heard(a: Reading, b: Reading) -> tuple[str | None, str, str]:
    """Two transcripts against each other: a shared likely reading counts as the same."""
    shared = a.likely & b.likely
    if shared:
        r = sorted(shared)[0]
        return None, r, r
    particle = ({r for r in a.options if r.endswith("5")} & b.likely) or (
        {r for r in b.options if r.endswith("5")} & a.likely
    )
    if particle:
        r = sorted(particle)[0]
        return None, r, r
    for ra in sorted(a.likely):
        for rb in sorted(b.likely):
            if toneless(ra) == toneless(rb):
                return "tone", ra, rb
    return "sound", a.meant, b.meant
