import logging
import threading
from typing import Callable, Any, Dict, List
from dataclasses import dataclass
from enum import Enum


class EventType(Enum):
    """Типы событий в системе"""
    AUDIO_CAPTURED = "audio_captured"
    TEXT_RECOGNIZED = "text_recognized"
    TEXT_TRANSLATED = "text_translated"
    TRANSLATION_STARTED = "translation_started"
    TTS_STARTED = "tts_started"
    AUDIO_PLAYING = "audio_playing"
    ERROR_OCCURRED = "error_occurred"
    SYSTEM_STATUS = "system_status"


@dataclass
class Event:
    """Событие системы"""
    type: EventType
    data: Dict[str, Any]
    source: str = "system"


class EventBus:
    """Шина событий для взаимодействия компонентов"""

    def __init__(self, logger: logging.Logger = None):
        self.logger = logger or logging.getLogger(__name__)
        self._subscribers: Dict[EventType, List[Callable]] = {}
        self._lock = threading.RLock()

    def subscribe(self, event_type: EventType, callback: Callable):
        """Подписать callback на событие"""
        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            self._subscribers[event_type].append(callback)
            self.logger.debug(f"Subscribed to {event_type.value}")

    def unsubscribe(self, event_type: EventType, callback: Callable):
        """Отписать callback от события"""
        with self._lock:
            if event_type in self._subscribers:
                self._subscribers[event_type].remove(callback)
                self.logger.debug(f"Unsubscribed from {event_type.value}")

    def publish(self, event: Event):
        """Опубликовать событие"""
        with self._lock:
            subscribers = self._subscribers.get(event.type, [])
            self.logger.debug(f"Publishing {event.type.value} from {event.source}")

        # Запускаем callback'и вне lock'а чтобы не заблокировать других издателей
        for callback in subscribers:
            try:
                threading.Thread(
                    target=callback,
                    args=(event,),
                    daemon=True,
                    name=f"EventHandler-{event.type.value}"
                ).start()
            except Exception as e:
                self.logger.exception(f"Error in event handler: {e}")
