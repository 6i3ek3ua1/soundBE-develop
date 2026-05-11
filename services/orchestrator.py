import logging
import threading
from typing import Optional, Dict, Any
import numpy as np

from services.event_bus import EventBus, EventType, Event
from services.sound_capture import SoundCapturer
from services.asr_whisper import WhisperASR
from services.translation_service import TranslationService
from services.tts_service import TextToSpeechService


class SystemOrchestrator:
    """Главный оркестратор системы, управляет всеми компонентами"""

    def __init__(
        self,
        logger: logging.Logger,
        config: Any,  # SimpleNamespace from config.load_config()
    ):
        """
        Args:
            logger: Logger instance
            config: Configuration object
        """
        self.logger = logger
        self.config = config
        self.event_bus = EventBus(logger=logger)

        # Инициализируем компоненты
        self._initialize_components()

        # Подписываемся на события
        self._setup_event_handlers()

        self.running = False
        self.logger.info("SystemOrchestrator initialized")

    def _initialize_components(self):
        """Инициализировать все компоненты системы"""

        # ASR (Whisper)
        whisper_model = getattr(self.config, "WHISPER_MODEL", "base")
        whisper_lang = getattr(self.config, "WHISPER_LANGUAGE", "en")
        whisper_fp16 = str(getattr(self.config, "WHISPER_FP16", "0")) in (
            "1",
            "true",
            "True",
        )

        self.asr = WhisperASR(
            model_name=whisper_model,
            language=whisper_lang,
            fp16=whisper_fp16,
        )
        self.logger.info("ASR initialized")

        # Sound Capturer
        self.sound_capturer = SoundCapturer(
            logger=self.logger,
            asr=self.asr,
            event_bus=self.event_bus,
        )
        self.logger.info("SoundCapturer initialized")

        # Translation Service
        translation_enabled = str(
            getattr(self.config, "TRANSLATION_ENABLED", "1")
        ) in ("1", "true", "True")
        target_lang = getattr(self.config, "TARGET_LANGUAGE", "English")
        translation_model = getattr(
            self.config,
            "TRANSLATION_MODEL",
            "Qwen/Qwen2-4B-Instruct",
        )

        if translation_enabled:
            self.translation_service = TranslationService(
                model_name=translation_model,
                target_language=target_lang,
                logger=self.logger,
                use_gpu=True,
            )
            self.logger.info("Translation service initialized")
        else:
            self.translation_service = None
            self.logger.info("Translation service disabled")

        # TTS Service
        tts_enabled = str(getattr(self.config, "TTS_ENABLED", "1")) in (
            "1",
            "true",
            "True",
        )
        tts_lang = getattr(self.config, "TTS_LANGUAGE", "en")

        if tts_enabled:
            self.tts_service = TextToSpeechService(
                logger=self.logger,
                sample_rate=16000,
                language=tts_lang,
            )
            self.logger.info("TTS service initialized")
        else:
            self.tts_service = None
            self.logger.info("TTS service disabled")

    def _setup_event_handlers(self):
        """Подписать обработчики на события"""

        # Когда текст распознан - отправляем на перевод
        self.event_bus.subscribe(
            EventType.TEXT_RECOGNIZED, self._on_text_recognized
        )

        # Когда текст переведён - отправляем на озвучку
        self.event_bus.subscribe(
            EventType.TEXT_TRANSLATED, self._on_text_translated
        )

    def _on_text_recognized(self, event: Event):
        """Обработчик события распознавания текста"""
        text = event.data.get("text", "")
        infer_time = event.data.get("infer_time", 0)

        self.logger.info(f"Text recognized: {text[:100]}...")

        if not text.strip():
            return

        if self.translation_service is not None:
            threading.Thread(
                target=self._translate_text,
                args=(text,),
                daemon=True,
                name="TranslationThread",
            ).start()
        else:
            # Если перевода нет, сразу озвучиваем распознанный текст
            if self.tts_service is not None:
                threading.Thread(
                    target=self._synthesize_and_play,
                    args=(text, "recognized"),
                    daemon=True,
                    name="TTSThread",
                ).start()

    def _translate_text(self, text: str):
        """Перевести текст"""
        try:
            self.event_bus.publish(
                Event(
                    type=EventType.TRANSLATION_STARTED,
                    data={"text": text},
                    source="orchestrator",
                )
            )

            result = self.translation_service.translate(text)

            if result.get("error"):
                self.logger.error(f"Translation error: {result['error']}")
                translated_text = text
            else:
                translated_text = result.get("translated_text", text)

            self.event_bus.publish(
                Event(
                    type=EventType.TEXT_TRANSLATED,
                    data={
                        "original_text": text,
                        "translated_text": translated_text,
                        "infer_time": result.get("infer_time", 0),
                    },
                    source="orchestrator",
                )
            )

            self.logger.info(f"Text translated: {translated_text[:100]}...")

        except Exception as e:
            self.logger.exception(f"Translation error: {e}")
            self.event_bus.publish(
                Event(
                    type=EventType.ERROR_OCCURRED,
                    data={"error": str(e), "stage": "translation"},
                    source="orchestrator",
                )
            )

    def _on_text_translated(self, event: Event):
        """Обработчик события перевода текста"""
        translated_text = event.data.get("translated_text", "")

        if self.tts_service is not None:
            threading.Thread(
                target=self._synthesize_and_play,
                args=(translated_text, "translated"),
                daemon=True,
                name="TTSThread",
            ).start()

    def _synthesize_and_play(self, text: str, text_type: str):
        """Синтезировать и воспроизвести текст"""
        try:
            self.event_bus.publish(
                Event(
                    type=EventType.TTS_STARTED,
                    data={"text": text[:100], "type": text_type},
                    source="orchestrator",
                )
            )

            result = self.tts_service.synthesize(text)

            if result.get("error"):
                self.logger.error(f"TTS error: {result['error']}")
                return

            audio = result.get("audio")
            if audio is not None and len(audio) > 0:
                self.tts_service.play_audio(audio, result.get("sample_rate"))

                self.event_bus.publish(
                    Event(
                        type=EventType.AUDIO_PLAYING,
                        data={"type": text_type, "infer_time": result.get("infer_time")},
                        source="orchestrator",
                    )
                )

                self.logger.info(f"Audio played ({text_type})")

        except Exception as e:
            self.logger.exception(f"TTS playback error: {e}")
            self.event_bus.publish(
                Event(
                    type=EventType.ERROR_OCCURRED,
                    data={"error": str(e), "stage": "tts"},
                    source="orchestrator",
                )
            )

    def start(self, device_idx: Optional[int] = None):
        """Запустить систему"""
        self.running = True
        self.logger.info("System starting...")

        try:
            self.sound_capturer.capture(device_idx=device_idx)
        except KeyboardInterrupt:
            self.logger.info("System interrupted by user")
        except Exception as e:
            self.logger.exception(f"System error: {e}")
        finally:
            self.stop()

    def stop(self):
        """Остановить систему"""
        self.running = False
        self.sound_capturer.stop_capture()
        self.logger.info("System stopped")

    def get_status(self) -> Dict[str, Any]:
        """Получить статус системы"""
        return {
            "running": self.running,
            "asr_model": self.asr.model_name,
            "translation_enabled": self.translation_service is not None,
            "tts_enabled": self.tts_service is not None,
        }
