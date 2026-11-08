"""Hugging Face transformers + PyTorch: Qwen3-ASR (``-hf`` checkpoints) or
Whisper, on CUDA, Apple's MPS or CPU."""

from __future__ import annotations

import numpy as np

from .base import LANG_NAMES, Backend, BackendError, need


class Transformers(Backend):
    name = "transformers"
    max_seconds = 30.0

    def __init__(self, model: str):
        self.model = model
        torch = need("torch", "transformers")
        tf = need("transformers", "transformers")
        if torch.cuda.is_available():
            self._device, self._dtype = "cuda", torch.float16
        elif torch.backends.mps.is_available():
            self._device, self._dtype = "mps", torch.float32
        else:
            self._device, self._dtype = "cpu", torch.float32
        self._torch = torch
        self.family = tf.AutoConfig.from_pretrained(model).model_type
        self._proc = tf.AutoProcessor.from_pretrained(model)
        if self.family == "whisper":
            cls = tf.WhisperForConditionalGeneration
        elif self.family == "qwen3_asr":
            cls = getattr(tf, "Qwen3ASRForConditionalGeneration", None)
            if cls is None:
                raise BackendError("this transformers has no Qwen3-ASR; it needs transformers 5.18 or later")
        else:
            raise BackendError(f"{model} is a {self.family!r} model; this backend runs Whisper and Qwen3-ASR")
        self._m = cls.from_pretrained(model, dtype=self._dtype).to(self._device).eval()

    def _transcribe(self, audio: np.ndarray, lang: str) -> str:
        torch = self._torch
        audio = np.asarray(audio, dtype=np.float32)
        with torch.inference_mode():
            if self.family == "whisper":
                feats = self._proc(audio, sampling_rate=16000, return_tensors="pt").input_features
                ids = self._m.generate(
                    feats.to(self._device, self._dtype), language=lang, task="transcribe", num_beams=1, do_sample=False
                )
                return self._proc.batch_decode(ids, skip_special_tokens=True)[0]
            inputs = self._proc.apply_transcription_request(audio=audio, language=LANG_NAMES[lang])
            inputs = {
                k: (v.to(self._device, self._dtype) if v.is_floating_point() else v.to(self._device))
                for k, v in inputs.items()
            }
            out = self._m.generate(**inputs, max_new_tokens=1024, do_sample=False)
            new = out[0, inputs["input_ids"].shape[1] :]
            return self._proc.decode(new, return_format="transcription_only")

    def close(self) -> None:
        self._m = None
