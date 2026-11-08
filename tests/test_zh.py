import pytest

from tts_asr_check import zh


@pytest.mark.parametrize(
    "given, tone3", [("miù", "miu4"), ("miu4", "miu4"), ("lǜ", "lv4"), ("lü4", "lv4"), ("zi", "zi5")]
)
def test_to_tone3(given, tone3):
    assert zh.to_tone3(given) == tone3


@pytest.mark.parametrize(
    "tone3, shown", [("miu4", "miù"), ("miao4", "miào"), ("lv4", "lǜ"), ("zi5", "zi"), ("gou3", "gǒu")]
)
def test_marks(tone3, shown):
    assert zh.marks(tone3) == shown


def test_unpinned_polyphone_is_a_guess():
    r = zh.readings("缪子的质量")
    assert r[0].guessed
    assert {"miu4", "mou2"} <= r[0].options


def test_pinned_reading_wins():
    r = zh.readings("缪子的质量", zh.parse_pinned({"缪": "miù"}))
    assert r[0].meant == "miu4" and not r[0].guessed


def test_phrase_decides_polyphone():
    r = zh.readings("银行行长")
    assert [r[i].meant for i in range(4)] == ["yin2", "hang2", "hang2", "zhang3"]
    assert not any(x.guessed for x in r.values())


def test_rare_readings_do_not_make_a_polyphone():
    assert not zh.polyphonic("它")  # pypinyin also lists tuó
    assert zh.polyphonic("行") and zh.polyphonic("缪")


def test_pinned_reading_length_must_match():
    with pytest.raises(ValueError):
        zh.parse_pinned({"缪子": "miù"})


def _one(script, heard, pinned=None):
    s = zh.readings(script, zh.parse_pinned(pinned or {}))[0]
    h = zh.readings(heard)[0]
    return zh.compare_char(s, h)


def test_compare_char_kinds():
    assert _one("缪", "妙", {"缪": "miù"}) == ("sound", "miao4")
    assert _one("缪", "谬", {"缪": "miù"}) == (None, "miu4")
    assert _one("缪", "妙") == ("polyphone", "miao4")
    assert _one("答", "打")[0] == "tone"  # 打 can be dá, but almost never is
    assert _one("地", "的")[0] is None  # particles: one sound, several spellings


def test_particles_match_between_transcripts():
    a, b = zh.readings("重得多"), zh.readings("重的多")
    assert zh.compare_heard(a[1], b[1])[0] is None
