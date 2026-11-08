from tts_asr_check.align import split


def test_split_a_whole_transcript_into_lines():
    lines = ["宇宙射线撞上大气层，会产生大量缪子。", "缪子的质量大约是电子的两百倍。", "所以它能穿透很厚的岩石。"]
    heard = "宇宙射线撞上大气层会产生大量妙子 妙子的质量大约是电子的200倍 所以他能穿透很厚的岩石"
    assert split(lines, heard) == [
        "宇宙射线撞上大气层会产生大量妙子",
        "妙子的质量大约是电子的200倍",
        "所以他能穿透很厚的岩石",
    ]


def test_a_line_not_heard_comes_back_empty():
    lines = ["one two three", "four five", "six seven"]
    assert split(lines, "one two three six seven") == ["one two three", "", "six seven"]


def test_extra_words_go_to_the_line_before():
    lines = ["one two", "three four"]
    assert split(lines, "one two uh three four") == ["one two uh", "three four"]
