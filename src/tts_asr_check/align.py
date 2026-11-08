"""Splitting one transcript of a whole recording into the script's lines.

Used when the audio is one file with no timings. The transcript's tokens are
aligned to the script's tokens (all lines in a row); each line gets the stretch
of transcript that lines up with it. Words heard between two lines go to the
line before.
"""

from __future__ import annotations

from difflib import SequenceMatcher

from .text import tokenize


def split(lines: list[str], transcript: str) -> list[str]:
    s_toks, bounds = [], [0]
    for line in lines:
        s_toks += [t.text for t in tokenize(line)]
        bounds.append(len(s_toks))
    h = tokenize(transcript)
    h_toks = [t.text for t in h]
    # where[i]: the transcript token that script token i lines up with.
    where = [0] * (len(s_toks) + 1)
    sm = SequenceMatcher(None, s_toks, h_toks, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        for i in range(i1, i2):
            if tag == "equal":
                where[i] = j1 + (i - i1)
            elif tag == "replace":
                where[i] = j1 + (i - i1) * (j2 - j1) // (i2 - i1)
            else:  # delete
                where[i] = j1
    where[len(s_toks)] = len(h_toks)
    pieces, prev = [], 0
    for k in range(len(lines)):
        a = prev
        b = max(where[bounds[k + 1]], a)
        pieces.append("" if a == b else transcript[h[a].start : h[b - 1].end])
        prev = b
    return pieces
