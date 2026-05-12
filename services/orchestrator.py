import logging
import threading
import time
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
        self.models_ready = False
        self.models_loading = False
        self.models_error = None
        self.models_status = "not_started"
        self._model_preload_lock = threading.Lock()

        # Инициализируем компоненты
        self._initialize_components()

        # Подписываемся на события
        self._setup_event_handlers()

        self.running = False
        self._update_models_state()
        self.logger.info("SystemOrchestrator initialized")

        preload_models = str(getattr(self.config, "PRELOAD_MODELS", "1")).lower() in (
            "1",
            "true",
            "yes",
        )
        if preload_models:
            self.prepare_models_async()

    def _publish_status(self):
        self.event_bus.publish(
            Event(
                type=EventType.SYSTEM_STATUS,
                data=self.get_status(),
                source="orchestrator",
            )
        )

    def _update_models_state(self):
        translation_ready = (
            self.translation_service is None
            or getattr(self.translation_service, "is_ready", False)
        )
        self.models_ready = translation_ready and not self.models_error
        if self.models_error:
            self.models_status = "error"
        elif self.models_loading:
            self.models_status = "loading"
        elif self.models_ready:
            self.models_status = "ready"
        else:
            self.models_status = "not_started"

    def prepare_models_async(self):
        with self._model_preload_lock:
            if self.models_ready or self.models_loading:
                return

            self.models_loading = True
            self.models_error = None
            self.models_status = "loading"

            threading.Thread(
                target=self._prepare_models,
                daemon=True,
                name="ModelPreloadThread",
            ).start()

        self._publish_status()

    def _prepare_models(self):
        self.logger.info("Preparing models...")

        try:
            if self.translation_service is not None:
                self.logger.info(
                    "Preparing translation model: %s",
                    self.translation_service.model_name,
                )
                self.translation_service.ensure_ready()

            self.models_error = None
            self.models_loading = False
            self._update_models_state()
            self.logger.info("Models are ready")
        except Exception as e:
            self.models_loading = False
            self.models_error = str(e)
            self._update_models_state()
            self.logger.exception("Model preparation failed: %s", e)
            self.event_bus.publish(
                Event(
                    type=EventType.ERROR_OCCURRED,
                    data={"error": str(e), "stage": "model_preload"},
                    source="orchestrator",
                )
            )
        finally:
            self._publish_status()

    def configure_runtime(
        self,
        translation_enabled: Optional[bool] = None,
        tts_enabled: Optional[bool] = None,
        recognition_language: Optional[str] = None,
        target_language: Optional[str] = None,
    ):
        """Apply UI runtime settings before starting capture."""
        if recognition_language is not None:
            self.config.WHISPER_LANGUAGE = recognition_language
            self.asr.language = self._normalize_recognition_language(recognition_language)

        if target_language:
            self.config.TARGET_LANGUAGE = target_language
            if self.translation_service is not None:
                self.translation_service.target_language = target_language

        if translation_enabled is not None:
            if translation_enabled and self.translation_service is None:
                translation_model = getattr(
                    self.config,
                    "TRANSLATION_MODEL",
                    "Qwen/Qwen2.5-1.5B-Instruct",
                )
                use_vllm = str(getattr(self.config, "USE_VLLM", "false")).lower() == "true"
                self.translation_service = TranslationService(
                    model_name=translation_model,
                    target_language=getattr(self.config, "TARGET_LANGUAGE", "English"),
                    logger=self.logger,
                    use_gpu=True,
                    use_vllm=use_vllm,
                )
                self.models_error = None
                self._update_models_state()
                self.logger.info("Translation service enabled from UI")
            elif not translation_enabled and self.translation_service is not None:
                self.translation_service = None
                self.models_loading = False
                self.models_error = None
                self._update_models_state()
                self.logger.info("Translation service disabled from UI")

        if self.translation_service is not None and not self.translation_service.is_ready:
            self.models_error = None
            self._update_models_state()
            preload_models = str(getattr(self.config, "PRELOAD_MODELS", "1")).lower() in (
                "1",
                "true",
                "yes",
            )
            if preload_models:
                self.prepare_models_async()

        if tts_enabled is not None:
            if tts_enabled and self.tts_service is None:
                self.tts_service = TextToSpeechService(
                    logger=self.logger,
                    sample_rate=16000,
                    language=getattr(self.config, "TTS_LANGUAGE", "en"),
                )
                self.logger.info("TTS service enabled from UI")
            elif not tts_enabled and self.tts_service is not None:
                self.tts_service = None
                self.logger.info("TTS service disabled from UI")

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
            language=self._normalize_recognition_language(whisper_lang),
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
            "Qwen/Qwen2.5-1.5B-Instruct",
        )

        if translation_enabled:
            use_vllm = str(getattr(self.config, "USE_VLLM", "false")).lower() == "true"
            self.translation_service = TranslationService(
                model_name=translation_model,
                target_language=target_lang,
                logger=self.logger,
                use_gpu=True,
                use_vllm=use_vllm,
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

    @staticmethod
    def _normalize_recognition_language(language: Optional[str]) -> Optional[str]:
        if language is None:
            return None

        language = str(language).strip()
        if not language or language.lower() in ("auto", "none", "null"):
            return None

        return language

    @staticmethod
    def _language_name(language: Optional[str]) -> str:
        language_names = {
            "en": "English",
            "ru": "Russian",
            "es": "Spanish",
            "fr": "French",
            "de": "German",
            "zh": "Chinese",
            "ja": "Japanese",
            "ko": "Korean",
            "pt": "Portuguese",
            "it": "Italian",
        }

        if not language:
            return "the detected language"

        return language_names.get(str(language).lower(), str(language))

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

            source_language = self._language_name(
                self.asr.language or getattr(self.asr, "last_detected_language", None)
            )
            target_language = getattr(self.translation_service, "target_language", None)
            result = self.translation_service.translate(
                text,
                source_language=source_language,
                target_language=target_language,
            )

            if result.get("error"):
                self.logger.error(f"Translation error: {result['error']}")
                translated_text = f"[Translation error] {text}"
                self.event_bus.publish(
                    Event(
                        type=EventType.ERROR_OCCURRED,
                        data={"error": result["error"], "stage": "translation"},
                        source="orchestrator",
                    )
                )
            else:
                translated_text = result.get("translated_text", text)

            self.event_bus.publish(
                Event(
                    type=EventType.TEXT_TRANSLATED,
                    data={
                        "original_text": text,
                        "translated_text": translated_text,
                        "infer_time": result.get("infer_time", 0),
                        "source_language": result.get("source_language", source_language),
                        "target_language": result.get("target_language", target_language),
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
        while self.models_loading:
            self.logger.info("Waiting for models to become ready...")
            time.sleep(0.5)

        if not self.models_ready:
            self._prepare_models()

        if not self.models_ready:
            self.logger.error("Cannot start system: models are not ready")
            return

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
            "recognition_language": self.asr.language or "",
            "recognition_language_name": self._language_name(self.asr.language),
            "translation_enabled": self.translation_service is not None,
            "translation_model": getattr(self.translation_service, "model_name", None),
            "target_language": getattr(
                self.translation_service,
                "target_language",
                getattr(self.config, "TARGET_LANGUAGE", "English"),
            ),
            "tts_enabled": self.tts_service is not None,
            "models_ready": self.models_ready,
            "models_loading": self.models_loading,
            "models_status": self.models_status,
            "models_error": self.models_error,
        }
