import json

import pytest

from tts_asr_check.script import ScriptError, assign_audio, load


def test_text_script(tmp_path):
    p = tmp_path / "s.txt"
    p.write_text("first line\n\nsecond line\n", encoding="utf-8")
    s = load(p)
    assert [(ln.id, ln.text) for ln in s.lines] == [("1", "first line"), ("2", "second line")]


def test_json_script_with_readings_and_audio(tmp_path):
    p = tmp_path / "s.json"
    p.write_text(
        json.dumps(
            {
                "lang": "zh",
                "readings": {"缪": "miù"},
                "lines": [{"id": "a", "text": "缪子", "audio": "a.wav", "readings": {"重": "zhòng"}}],
            }
        ),
        encoding="utf-8",
    )
    s = load(p)
    assert s.lang == "zh" and s.readings == {"缪": "miù"}
    assert s.lines[0].audio == tmp_path / "a.wav" and s.lines[0].readings == {"重": "zhòng"}
    assert assign_audio(s, []) == "lines"


def test_srt_cues_carry_timings(tmp_path):
    p = tmp_path / "s.srt"
    p.write_text(
        "1\n00:00:01,000 --> 00:00:03,500\n第一句\n\n2\n00:00:04,000 --> 00:00:06,250\n<i>第二句</i>\n",
        encoding="utf-8",
    )
    s = load(p)
    assert [(ln.text, ln.start, ln.end) for ln in s.lines] == [("第一句", 1.0, 3.5), ("第二句", 4.0, 6.25)]
    assert assign_audio(s, [tmp_path / "all.wav"]) == "lines"


def test_audio_folder_matched_by_line_id(tmp_path):
    p = tmp_path / "s.jsonl"
    p.write_text('{"id": "intro", "text": "a"}\n{"id": "outro", "text": "b"}\n', encoding="utf-8")
    d = tmp_path / "clips"
    d.mkdir()
    for name in ("outro.wav", "intro.wav"):
        (d / name).write_bytes(b"")
    s = load(p)
    assert assign_audio(s, [d]) == "lines"
    assert [ln.audio.name for ln in s.lines] == ["intro.wav", "outro.wav"]


def test_one_untimed_recording_is_whole_mode(tmp_path):
    p = tmp_path / "s.txt"
    p.write_text("a\nb\n", encoding="utf-8")
    s = load(p)
    assert assign_audio(s, [tmp_path / "all.wav"]) == "whole"


def test_wrong_number_of_files(tmp_path):
    p = tmp_path / "s.txt"
    p.write_text("a\nb\nc\n", encoding="utf-8")
    with pytest.raises(ScriptError):
        assign_audio(load(p), [tmp_path / "1.wav", tmp_path / "2.wav"])


def test_repeated_ids(tmp_path):
    p = tmp_path / "s.json"
    p.write_text(json.dumps([{"id": "x", "text": "a"}, {"id": "x", "text": "b"}]), encoding="utf-8")
    with pytest.raises(ScriptError):
        load(p)
