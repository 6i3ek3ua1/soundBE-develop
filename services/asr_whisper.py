import time
import numpy as np
import whisper


class WhisperASR:
    def __init__(self, model_name: str = "base", language: str | None = None, fp16: bool = False):
        if whisper is None:
            raise ImportError("Whisper не установлен. Установи: pip install -U openai-whisper")

        self.model_name = model_name
        self.language = language
        self.fp16 = fp16
        self.model = whisper.load_model(model_name)

    def transcribe(self, audio_16k: np.ndarray) -> tuple[str, float]:
        """
        audio_16k: float32 ndarray shape (N,), sample_rate=16000, диапазон [-1; 1]
        return: (text, infer_seconds)
        """
        t0 = time.perf_counter()

        result = self.model.transcribe(
            audio_16k,
            language=self.language,
            fp16=self.fp16,
            task="transcribe",
            verbose=False
        )

        infer_s = time.perf_counter() - t0
        text = (result.get("text") or "").strip()
        return text, infer_s

