import pytest

from tts_asr_check.numbers import en_spellings, ja_spellings, spellings, zh_cardinal, zh_spellings


@pytest.mark.parametrize(
    "n, words",
    [
        (0, "零"),
        (10, "十"),
        (15, "十五"),
        (105, "一百零五"),
        (110, "一百一十"),
        (2026, "二千零二十六"),
        (10000, "一万"),
        (10005, "一万零五"),
        (100000, "十万"),
        (100010000, "一亿零一万"),
    ],
)
def test_zh_cardinal(n, words):
    assert zh_cardinal(n) == words


def test_zh_spellings_cover_years_and_liang():
    assert {"二〇二六", "二零二六", "两千零二十六"} <= zh_spellings("2026")
    assert "两百" in zh_spellings("200")
    assert "三点一四" in zh_spellings("3.14")


def test_en_spellings():
    assert "forty two" in en_spellings("42")
    assert {"twenty twenty six", "two thousand twenty six", "two thousand and twenty six"} <= en_spellings("2026")
    assert "twenty oh five" in en_spellings("2005")
    assert "twenty first" in en_spellings("21st")
    assert "a hundred" in en_spellings("100")


def test_ja_spellings():
    assert {"二千二十六", "十", "百"} & ja_spellings("2026") == {"二千二十六"}
    assert "十" in ja_spellings("10")


def test_percent_moves_in_chinese():
    assert list("百分之五十") in spellings(["50", "%"], "zh")
    assert ["fifty", "percent"] in spellings(["50", "%"], "en")
