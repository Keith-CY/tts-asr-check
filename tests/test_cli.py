import json
import sys
from pathlib import Path

import numpy as np
import pytest

from tts_asr_check import cli
from tts_asr_check.backends import BackendError, make

FIX = Path(__file__).parent / "fixtures"


def run(capsys, *argv):
    code = cli.main([str(a) for a in argv])
    return code, capsys.readouterr().out


def test_compare_reports_and_exits_1(capsys):
    code, out = run(capsys, "compare", FIX / "muon-zh.json", FIX / "muon-zh.A.json", FIX / "muon-zh.B.json")
    assert code == 1
    assert "1 likely misread · 1 worth a listen · 1 ok" in out
    assert "缪 miù → 妙 miào: different syllable" in out


def test_compare_json(capsys):
    code, out = run(
        capsys, "compare", FIX / "muon-zh.json", FIX / "muon-zh.A.json", FIX / "muon-zh.B.json", "--json", "-"
    )
    data = json.loads(out)
    assert data["summary"] == {"lines": 3, "ok": 1, "listen": 1, "misread": 1}
    assert [ln["status"] for ln in data["lines"]] == ["listen", "misread", "ok"]
    assert data["lines"][1]["both_heard"] == ["妙 miào"]


def test_fail_on(capsys):
    args = ["compare", FIX / "clock-en.txt", FIX / "clock-en.A.jsonl", FIX / "clock-en.B.jsonl"]
    assert run(capsys, *args)[0] == 1
    assert run(capsys, *args, "--fail-on", "misread")[0] == 0
    assert run(capsys, *args, "--fail-on", "never")[0] == 0


def test_clean_run_exits_0(tmp_path, capsys):
    a = tmp_path / "a.json"
    a.write_text(
        json.dumps(
            {
                "1": "宇宙射线撞上大气层会产生大量谬子",
                "2": "谬子的质量大约是电子的200倍",
                "3": "所以它能穿透很厚的岩石",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    code, out = run(capsys, "compare", FIX / "muon-zh.json", a, a)
    assert code == 0
    assert "0 likely misread · 0 worth a listen · 3 ok" in out


def test_whole_transcript_is_split_into_lines(capsys):
    code, out = run(
        capsys, "compare", FIX / "muon-zh.json", FIX / "muon-whole.A.json", FIX / "muon-zh.B.json", "--json", "-"
    )
    data = json.loads(out)
    assert data["lines"][1]["A"]["heard"] == "妙子的质量大约是电子的200倍"


def test_reading_flag(capsys):
    code, out = run(
        capsys,
        "compare",
        FIX / "muon-zh.json",
        FIX / "muon-zh.B.json",
        FIX / "muon-zh.B.json",
        "--reading",
        "缪=móu",
        "--json",
        "-",
    )
    data = json.loads(out)
    # Pinned to móu, the models' miù and miào no longer match.
    assert data["summary"]["misread"] == 2


def test_bad_input_exits_2(tmp_path, capsys):
    assert cli.main(["compare", str(tmp_path / "missing.txt"), "a", "b"]) == 2
    assert (
        cli.main(
            [
                "compare",
                str(FIX / "muon-zh.json"),
                str(FIX / "muon-zh.A.json"),
                str(FIX / "muon-zh.B.json"),
                "--reading",
                "缪",
            ]
        )
        == 2
    )


def test_readings_lists_guessed_polyphones(tmp_path, capsys):
    p = tmp_path / "s.txt"
    p.write_text("缪子的质量\n", encoding="utf-8")
    code, out = run(capsys, "readings", p)
    assert "[缪 móu? miào/miù/móu]" in out
    code, out = run(capsys, "readings", p, "--reading", "缪=miù")
    assert "miù" in out and "[" not in out.split("\n")[1]


class Fake:
    """Hears the text stored for the clip's first sample value."""

    def __init__(self, name, texts):
        self.name, self.model, self.texts = name, "fake", texts

    def transcribe(self, audio, lang):
        return self.texts[int(audio[0])]


def test_check_with_fake_backends(tmp_path, monkeypatch, capsys):
    script = tmp_path / "s.txt"
    script.write_text("缪子的质量大约是电子的两百倍。\n所以它能穿透很厚的岩石。\n", encoding="utf-8")
    clips = []
    for i in range(2):
        clips.append(tmp_path / f"{i}.wav")
        clips[-1].write_bytes(b"")
    monkeypatch.setattr(cli, "load_audio", lambda path, *a: np.array([float(Path(path).stem)], dtype=np.float32))
    fakes = iter(
        [
            Fake("a", ["妙子的质量大约是电子的200倍", "所以他能穿透很厚的岩石"]),
            Fake("b", ["妙子的质量大约是电子的两百倍", "所以它能穿透很厚的岩石"]),
        ]
    )
    monkeypatch.setattr(cli, "make", lambda spec: next(fakes))
    out_dir = tmp_path / "heard"
    code, out = run(
        capsys,
        "check",
        script,
        *clips,
        "--asr",
        "x",
        "--asr",
        "y",
        "--reading",
        "缪=miù",
        "--save-transcripts",
        out_dir,
        "--json",
        tmp_path / "r.json",
    )
    assert code == 1
    assert "Likely misread" in out
    saved = json.loads((out_dir / "A.json").read_text(encoding="utf-8"))
    assert saved["lines"]["1"] == "妙子的质量大约是电子的200倍"
    assert json.loads((tmp_path / "r.json").read_text(encoding="utf-8"))["summary"]["misread"] == 1


def test_check_needs_two_models(tmp_path, capsys):
    script = tmp_path / "s.txt"
    script.write_text("a\n", encoding="utf-8")
    (tmp_path / "a.wav").write_bytes(b"")
    assert cli.main(["check", str(script), str(tmp_path / "a.wav"), "--asr", "x"]) == 2


def test_backend_plugin(tmp_path, monkeypatch):
    (tmp_path / "my_asr.py").write_text(
        "class B:\n    name = 'mine'\n    def __init__(self, model): self.model = model or 'm'\n"
        "    def transcribe(self, audio, lang): return 'hi'\n"
        "def factory(model): return B(model)\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    b = make("my_asr:factory=tiny")
    assert (b.name, b.model, b.transcribe(None, "en")) == ("mine", "tiny", "hi")
    with pytest.raises(BackendError):
        make("nope")
    sys.modules.pop("my_asr", None)


def test_backend_load_failure_is_reported_not_raised(tmp_path, monkeypatch, capsys):
    script = tmp_path / "s.txt"
    script.write_text("a\n", encoding="utf-8")
    (tmp_path / "a.wav").write_bytes(b"")
    monkeypatch.setattr(cli, "load_audio", lambda *a, **k: np.zeros(1, dtype=np.float32))

    def broken(spec):
        raise OSError("no such model")

    monkeypatch.setattr(cli, "make", broken)
    assert cli.main(["check", str(script), str(tmp_path / "a.wav"), "--asr", "x", "--asr", "y"]) == 2
    assert "could not load x: OSError: no such model" in capsys.readouterr().err
