# tts-asr-check

A text-to-speech voice we used for a narrated video read 缪 (miù, as in 缪子, "muon") as 妙 (miào).
Whisper medium wrote 妙 for both readings, so a check with Whisper alone missed it; Qwen3-ASR told them apart.
Since then every narrated line is checked by two different speech recognisers, and this tool is that check.

You give it the narration audio and the script it was meant to say. Two speech recognisers transcribe the
audio, and the tool reports, line by line:

- where each transcript differs from the script;
- where the two transcripts disagree with each other;
- for Chinese, where the syllable or tone heard differs from the reading the script means (缪 miù → 妙 miào).

A line where **both** models differ from the script at the same place is a **likely misread**. A line where
only one does is **worth a listen**. The report is Markdown (readable in a terminal) and JSON, and the exit
code is 1 when any line needs a listen, so it can stop a pipeline. Chinese, English and Japanese.

## Install

Python 3.11 or later and [ffmpeg](https://ffmpeg.org/) (`brew install ffmpeg`). Straight from GitHub:

```sh
pip install "tts-asr-check[mlx] @ git+https://github.com/Keith-CY/tts-asr-check"   # Apple Silicon
```

Or from a checkout of this repository:

```sh
pip install ".[mlx]"                          # Apple Silicon: mlx-whisper + mlx-audio
pip install ".[faster-whisper,transformers]"  # Linux / Windows / Intel: CPU or CUDA
pip install ".[ja]"                           # optional: Japanese readings (fugashi + UniDic-lite)
```

The models download from Hugging Face on first use: about 1.6 GB for Whisper large-v3-turbo, and 1 GB
(8-bit MLX) or 1.6 GB (PyTorch) for Qwen3-ASR 0.6B.

## Usage

```sh
tts-asr-check check script.json                      # the script names each line's audio file
tts-asr-check check script.txt clips/                # a folder: files named after the line ids, or one per line in order
tts-asr-check check script.txt 01.wav 02.wav 03.wav  # one file per line
tts-asr-check check subtitles.srt narration.wav      # one recording, cut at the subtitle timings
tts-asr-check check script.txt narration.wav         # one recording, no timings: the transcript is aligned to the lines
```

Useful options:

| Option | |
|---|---|
| `--reading 缪=miù` | Chinese: the reading meant for a character or word (repeatable; also `"readings"` in a JSON script) |
| `--asr BACKEND[=MODEL]` | the two recognisers, given twice (default: `mlx-whisper` and `mlx-qwen3-asr` on Apple Silicon, `faster-whisper` and `transformers` elsewhere) |
| `--json PATH`, `--markdown PATH` | write the reports to files; `--json -` prints JSON instead of Markdown |
| `--save-transcripts DIR` | keep what each model heard, to re-run the comparison later with `compare` |
| `--fail-on listen\|misread\|never` | when to exit 1 (default: any line worth a listen) |
| `--lang zh\|en\|ja` | otherwise taken from the script |

Exit codes: 0 when no line needs a listen, 1 when some do (see `--fail-on`), 2 for bad input or a recogniser
that failed to load or run.

Other commands:

- `tts-asr-check compare SCRIPT A.json B.json`: compare saved transcripts with the script, no models. It
  takes transcripts from any recogniser: `{"lines": {"1": "…", "2": "…"}}`, or `{"text": "…"}` for one long
  transcript.
- `tts-asr-check readings SCRIPT`: Chinese only. Shows the reading each character will be checked against;
  characters with several readings in common use and nothing to decide between them are in [brackets]. Pin
  those with `--reading`.
- `tts-asr-check backends`: the recognisers and whether they are installed.

Scripts can be `.txt` (one line per line), `.srt` / `.vtt`, `.jsonl`, or `.json`:

```json
{
  "lang": "zh",
  "readings": {"缪": "miù"},
  "lines": [
    {"id": "1", "text": "宇宙射线撞上大气层，会产生大量缪子。", "audio": "1.aiff"},
    {"id": "2", "text": "缪子比电子重得多。", "audio": "all.wav", "start": 4.0, "end": 6.4}
  ]
}
```

`audio` paths are relative to the script. `start` / `end` (seconds) cut a stretch out of a longer file.

### Try it on a Mac

macOS's built-in Chinese voice makes the same mistake: `say -v Tingting` reads 缪子 as miào zǐ.

```sh
cd examples
sh make-clips.sh                  # three clips with `say` (the voice may need downloading: System Settings → Accessibility → Spoken Content)
tts-asr-check check muon-zh.json
```

## Sample report

The run above, on macOS 26.6 (real output):

```markdown
# Narration check

- Script: muon-zh.json (3 lines, zh)
- A: mlx-whisper · mlx-community/whisper-large-v3-turbo
- B: mlx-qwen3-asr · mlx-community/Qwen3-ASR-0.6B-8bit
- Result: 1 likely misread · 1 worth a listen · 1 ok

## Likely misread

Both models differ from the script at the same place.

### Line 2 · 2.aiff

- Script: 缪子比电子重得多。
- A heard: 妙子比电子重得多。
  - 缪 miù → 妙 miào: different syllable
- B heard: 庙子比电子重得多。
  - 缪 miù → 庙 miào: different syllable
- Both heard: 妙 / 庙 miào
- A and B: agree in sound

## Worth a listen

One model differs from the script, or both do in different places.

### Line 1 · 1.aiff

- Script: 宇宙射线撞上大气层，会产生大量缪子。
- A heard: 宇宙射现状上大气层,会产生大量妙子。
  - 缪 miù → 妙 miào: different syllable
- B heard: 宇宙射线撞上大气层，会产生大量缪子。
  - 缪: written as in the script, which doesn't show which reading was heard
- A and B differ:
  - A 妙 miào · B 缪 miào/miù/móu

## All lines

| Line | Result | A | B | Script |
|---|---|---|---|---|
| 1 | worth a listen | 缪→妙 | exact | 宇宙射线撞上大气层，会产生大量缪子。 |
| 2 | likely misread | 缪→妙 | 缪→庙 | 缪子比电子重得多。 |
| 3 | ok | exact | exact | 所以它能穿透很厚的岩石。 |
```

Both lines contain the same misread. In line 2 both models wrote a character read miào. In line 1 Qwen3-ASR
wrote 缪 back, which can also be read miào, so only Whisper shows the problem. Whisper's 射现状 for 射线撞 is
not reported because it sounds the same.

The JSON report has the same content. One line of it, shortened:

```json
{
  "id": "2",
  "script": "缪子比电子重得多。",
  "status": "misread",
  "audio": "2.aiff",
  "A": {
    "heard": "妙子比电子重得多。",
    "verdict": "differs",
    "diffs": [{"kind": "sound", "script": "缪", "heard": "妙", "start": 0, "end": 1,
               "script_reading": "miù", "heard_reading": "miào"}],
    "same": []
  },
  "B": {"heard": "庙子比电子重得多。", "verdict": "differs", "diffs": ["…"], "same": []},
  "A_vs_B": {"heard": "庙子比电子重得多。", "verdict": "same", "diffs": [], "same": ["…"]},
  "both_heard": ["妙 / 庙 miào"]
}
```

## How the comparison works

1. **Normalise.** Unicode NFKC (full-width letters and digits become half-width), lower case, punctuation and
   spaces dropped. Each Chinese character or kana is one token; a run of letters or digits is one token.
2. **Align.** The script's tokens and the transcript's tokens are aligned with Python's `difflib`. Every
   stretch that doesn't match is checked for being the same sound written another way:
   - **numbers**: 2026 / 二〇二六 / 两千零二十六, 42 / forty-two, 2026 / twenty twenty-six, 50% / 百分之五十;
   - **Chinese** (pypinyin): each script character gets the reading meant in context, from pypinyin's phrase
     dictionary or from `--reading`. A transcript character counts with its reading in context and its most
     common reading. If one of those is the reading meant, the sound is the same (它/他, traditional and
     simplified characters, 的/地/得). Otherwise the difference is a **tone** (same syllable, other tone), a
     **sound** (other syllable), or a **polyphone** (the script's character has several readings in common use,
     none was pinned, and the model heard one of the others);
   - **Japanese**: hiragana and katakana spellings of the same kana match; with the `ja` extra, kanji and kana
     are compared by reading (下さい / ください);
   - **English**: spacing and hyphens (e-mail / email).
3. **Classify each line.** No differences from either model: **ok**. Differences from one model, or from both
   in different places: **worth a listen**. Both models differ at the same place: **likely misread**.
4. **Compare the two transcripts** the same way, so the report shows where the models disagree.

The models never see the script: no prompts, no hotwords. A recogniser that is told what to expect tends to
hear it.

## Recognisers

| Backend | Default model | Model licence | Runs on | Library |
|---|---|---|---|---|
| `mlx-whisper` | [mlx-community/whisper-large-v3-turbo](https://huggingface.co/mlx-community/whisper-large-v3-turbo) | MIT (OpenAI's [whisper-large-v3-turbo](https://huggingface.co/openai/whisper-large-v3-turbo); the MLX conversion states no licence of its own) | Apple Silicon | mlx-whisper (MIT) |
| `mlx-qwen3-asr` | [mlx-community/Qwen3-ASR-0.6B-8bit](https://huggingface.co/mlx-community/Qwen3-ASR-0.6B-8bit) | Apache-2.0 (from [Qwen/Qwen3-ASR-0.6B](https://huggingface.co/Qwen/Qwen3-ASR-0.6B)) | Apple Silicon | mlx-audio (MIT) |
| `faster-whisper` | `large-v3-turbo` (faster-whisper's name for [dropbox-dash/faster-whisper-large-v3-turbo](https://huggingface.co/dropbox-dash/faster-whisper-large-v3-turbo), formerly mobiuslabsgmbh) | MIT | CPU, CUDA | faster-whisper (MIT) |
| `transformers` | [Qwen/Qwen3-ASR-0.6B-hf](https://huggingface.co/Qwen/Qwen3-ASR-0.6B-hf) | Apache-2.0 | CUDA, CPU, Apple MPS | transformers ≥ 5.18 (Apache-2.0), PyTorch (BSD-3-Clause) |

Each backend takes another model: `--asr mlx-qwen3-asr=mlx-community/Qwen3-ASR-1.7B-8bit`, or a local folder.
The `transformers` backend runs Whisper checkpoints too (`--asr transformers=openai/whisper-large-v3-turbo`).
Use two different families: two Whisper models tend to make the same mistakes, and a mistake both make looks
like a misread.

Your own recogniser: `--asr my_package.my_module:factory=MODEL`, where `factory(model)` returns an object with
`name`, `model` and `transcribe(audio, lang) -> str` (`audio` is 16 kHz mono float32, `lang` is `zh`, `en` or
`ja`). Or run it yourself and use `compare`.

Other dependencies: [pypinyin](https://github.com/mozillazg/python-pinyin) (MIT), NumPy (BSD-3-Clause), and
for `ja` [fugashi](https://github.com/polm/fugashi) (MIT) with [UniDic-lite](https://github.com/polm/unidic-lite)
(MIT; the UniDic dictionary is BSD-3-Clause / LGPL / GPL).

## Limits

- **It compares text, not sound.** When a recogniser writes back the script's own character, its reading
  can't be seen: in the sample above Qwen3-ASR wrote 缪 for a spoken miào. Pinned characters that both models
  wrote back are listed under "Pinned readings not confirmed".
- **Both models can be wrong the same way.** An "ok" means two recognisers agreed with the script. It doesn't
  prove the audio is right.
- **Chinese readings come from pypinyin.** Its guess for a polyphonic character can be wrong (缪 defaults to
  móu); check with `tts-asr-check readings` and pin what matters. Tone sandhi (一, 不), erhua and neutral tones
  go no further than pypinyin does.
- **Whisper is weak on Chinese tones and rare characters**; that is why the second model is Qwen3-ASR.
- **Japanese**: pitch accent is not checked (雨 and 飴 have the same reading). Without the `ja` extra, kanji
  against kana counts as a difference.
- **English**: no spelling variants (colour / color) and no contractions (it's / it is).
- **One recording without timings** is split by aligning text, so a badly misheard stretch can shift words
  into a neighbouring line. Clips per line, or subtitles with timings, are more precise.
- Other languages are not supported.

## 中文说明

我们给一段旁白配音时，TTS 把「缪」（miù，缪子）读成了「妙」（miào）。Whisper medium 把两种读音都写成「妙」，
只用它核对就漏掉了；Qwen3-ASR 能分开。从那以后每句旁白都用两个不同的语音识别模型核对，这个工具就是这一步。

给它配音音频和原稿，它用两个模型转写，逐句报告：每个模型听到的和原稿哪里不同、两个模型之间哪里不同、
中文的音节或声调和原稿想要的读音哪里不同（用 pypinyin）。两个模型在同一处都和原稿不同 =「很可能读错」；
只有一个不同 =「值得听一下」。输出 Markdown 和 JSON；有需要听的句子时退出码为 1，可以放进流水线。

多音字用 `--reading 缪=miù`（或 JSON 原稿里的 `"readings"`）写明想要的读音；`tts-asr-check readings 原稿`
会把读音定不下来的字用方括号标出。限制：只比文字，模型把原稿里的多音字原样写回时，看不出它听到的是哪个读音；
两个模型也可能一起错。

```sh
pip install ".[mlx]"
tts-asr-check check 原稿.json
```

## Licence

MIT, © 2026 Keith. The models have their own licences (see the table above).
