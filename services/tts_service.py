import logging
import threading
import numpy as np
from typing import Optional, Dict, Any
import time


class TextToSpeechService:
    """Сервис синтеза речи"""

    def __init__(
        self,
        logger: logging.Logger = None,
        sample_rate: int = 16000,
        language: str = "en",
    ):
        """
        Args:
            logger: Logger instance
            sample_rate: Частота дискретизации
            language: Язык (en, ru и т.д.)
        """
        self.logger = logger or logging.getLogger(__name__)
        self.sample_rate = sample_rate
        self.language = language
        self.tts_engine = None
        self._initialized = False
        self._init_lock = threading.Lock()

        self.logger.info(f"TextToSpeechService initialized (lang: {language})")

    def _lazy_init(self):
        """Ленивая инициализация TTS"""
        if self._initialized:
            return

        with self._init_lock:
            if self._initialized:
                return

            try:
                # Пробуем использовать pyttsx3 как fallback
                import pyttsx3

                self.tts_engine = pyttsx3.init()
                self.tts_engine.setProperty("rate", 150)
                self._initialized = True
                self.logger.info("TTS engine initialized with pyttsx3")

            except ImportError:
                self.logger.warning(
                    "pyttsx3 not available. Install: pip install pyttsx3"
                )
                self._initialized = False

    def synthesize(self, text: str) -> Dict[str, Any]:
        """
        Синтезировать речь из текста

        Args:
            text: Исходный текст

        Returns:
            Dict с полями:
                - audio: numpy array с аудиоданными
                - sample_rate: Частота дискретизации
                - infer_time: Время синтеза
        """
        if not text.strip():
            return {
                "audio": np.array([], dtype=np.float32),
                "sample_rate": self.sample_rate,
                "infer_time": 0.0,
            }

        self._lazy_init()

        if not self._initialized:
            self.logger.warning("TTS engine not initialized")
            return {
                "audio": np.array([], dtype=np.float32),
                "sample_rate": self.sample_rate,
                "infer_time": 0.0,
                "error": "TTS engine not available",
            }

        try:
            t0 = time.perf_counter()

            # Используем временный файл для сохранения синтезированной речи
            import tempfile
            import soundfile as sf
            import pyttsx3

            with tempfile.NamedTemporaryFile(
                suffix=".wav", delete=False
            ) as tmp_file:
                tmp_path = tmp_file.name

            # Синтезируем
            self.tts_engine.save_to_file(text, tmp_path)
            self.tts_engine.runAndWait()

            # Загружаем аудио
            audio_data, sr = sf.read(tmp_path)

            # Конвертируем в нужную частоту дискретизации если нужно
            if sr != self.sample_rate:
                import librosa

                audio_data = librosa.resample(
                    audio_data, orig_sr=sr, target_sr=self.sample_rate
                )

            # Нормализуем
            if audio_data.dtype != np.float32:
                audio_data = audio_data.astype(np.float32) / 32768.0

            infer_time = time.perf_counter() - t0

            self.logger.debug(f"Synthesized {len(audio_data)} samples in {infer_time:.2f}s")

            # Очищаем временный файл
            import os

            try:
                os.remove(tmp_path)
            except:
                pass

            return {
                "audio": audio_data,
                "sample_rate": self.sample_rate,
                "infer_time": infer_time,
            }

        except Exception as e:
            self.logger.exception(f"TTS synthesis error: {e}")
            return {
                "audio": np.array([], dtype=np.float32),
                "sample_rate": self.sample_rate,
                "infer_time": 0.0,
                "error": str(e),
            }

    def play_audio(self, audio: np.ndarray, sample_rate: int = None) -> bool:
        """
        Воспроизвести аудио

        Args:
            audio: Аудиоданные (numpy array)
            sample_rate: Частота дискретизации

        Returns:
            True если успешно, False если ошибка
        """
        if sample_rate is None:
            sample_rate = self.sample_rate

        if audio is None or len(audio) == 0:
            self.logger.warning("Empty audio data")
            return False

        try:
            import sounddevice as sd

            self.logger.debug(f"Playing audio: {len(audio)} samples at {sample_rate}Hz")

            # Нормализуем если нужно
            if audio.max() > 1.0:
                audio = audio / 32768.0

            # Воспроизводим
            sd.play(audio, samplerate=sample_rate)
            sd.wait()

            return True

        except Exception as e:
            self.logger.exception(f"Audio playback error: {e}")
            return False
