"""Speech recognisers.

A backend turns 16 kHz mono float32 audio into text. Name one on the command
line as ``NAME`` or ``NAME=MODEL``; a backend of your own as
``package.module:factory`` (or ``…:factory=MODEL``), where ``factory(model)``
returns an object with ``name``, ``model`` and ``transcribe(audio, lang)``.
"""

from __future__ import annotations

import importlib
import platform

from .base import LANG_NAMES, Backend, BackendError

__all__ = ["LANG_NAMES", "Backend", "BackendError", "REGISTRY", "default_pair", "make"]

# name: (module, class, default model, what it is)
REGISTRY = {
    "mlx-whisper": (
        "tts_asr_check.backends.mlx",
        "MlxWhisper",
        "mlx-community/whisper-large-v3-turbo",
        "Whisper on Apple Silicon (mlx-whisper)",
    ),
    "mlx-qwen3-asr": (
        "tts_asr_check.backends.mlx",
        "MlxQwen3ASR",
        "mlx-community/Qwen3-ASR-0.6B-8bit",
        "Qwen3-ASR on Apple Silicon (mlx-audio)",
    ),
    "faster-whisper": (
        "tts_asr_check.backends.faster_whisper",
        "FasterWhisper",
        "large-v3-turbo",
        "Whisper on CPU or CUDA (faster-whisper / CTranslate2)",
    ),
    "transformers": (
        "tts_asr_check.backends.hf",
        "Transformers",
        "Qwen/Qwen3-ASR-0.6B-hf",
        "Qwen3-ASR or Whisper on CUDA, CPU or MPS (Hugging Face transformers + PyTorch)",
    ),
}


def apple_silicon() -> bool:
    return platform.system() == "Darwin" and platform.machine() == "arm64"


def default_pair() -> list[str]:
    if apple_silicon():
        return ["mlx-whisper", "mlx-qwen3-asr"]
    return ["faster-whisper", "transformers"]


def make(spec: str) -> Backend:
    name, _, model = spec.partition("=")
    name, model = name.strip(), model.strip() or None
    if name in REGISTRY:
        module, cls, default, _ = REGISTRY[name]
        return getattr(importlib.import_module(module), cls)(model or default)
    if ":" in name:
        module, _, attr = name.partition(":")
        try:
            factory = getattr(importlib.import_module(module), attr)
        except (ImportError, AttributeError) as e:
            raise BackendError(f"cannot load backend {name!r}: {e}") from None
        backend = factory(model)
        for need in ("name", "model", "transcribe"):
            if not hasattr(backend, need):
                raise BackendError(f"backend {name!r} has no {need!r}")
        return backend
    raise BackendError(f"unknown backend {name!r}; known: {', '.join(REGISTRY)}")
