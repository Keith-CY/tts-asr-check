"""Apple Silicon backends: Whisper with mlx-whisper, Qwen3-ASR with mlx-audio."""

from __future__ import annotations

import numpy as np

from .base import LANG_NAMES, Backend, need


class MlxWhisper(Backend):
    name = "mlx-whisper"

    def __init__(self, model: str):
        self.model = model
        self._mw = need("mlx_whisper", "mlx")

    def _transcribe(self, audio: np.ndarray, lang: str) -> str:
        # Greedy decoding, no fallback to sampling and no conditioning on the
        # previous window: the same audio gives the same text every run.
        r = self._mw.transcribe(
            audio,
            path_or_hf_repo=self.model,
            language=lang,
            temperature=0.0,
            condition_on_previous_text=False,
            verbose=None,
        )
        return str(r["text"])


class MlxQwen3ASR(Backend):
    name = "mlx-qwen3-asr"

    def __init__(self, model: str):
        self.model = model
        utils = need("mlx_audio.stt.utils", "mlx")
        self._m = utils.load_model(model)

    def _transcribe(self, audio: np.ndarray, lang: str) -> str:
        out = self._m.generate(np.asarray(audio, dtype=np.float32), language=LANG_NAMES[lang], temperature=0.0)
        text = str(out.text)
        return text.split("<asr_text>", 1)[1] if "<asr_text>" in text else text

    def close(self) -> None:
        self._m = None
