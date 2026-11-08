"""Ways a number can be written, so 2026 and 二〇二六 or 42 and forty-two
are not reported as differences.

Only digits are expanded. A transcript that writes a number in words where
the script uses digits (or the other way round) is accepted when any of the
spellings here matches.
"""

from __future__ import annotations

import itertools
import re

MAX_SPELLINGS = 64

_ZH = "零一二三四五六七八九"
_NUM = re.compile(r"^\d+(\.\d+)?$")
_ORD = re.compile(r"^(\d+)(st|nd|rd|th)$")


def is_number(tok: str) -> bool:
    return bool(_NUM.match(tok) or _ORD.match(tok))


# --- Chinese ---------------------------------------------------------------


def _zh_group(g: int) -> str:
    s, zero = "", False
    for d, unit in zip((g // 1000, g // 100 % 10, g // 10 % 10, g % 10), ("千", "百", "十", "")):
        if d == 0:
            zero = bool(s)
            continue
        if zero:
            s += "零"
            zero = False
        s += _ZH[d] + unit
    return s


def zh_cardinal(n: int) -> str:
    if n == 0:
        return "零"
    units = ("", "万", "亿", "万亿")
    groups = []
    while n:
        groups.append(n % 10000)
        n //= 10000
    out, gap = "", False
    for i in range(len(groups) - 1, -1, -1):
        g = groups[i]
        if g == 0:
            gap = bool(out)
            continue
        if out and (gap or g < 1000):
            out += "零"
        out += _zh_group(g) + units[i]
        gap = False
    return out[1:] if out.startswith("一十") else out


def _zh_liang(s: str) -> str:
    for unit in "千百万亿":
        s = s.replace("二" + unit, "两" + unit)
    return s


def _digits(s: str, zero: str) -> str:
    return "".join(zero if c == "0" else _ZH[int(c)] for c in s)


def zh_spellings(tok: str) -> set[str]:
    if "." in tok:
        whole, frac = tok.split(".", 1)
        heads = {zh_cardinal(int(whole)), _digits(whole, "零")}
        return {h + "点" + _digits(frac, z) for h in heads for z in "零〇"}
    n = int(tok)
    card = zh_cardinal(n)
    out = {card, _zh_liang(card), _digits(tok, "零"), _digits(tok, "〇")}
    if n == 2:
        out.add("两")
    if card.startswith("十"):
        out.add("一" + card)
    return out


# --- Japanese --------------------------------------------------------------


def ja_cardinal(n: int, ichi_sen: bool = False) -> str:
    if n == 0:
        return "零"
    units = ("", "万", "億", "兆")
    i = 0
    parts = []
    while n:
        g = n % 10000
        n //= 10000
        if g:
            s = ""
            for d, unit in zip((g // 1000, g // 100 % 10, g // 10 % 10, g % 10), ("千", "百", "十", "")):
                if d == 0:
                    continue
                if d == 1 and unit in ("百", "十") or d == 1 and unit == "千" and not ichi_sen:
                    s += unit
                else:
                    s += _ZH[d] + unit
            parts.append(s + units[i])
        i += 1
    return "".join(reversed(parts))


def ja_spellings(tok: str) -> set[str]:
    if "." in tok:
        whole, frac = tok.split(".", 1)
        return {ja_cardinal(int(whole)) + "点" + _digits(frac, z) for z in "〇零"}
    n = int(tok)
    return {ja_cardinal(n), ja_cardinal(n, True), _digits(tok, "〇"), _digits(tok, "零")}


# --- English ---------------------------------------------------------------

_ONES = (
    "zero one two three four five six seven eight nine ten eleven twelve thirteen "
    "fourteen fifteen sixteen seventeen eighteen nineteen"
).split()
_TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
_SCALES = ["", "thousand", "million", "billion", "trillion"]
_ORDINAL = {
    "one": "first",
    "two": "second",
    "three": "third",
    "five": "fifth",
    "eight": "eighth",
    "nine": "ninth",
    "twelve": "twelfth",
}


def _under_100(n: int) -> list[str]:
    if n < 20:
        return [_ONES[n]]
    t, o = divmod(n, 10)
    return [_TENS[t]] + ([_ONES[o]] if o else [])


def _under_1000(n: int, use_and: bool) -> list[str]:
    h, r = divmod(n, 100)
    words = [_ONES[h], "hundred"] if h else []
    if r:
        words += (["and"] if h and use_and else []) + _under_100(r)
    return words


def en_cardinal(n: int, use_and: bool = False) -> list[str]:
    if n == 0:
        return ["zero"]
    groups = []
    while n:
        groups.append(n % 1000)
        n //= 1000
    words: list[str] = []
    for i in range(len(groups) - 1, -1, -1):
        g = groups[i]
        if not g:
            continue
        if use_and and i == 0 and words and g < 100:
            words.append("and")
        words += _under_1000(g, use_and) + ([_SCALES[i]] if _SCALES[i] else [])
    return words


def _en_ordinal(words: list[str]) -> list[str]:
    last = words[-1]
    if last in _ORDINAL:
        last = _ORDINAL[last]
    elif last.endswith("y"):
        last = last[:-1] + "ieth"
    else:
        last += "th"
    return words[:-1] + [last]


def en_spellings(tok: str) -> set[str]:
    m = _ORD.match(tok)
    if m:
        n = int(m.group(1))
        return {" ".join(_en_ordinal(en_cardinal(n))), " ".join(_en_ordinal(en_cardinal(n, True)))}
    digit_words = [_ONES[int(c)] for c in tok if c.isdigit()]
    if "." in tok:
        whole, frac = tok.split(".", 1)
        tail = ["point"] + [_ONES[int(c)] for c in frac]
        return {" ".join(en_cardinal(int(whole)) + tail), " ".join(en_cardinal(int(whole), True) + tail)}
    n = int(tok)
    out = {" ".join(en_cardinal(n)), " ".join(en_cardinal(n, True)), " ".join(digit_words)}
    out.add(" ".join("oh" if w == "zero" else w for w in digit_words))
    if 100 <= n < 2000 and n % 100 == 0:
        out.add(" ".join(["a"] + en_cardinal(n)[1:]))  # a hundred, a thousand
    if 1000 <= n <= 9999 and n % 1000:
        hi, lo = divmod(n, 100)
        if lo == 0:
            out.add(" ".join(_under_100(hi) + ["hundred"]))  # nineteen hundred
        elif lo < 10:
            out.add(" ".join(_under_100(hi) + ["oh", _ONES[lo]]))  # twenty oh five
        else:
            out.add(" ".join(_under_100(hi) + _under_100(lo)))  # twenty twenty-six
    return out


# --- token lists -----------------------------------------------------------


def _number_options(tok: str, lang: str) -> list[list[str]]:
    if lang == "en":
        return [s.split() for s in sorted(en_spellings(tok))]
    if not _NUM.match(tok):
        return [[tok]]
    words = zh_spellings(tok) if lang == "zh" else ja_spellings(tok)
    return [list(w) for w in sorted(words)]


def spellings(tokens: list[str], lang: str) -> list[list[str]]:
    """The token list as written, plus versions with each number spelled out.

    ``%`` after a number is read as 百分之… (zh), …パーセント (ja) or
    "percent" (en).
    """
    options: list[list[list[str]]] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        pct = i + 1 < len(tokens) and tokens[i + 1] == "%"
        if is_number(tok):
            opts = [[tok]] + _number_options(tok, lang)
            if pct:
                if lang == "zh":
                    opts = [list("百分之") + o for o in opts] + [[tok, "%"]]
                elif lang == "ja":
                    opts = [o + list("パーセント") for o in opts] + [[tok, "%"]]
                else:
                    opts = [o + ["percent"] for o in opts] + [[tok, "%"]]
                i += 1
            options.append(opts)
        elif tok == "%":
            options.append([["%"], ["percent"] if lang == "en" else list("百分之" if lang == "zh" else "パーセント")])
        else:
            options.append([[tok]])
        i += 1
    out = []
    for combo in itertools.islice(itertools.product(*options), MAX_SPELLINGS):
        out.append([t for part in combo for t in part])
    return out
