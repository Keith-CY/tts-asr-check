import pytest

from tts_asr_check import ja, zh
from tts_asr_check.compare import Diff, Match, both_heard, compare, overlap, status, unconfirmed

PIN = zh.parse_pinned({"缪": "miù"})
LINE = "缪子的质量大约是电子的两百倍。"


def test_exact_after_normalising():
    assert compare(LINE, "缪子的质量大约是电子的两百倍", "zh", PIN).verdict == "exact"


def test_homophone_and_traditional_characters_are_the_same_sound():
    m = compare(LINE, "謬子的質量大約是電子的兩百倍", "zh", PIN)
    assert m.verdict == "same" and {d.kind for d in m.same} == {"homophone"}


def test_numbers_written_either_way():
    m = compare(LINE, "缪子的质量大约是电子的200倍", "zh", PIN)
    assert m.verdict == "same" and [d.kind for d in m.same] == ["number"]


def test_the_miu_miao_case():
    m = compare(LINE, "妙子的质量大约是电子的两百倍", "zh", PIN)
    assert m.verdict == "differs"
    (d,) = m.diffs
    assert (d.kind, d.script, d.heard, d.script_reading, d.heard_reading) == ("sound", "缪", "妙", "miù", "miào")


def test_unpinned_polyphone_is_flagged_with_its_readings():
    (d,) = compare(LINE, "妙子的质量大约是电子的两百倍", "zh").diffs
    assert d.kind == "polyphone" and "miù" in d.options and "móu" in d.options


def test_missing_and_extra():
    m = compare("所以它能穿透很厚的岩石", "所以它能穿透岩石谢谢观看", "zh")
    assert [(d.kind, d.script, d.heard) for d in m.diffs] == [("missing", "很厚的", ""), ("extra", "", "谢谢观看")]


def test_english_words_and_numbers():
    assert (
        compare("Lose one second in 40 billion years.", "lose one second in forty billion years", "en").verdict
        == "same"
    )
    m = compare("a single strontium atom", "a single strontium Adam", "en")
    assert [(d.kind, d.script, d.heard) for d in m.diffs] == [("word", "atom", "Adam")]
    assert compare("Send an e-mail.", "Send an email.", "en").verdict == "same"


def test_japanese_numbers_and_kana():
    assert compare("気温は十度まで下がります。", "気温は10度まで下がります", "ja").verdict == "same"
    assert compare("気温は十度まで下がります。", "気温は10度まで上がります", "ja").verdict == "differs"
    assert compare("カタカナです", "かたかなです", "ja").verdict == "same"


@pytest.mark.skipif(not ja.available(), reason="needs the ja extra (fugashi + UniDic-lite)")
def test_japanese_kanji_and_kana_by_reading():
    assert compare("傘を持って行って下さい。", "傘を持っていってください", "ja").verdict == "same"
    assert compare("明日は東京で雨が降ります。", "明日は東京で飴が降ります", "ja").verdict == "same"


def test_two_transcripts_compared_by_sound():
    assert compare("妙子的质量", "妙子的質量", "zh", pair=True).verdict == "same"
    m = compare("妙子的质量", "谬子的质量", "zh", pair=True)
    assert [(d.script_reading, d.heard_reading) for d in m.diffs] == [("miào", "miù")]


def _m(*spans):
    return Match("", "differs" if spans else "exact", [Diff("word", "", "", a, b) for a, b in spans])


def test_status_rules():
    assert status(_m(), _m()) == "ok"
    assert status(_m((3, 4)), _m()) == "listen"
    assert status(_m((3, 4)), _m((3, 5))) == "misread"
    assert status(_m((0, 1)), _m((6, 7))) == "listen"  # both differ, in different places
    assert status(_m((3, 3)), _m((2, 3))) == "misread"  # extra word right after a changed one


def test_overlap_of_insertions():
    assert overlap(Diff("extra", "", "x", 4, 4), Diff("extra", "", "y", 4, 4))
    assert not overlap(Diff("extra", "", "x", 4, 4), Diff("word", "", "", 6, 7))


def test_both_heard_the_same_wrong_thing():
    a = compare(LINE, "妙子的质量大约是电子的200倍", "zh", PIN)
    b = compare(LINE, "妙子的质量大约是电子的两百倍", "zh", PIN)
    assert status(a, b) == "misread"
    assert both_heard(a, b, "zh", PIN) == ["妙 miào"]


def test_both_heard_compares_by_sound():
    a = compare("缪子的质量很大", "妙子的质量很大", "zh", PIN)
    b = compare("缪子的质量很大", "庙子的质量很大", "zh", PIN)
    assert status(a, b) == "misread"
    assert both_heard(a, b, "zh", PIN) == ["妙 / 庙 miào"]


def test_pinned_polyphone_written_back_is_unconfirmed():
    a = compare(LINE, LINE, "zh", PIN)
    b = compare(LINE, "谬子的质量大约是电子的两百倍", "zh", PIN)
    assert [c for _, c in a.echoed] == ["缪"]
    assert unconfirmed(a, a) == ["缪"]
    assert unconfirmed(a, b) == []  # B's 谬 can only be miù
    assert compare(LINE, LINE, "zh").echoed == []  # nothing pinned, nothing to confirm


def test_a_difference_is_trimmed_to_the_characters_that_sound_different():
    (d,) = compare("宇宙射线撞上大气层", "宇宙舍现状上大气层", "zh").diffs
    assert (d.kind, d.script, d.heard, d.script_reading, d.heard_reading) == ("tone", "射", "舍", "shè", "shě")
    assert (d.start, d.end) == (2, 3)
