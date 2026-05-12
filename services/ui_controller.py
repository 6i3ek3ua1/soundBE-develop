import logging
import os
import threading
from typing import List, Optional, Dict, Any

from services.event_bus import EventBus, Event, EventType
import sounddevice as sd


class UIController:
    """Контроллер UI, работает с Eel для веб-интерфейса"""

    def __init__(self, logger: logging.Logger, orchestrator=None):
        """
        Args:
            logger: Logger instance
            orchestrator: SystemOrchestrator instance
        """
        self.logger = logger
        self.orchestrator = orchestrator
        self.is_running = False

        # Поддерживаем eel импорт
        try:
            import eel

            self.eel = eel
        except ImportError:
            self.logger.warning(
                "Eel not installed. Install: pip install eel"
            )
            self.eel = None

        self.logger.info("UIController initialized")

    def _setup_eel(self):
        """Настроить Eel"""
        if self.eel is None:
            return

        try:
            # Инициализируем Eel с папкой UI
            ui_dir = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), "ui"
            )
            self.eel.init(ui_dir)

            # Регистрируем Python функции доступные из JavaScript
            self.eel.expose(self.start_capture)
            self.eel.expose(self.stop_capture)
            self.eel.expose(self.get_system_status)
            self.eel.expose(self.get_audio_devices)
            self.eel.expose(self.update_runtime_settings)

            self.logger.info("Eel setup completed")

        except Exception as e:
            self.logger.exception(f"Error setting up Eel: {e}")

    def _subscribe_to_events(self):
        """Подписать обработчики на события от оркестратора"""
        if self.orchestrator is None:
            return

        event_bus = self.orchestrator.event_bus

        event_bus.subscribe(
            EventType.TEXT_RECOGNIZED, self._on_text_recognized
        )
        event_bus.subscribe(
            EventType.TEXT_TRANSLATED, self._on_text_translated
        )
        event_bus.subscribe(
            EventType.SYSTEM_STATUS, self._on_system_status
        )
        event_bus.subscribe(EventType.ERROR_OCCURRED, self._on_error)

        self.logger.info("Event subscriptions setup completed")

    def _on_text_recognized(self, event: Event):
        """Обработчик события распознавания текста"""
        try:
            if self.eel is not None:
                self.eel.onTextRecognized(event.data)
        except Exception as e:
            self.logger.exception(f"Error in text_recognized callback: {e}")

    def _on_text_translated(self, event: Event):
        """Обработчик события перевода текста"""
        try:
            if self.eel is not None:
                self.eel.onTextTranslated(event.data)
        except Exception as e:
            self.logger.exception(f"Error in text_translated callback: {e}")

    def _on_system_status(self, event: Event):
        """Обработчик события статуса системы"""
        try:
            if self.eel is not None:
                self.eel.onSystemStatus(event.data)
        except Exception as e:
            self.logger.exception(f"Error in system_status callback: {e}")

    def _on_error(self, event: Event):
        """Обработчик события ошибки"""
        try:
            if self.eel is not None:
                self.eel.onError(event.data)
        except Exception as e:
            self.logger.exception(f"Error in error callback: {e}")

    # Python функции, вызываемые из JavaScript

    def start_capture(
        self,
        device_idx: Optional[int] = None,
        translation_enabled: Optional[bool] = None,
        tts_enabled: Optional[bool] = None,
        recognition_language: Optional[str] = None,
        target_language: Optional[str] = None,
    ):
        """Запустить захват аудио"""
        logging.info(f"start_capture() called with device_idx: {device_idx}")
        if self.orchestrator is None:
            logging.error("Orchestrator not available")
            return False

        try:
            if self.orchestrator.running:
                logging.info("Capture is already running")
                return True

            if device_idx is None:
                logging.error("No audio device selected")
                return False

            self.orchestrator.configure_runtime(
                translation_enabled=translation_enabled,
                tts_enabled=tts_enabled,
                recognition_language=recognition_language,
                target_language=target_language,
            )
            if not self.orchestrator.models_ready:
                self.orchestrator.prepare_models_async()
                logging.info("Models are not ready yet")
                return False

            threading.Thread(
                target=self.orchestrator.start,
                args=(device_idx,),
                daemon=False,
                name="OrchestratorThread",
            ).start()
            logging.info("Capture started successfully")
            return True
        except Exception as e:
            logging.exception(f"Error starting capture: {e}")
            return False

    def stop_capture(self):
        """Остановить захват аудио"""
        logging.info("stop_capture() called")
        if self.orchestrator is None:
            logging.error("Orchestrator not available")
            return False

        try:
            self.orchestrator.stop()
            logging.info("Capture stopped successfully")
            return True
        except Exception as e:
            logging.exception(f"Error stopping capture: {e}")
            return False

    def update_runtime_settings(
        self,
        translation_enabled: Optional[bool] = None,
        tts_enabled: Optional[bool] = None,
        recognition_language: Optional[str] = None,
        target_language: Optional[str] = None,
    ):
        """Update runtime options from the UI."""
        if self.orchestrator is None:
            logging.error("Orchestrator not available")
            return False

        try:
            self.orchestrator.configure_runtime(
                translation_enabled=translation_enabled,
                tts_enabled=tts_enabled,
                recognition_language=recognition_language,
                target_language=target_language,
            )
            return True
        except Exception as e:
            logging.exception(f"Error updating runtime settings: {e}")
            return False

    def get_system_status(self) -> Dict[str, Any]:
        """Получить статус системы"""
        if self.orchestrator is None:
            return {
                "running": False,
                "asr_model": "unknown",
                "recognition_language": "",
                "recognition_language_name": "the detected language",
                "translation_enabled": False,
                "target_language": "English",
                "tts_enabled": False,
                "models_ready": False,
                "models_loading": False,
                "models_status": "error",
                "models_error": "Orchestrator not available",
            }

        try:
            return self.orchestrator.get_status()
        except Exception as e:
            self.logger.exception(f"Error getting status: {e}")
            return {
                "running": False,
                "error": str(e),
            }

    @staticmethod
    def get_audio_devices() -> List[Dict[str, Any]]:
        """Получить список аудиоустройств"""
        logging.info("get_audio_devices() called")
        try:
            devices = sd.query_devices()
            logging.info(f"Found {len(devices)} audio devices")
            input_devices = []

            for idx, dev in enumerate(devices):
                if dev["max_input_channels"] > 0:
                    input_device = {
                        "id": idx,
                        "name": dev["name"],
                        "channels": dev["max_input_channels"],
                        "label": f"{idx}: {dev['name']} ({dev['max_input_channels']}ch)",
                    }
                    input_devices.append(input_device)
                    logging.debug(f"Device {idx}: {input_device['label']}")

            logging.info(f"Returning {len(input_devices)} input devices")
            return input_devices

        except Exception as e:
            logging.error(f"Error querying devices: {e}")
            return []

    def start(self, port: int = 8000):
        """Запустить Eel веб-интерфейс"""
        if self.eel is None:
            self.logger.error("Eel not available")
            return

        try:
            self._setup_eel()
            self._subscribe_to_events()

            host = os.getenv("EEL_HOST", "localhost")
            mode = os.getenv("EEL_MODE", "chrome-app")
            if mode.lower() in ("", "none", "false", "off"):
                mode = None

            self.logger.info(f"Starting Eel UI on {host}:{port}...")
            self.eel.start(
                "index.html",
                mode=mode,
                host=host,
                port=port,
            )

        except Exception as e:
            self.logger.exception(f"Error starting UI: {e}")
