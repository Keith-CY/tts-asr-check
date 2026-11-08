"""Whisper with faster-whisper (CTranslate2): CPU or CUDA, any OS."""

from __future__ import annotations

import numpy as np

from .base import Backend, need


class FasterWhisper(Backend):
    name = "faster-whisper"

    def __init__(self, model: str):
        self.model = model
        fw = need("faster_whisper", "faster-whisper")
        self._m = fw.WhisperModel(model, device="auto", compute_type="default")

    def _transcribe(self, audio: np.ndarray, lang: str) -> str:
        segments, _ = self._m.transcribe(
            audio,
            language=lang,
            beam_size=5,
            temperature=0.0,
            condition_on_previous_text=False,
            vad_filter=False,
        )
        return "".join(s.text for s in segments)

    def close(self) -> None:
        self._m = None
