import logging
import threading
from typing import Optional, Dict, Any
import time


class TranslationService:
    """Сервис перевода текста с использованием vLLM + Qwen3-4B-AWQ"""

    def __init__(
        self,
        model_name: str = "Qwen/Qwen2-4B-Instruct",
        target_language: str = "English",
        logger: logging.Logger = None,
        use_gpu: bool = True,
        max_tokens: int = 512,
    ):
        """
        Args:
            model_name: Название модели в HuggingFace
            target_language: Целевой язык для перевода
            logger: Logger instance
            use_gpu: Использовать GPU
            max_tokens: Максимальное количество токенов для ответа
        """
        self.logger = logger or logging.getLogger(__name__)
        self.model_name = model_name
        self.target_language = target_language
        self.use_gpu = use_gpu
        self.max_tokens = max_tokens

        self.model = None
        self.llm = None
        self._initialized = False
        self._init_lock = threading.Lock()

        self.logger.info(f"TranslationService initialized (model: {model_name})")

    def _lazy_init(self):
        """Ленивая инициализация модели"""
        if self._initialized:
            return

        with self._init_lock:
            if self._initialized:
                return

            try:
                from vllm import LLM, SamplingParams

                self.logger.info(f"Loading model {self.model_name}...")
                self.llm = LLM(
                    model=self.model_name,
                    quantization="awq" if "AWQ" in self.model_name else None,
                    gpu_memory_utilization=0.9 if self.use_gpu else 0.0,
                    device="auto" if self.use_gpu else "cpu",
                    dtype="auto",
                )
                self._initialized = True
                self.logger.info("Translation model loaded successfully")
            except ImportError:
                self.logger.error(
                    "vLLM not installed. Install: pip install vllm"
                )
                raise
            except Exception as e:
                self.logger.exception(f"Error loading translation model: {e}")
                raise

    def translate(
        self,
        text: str,
        source_language: str = "Russian",
        target_language: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Перевести текст на целевой язык

        Args:
            text: Исходный текст
            source_language: Исходный язык
            target_language: Целевой язык (если None, используется self.target_language)

        Returns:
            Dict с полями:
                - translated_text: Переведённый текст
                - infer_time: Время выполнения
                - tokens_used: Количество использованных токенов
        """
        if target_language is None:
            target_language = self.target_language

        if not text.strip():
            return {
                "translated_text": "",
                "infer_time": 0.0,
                "tokens_used": 0,
            }

        self._lazy_init()

        try:
            from vllm import SamplingParams

            t0 = time.perf_counter()

            # Формируем промпт для перевода
            prompt = self._build_translation_prompt(
                text, source_language, target_language
            )

            # Параметры выборки
            sampling_params = SamplingParams(
                temperature=0.3,
                top_p=0.95,
                max_tokens=self.max_tokens,
            )

            # Запускаем инференс
            outputs = self.llm.generate([prompt], sampling_params)

            infer_time = time.perf_counter() - t0

            # Извлекаем результат
            translated_text = outputs[0].outputs[0].text.strip()
            tokens_used = outputs[0].metrics.finish_reason if hasattr(outputs[0], 'metrics') else 0

            self.logger.debug(
                f"Translation completed in {infer_time:.2f}s: {text[:50]}... -> {translated_text[:50]}..."
            )

            return {
                "translated_text": translated_text,
                "infer_time": infer_time,
                "tokens_used": tokens_used,
                "source_language": source_language,
                "target_language": target_language,
            }

        except Exception as e:
            self.logger.exception(f"Translation error: {e}")
            return {
                "translated_text": text,
                "infer_time": 0.0,
                "tokens_used": 0,
                "error": str(e),
            }

    @staticmethod
    def _build_translation_prompt(
        text: str, source_language: str, target_language: str
    ) -> str:
        """Построить промпт для перевода"""
        return (
            f"Translate the following {source_language} text to {target_language}. "
            f"Only provide the translation, nothing else.\n\n"
            f"Text: {text}\n\n"
            f"Translation:"
        )

    def detect_language(self, text: str) -> str:
        """Определить язык текста"""
        try:
            from langdetect import detect

            return detect(text)
        except ImportError:
            self.logger.warning("langdetect not installed")
            return "unknown"
        except Exception as e:
            self.logger.debug(f"Language detection error: {e}")
            return "unknown"
