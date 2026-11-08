"""Turning a line of text into comparable tokens.

Every language goes through the same steps: Unicode NFKC (full-width letters
and digits become half-width, half-width katakana becomes full-width), case
folding, and dropping punctuation and spacing. Each CJK character or kana is
its own token; runs of letters and digits form one token. Every token keeps
the span of the original text it came from, so a report can quote the
original wording.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

LANGS = ("zh", "en", "ja")


@dataclass(frozen=True)
class Token:
    text: str  # normalised form, compared between script and transcript
    start: int  # span in the original string
    end: int


def is_han(ch: str) -> bool:
    o = ord(ch)
    return (
        0x3400 <= o <= 0x4DBF
        or 0x4E00 <= o <= 0x9FFF
        or 0xF900 <= o <= 0xFAFF
        or 0x20000 <= o <= 0x3134F
        or ch in "〇々〆"
    )


def is_kana(ch: str) -> bool:
    o = ord(ch)
    return 0x3040 <= o <= 0x30FF or 0x31F0 <= o <= 0x31FF


def is_hangul(ch: str) -> bool:
    o = ord(ch)
    return 0xAC00 <= o <= 0xD7AF or 0x1100 <= o <= 0x11FF or 0x3130 <= o <= 0x318F


def _single(ch: str) -> bool:
    """Characters that are a token on their own."""
    return is_han(ch) or is_kana(ch) or is_hangul(ch)


def _wordish(ch: str) -> bool:
    cat = unicodedata.category(ch)
    return cat[0] in "LN" or cat[0] == "M"


_APOSTROPHES = {"’": "'", "‘": "'", "ʼ": "'", "＇": "'"}


def tokenize(text: str) -> list[Token]:
    """Split ``text`` into normalised tokens with their original spans."""
    # Normalise character by character so every output character still knows
    # which input character it came from.
    chars: list[tuple[str, int]] = []
    for i, ch in enumerate(text):
        ch = _APOSTROPHES.get(ch, ch)
        for c in unicodedata.normalize("NFKC", ch).casefold():
            chars.append((c, i))

    tokens: list[Token] = []
    word: list[str] = []
    w_start = w_end = 0

    def flush() -> None:
        nonlocal word
        if word:
            tokens.append(Token("".join(word), w_start, w_end))
            word = []

    n = len(chars)
    for k, (c, i) in enumerate(chars):
        if _single(c):
            flush()
            tokens.append(Token(c, i, i + 1))
            continue
        if _wordish(c) and not _single(c):
            if not word:
                w_start = i
            word.append(c)
            w_end = i + 1
            continue
        prev = chars[k - 1][0] if k else ""
        nxt = chars[k + 1][0] if k + 1 < n else ""
        if word and c == "'" and nxt and _wordish(nxt) and not _single(nxt):
            word.append(c)  # don't, Newton's
            continue
        if word and c == "." and prev.isdigit() and nxt.isdigit():
            word.append(c)  # 3.14
            continue
        if word and c == "," and prev.isdigit() and _three_digits_follow(chars, k + 1):
            continue  # 1,000
        flush()
        if c == "%":
            tokens.append(Token("%", i, i + 1))
    flush()
    return tokens


def _three_digits_follow(chars: list[tuple[str, int]], k: int) -> bool:
    run = "".join(c for c, _ in chars[k : k + 4])
    return len(run) >= 3 and run[:3].isdigit() and (len(run) == 3 or not run[3].isdigit())


def joined(tokens: list[Token] | list[str]) -> str:
    """Tokens back into one comparable string (spaces only between words)."""
    out = ""
    prev_word = False
    for t in tokens:
        s = t.text if isinstance(t, Token) else t
        word = not (len(s) == 1 and _single(s))
        if out and word and prev_word:
            out += " "
        out += s
        prev_word = word
    return out


def normalize(text: str) -> str:
    return joined(tokenize(text))


def hira_to_kata(s: str) -> str:
    return "".join(chr(ord(c) + 0x60) if 0x3041 <= ord(c) <= 0x3096 else c for c in s)


def guess_lang(text: str) -> str:
    """zh, ja or en, from the characters a script uses."""
    kana = sum(1 for c in text if is_kana(c) and c != "ー")
    han = sum(1 for c in text if is_han(c))
    latin = len(re.findall(r"[A-Za-z]", text))
    if kana and kana >= 0.05 * (han + kana):
        return "ja"
    if han and han >= 0.2 * (han + latin):
        return "zh"
    return "en"
