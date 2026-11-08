from tts_asr_check.text import guess_lang, normalize, tokenize


def test_full_width_and_punctuation_fold_away():
    assert normalize("Ｈｅｌｌｏ，ＷＯＲＬＤ！") == normalize("hello world")
    assert normalize("缪子，的质量。") == normalize("缪子的质量")
    assert normalize("２０２６年") == "2026年"


def test_tokens_keep_original_spans():
    text = "宇宙，Ａ１ 射线"
    toks = tokenize(text)
    assert [t.text for t in toks] == ["宇", "宙", "a1", "射", "线"]
    assert [text[t.start : t.end] for t in toks] == ["宇", "宙", "Ａ１", "射", "线"]


def test_words_numbers_and_apostrophes():
    assert [t.text for t in tokenize("Don’t pay $1,000 or 3.14%.")] == ["don't", "pay", "1000", "or", "3.14", "%"]


def test_kana_is_one_token_per_character():
    assert [t.text for t in tokenize("ｶﾀｶﾅです")] == ["カ", "タ", "カ", "ナ", "で", "す"]


def test_guess_lang():
    assert guess_lang("缪子的质量大约是电子的两百倍。") == "zh"
    assert guess_lang("明日は東京で雨が降ります。") == "ja"
    assert guess_lang("They count the ticks of a strontium atom.") == "en"
