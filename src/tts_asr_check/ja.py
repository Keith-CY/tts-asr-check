"""Japanese readings, when fugashi and a UniDic dictionary are installed.

With them, 下さい and ください, or 一つ and ひとつ, count as the same sound.
Without them, only hiragana and katakana spellings of the same kana count as
the same; kanji against kana is reported as a difference.
"""

from __future__ import annotations

from functools import lru_cache

from .text import hira_to_kata, is_kana


@lru_cache(maxsize=1)
def _tagger():
    try:
        import fugashi
    except ImportError:
        return None
    try:
        return fugashi.Tagger()
    except Exception:  # no dictionary installed
        return None


def available() -> bool:
    return _tagger() is not None


_O_ROW = set("オコソトノホモヨロヲゴゾドボポョォ")
_E_ROW = set("エケセテネヘメレゲゼデベペェ")


def _fold(s: str) -> str:
    """Katakana, with long-vowel spellings folded together (トウキョウ = トーキョー)."""
    out: list[str] = []
    for c in hira_to_kata(s):
        prev = out[-1] if out else ""
        if c == "ー" and prev:
            continue
        if c == "ウ" and prev in _O_ROW:
            continue
        if c == "イ" and prev in _E_ROW:
            continue
        out.append(c)
    return "".join(out)


@lru_cache(maxsize=4096)
def reading(text: str) -> str | None:
    """Katakana reading of ``text``; None when a word has no known reading."""
    if not text:
        return ""
    tagger = _tagger()
    if tagger is None:
        return _fold(text) if all(is_kana(c) for c in text) else None
    parts = []
    for word in tagger(text):
        kana = getattr(word.feature, "kana", None) or getattr(word.feature, "pron", None)
        if kana and kana != "*":
            parts.append(kana)
        elif all(is_kana(c) for c in word.surface):
            parts.append(word.surface)
        elif word.surface.isdigit():
            parts.append(word.surface)
        else:
            return None
    return _fold("".join(parts))


def same_sound(a: str, b: str) -> bool:
    if _fold(a) == _fold(b) and all(is_kana(c) for c in a + b):
        return True
    ra, rb = reading(a), reading(b)
    return ra is not None and ra == rb
