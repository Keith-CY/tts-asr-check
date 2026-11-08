from __future__ import annotations

from pathlib import Path

import numpy as np

from ..audio import split_quiet

LANG_NAMES = {"zh": "Chinese", "en": "English", "ja": "Japanese"}


class BackendError(RuntimeError):
    pass


def need(module: str, extra: str):
    """Import an optional dependency, or explain how to install it."""
    import importlib

    try:
        return importlib.import_module(module)
    except ImportError:
        raise BackendError(f"{module} is not installed: pip install 'tts-asr-check[{extra}]'") from None


class Backend:
    name = "backend"
    model = ""
    # Longest audio the model takes in one go; longer audio is cut at quiet
    # moments and the pieces' text joined. None: the backend handles it.
    max_seconds: float | None = None

    def transcribe(self, audio: np.ndarray, lang: str) -> str:
        if self.max_seconds and len(audio) > self.max_seconds * 16000:
            sep = " " if lang == "en" else ""
            return sep.join(self._transcribe(p, lang).strip() for p in split_quiet(audio, self.max_seconds)).strip()
        return self._transcribe(audio, lang).strip()

    def _transcribe(self, audio: np.ndarray, lang: str) -> str:
        raise NotImplementedError

    def close(self) -> None:
        pass


def label(backend) -> str:
    """``mlx-whisper · mlx-community/whisper-large-v3-turbo``; a local model
    folder is shown by its name only."""
    model = str(getattr(backend, "model", ""))
    if model and Path(model).expanduser().exists():
        model = Path(model).name
    return f"{backend.name} · {model}" if model else backend.name
