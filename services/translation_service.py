import logging
import threading
from typing import Optional, Dict, Any
import time


class TranslationService:
    """Сервис перевода текста с использованием transformers или vLLM"""

    def __init__(
        self,
        model_name: str = "Qwen/Qwen2-4B-Instruct",
        target_language: str = "Russian",
        logger: logging.Logger = None,
        use_gpu: bool = True,
        max_tokens: int = 512,
        use_vllm: bool = False,  # Отключаем vLLM по умолчанию для совместимости
    ):
        """
        Args:
            model_name: Название модели в HuggingFace
            target_language: Целевой язык для перевода
            logger: Logger instance
            use_gpu: Использовать GPU
            max_tokens: Максимальное количество токенов для ответа
            use_vllm: Использовать vLLM (может не работать на Windows)
        """
        self.logger = logger or logging.getLogger(__name__)
        self.model_name = model_name
        self.target_language = target_language
        self.use_gpu = use_gpu
        self.max_tokens = max_tokens
        self.use_vllm = use_vllm

        self.model = None
        self.tokenizer = None
        self.llm = None
        self._initialized = False
        self._init_lock = threading.Lock()

        self.logger.info(f"TranslationService initialized (model: {model_name}, vLLM: {use_vllm})")

    @property
    def is_ready(self) -> bool:
        return self._initialized

    def ensure_ready(self):
        """Download/load the translation model if it is not ready yet."""
        self._lazy_init()

    def _lazy_init(self):
        """Ленивая инициализация модели"""
        if self._initialized:
            return

        with self._init_lock:
            if self._initialized:
                return

            try:
                if self.use_vllm:
                    # Попытка использовать vLLM
                    from vllm import LLM, SamplingParams

                    self.logger.info(f"Loading model {self.model_name} with vLLM...")
                    self.llm = LLM(
                        model=self.model_name,
                        quantization="awq" if "AWQ" in self.model_name else None,
                        gpu_memory_utilization=0.9 if self.use_gpu else 0.0,
                        device="auto" if self.use_gpu else "cpu",
                        dtype="auto",
                    )
                    self._backend = "vllm"
                elif self.model_name == "stub":
                    # Заглушка для тестирования
                    self.logger.info("Using stub translation service for testing")
                    self._backend = "stub"
                else:
                    # Использование transformers напрямую
                    from transformers import AutoConfig, AutoTokenizer, AutoModelForCausalLM, AutoModelForSeq2SeqLM
                    import torch

                    self.logger.info(f"Loading translation model {self.model_name} with transformers...")

                    device = "cuda" if self.use_gpu and torch.cuda.is_available() else "cpu"
                    self.logger.info(f"Using device: {device}")

                    config = AutoConfig.from_pretrained(self.model_name, trust_remote_code=True)
                    self.tokenizer = AutoTokenizer.from_pretrained(
                        self.model_name,
                        trust_remote_code=True,
                    )

                    model_class = AutoModelForSeq2SeqLM if getattr(config, "is_encoder_decoder", False) else AutoModelForCausalLM
                    self.model = model_class.from_pretrained(
                        self.model_name,
                        torch_dtype=torch.float16 if device == "cuda" else torch.float32,
                        device_map="auto" if device == "cuda" else None,
                        low_cpu_mem_usage=True,
                        trust_remote_code=True,
                    )

                    if device == "cpu":
                        self.model.to(device)

                    self._backend = "transformers-seq2seq" if getattr(config, "is_encoder_decoder", False) else "transformers-causal"

                self._initialized = True
                self.logger.info(f"Translation model loaded successfully (backend: {self._backend})")

            except ImportError as e:
                if "vllm" in str(e):
                    self.logger.warning("vLLM not available, falling back to transformers")
                    self.use_vllm = False
                    return self._lazy_init()  # Рекурсивный вызов с transformers
                else:
                    self.logger.error(f"Import error: {e}")
                    raise
            except Exception as e:
                self.logger.exception(f"Error loading translation model: {e}")
                raise

    def translate(
        self,
        text: str,
        source_language: str = "English",
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
            t0 = time.perf_counter()

            # Формируем промпт для перевода
            prompt = self._build_translation_prompt(
                text, source_language, target_language
            )

            if self._backend == "vllm":
                # Использование vLLM
                from vllm import SamplingParams

                sampling_params = SamplingParams(
                    temperature=0.3,
                    top_p=0.95,
                    max_tokens=self.max_tokens,
                )

                outputs = self.llm.generate([prompt], sampling_params)
                infer_time = time.perf_counter() - t0

                translated_text = outputs[0].outputs[0].text.strip()
                tokens_used = len(outputs[0].outputs[0].token_ids) if hasattr(outputs[0].outputs[0], 'token_ids') else 0

            elif self._backend == "stub":
                # Заглушка - просто возвращаем текст с префиксом [STUB]
                infer_time = time.perf_counter() - t0
                translated_text = f"[STUB] {text}"
                tokens_used = len(text.split())

            elif self._backend.startswith("transformers"):
                # Использование transformers напрямую
                if self._backend == "transformers-seq2seq":
                    # Seq2seq модель - переводим напрямую
                    translated_text, tokens_used, infer_time = self._translate_with_seq2seq(prompt, t0)
                else:
                    # Causal LM модель - используем промпт
                    translated_text, tokens_used, infer_time = self._translate_with_causal_lm(prompt, t0)

            self.logger.debug(
                f"Translation completed in {infer_time:.2f}s (backend: {self._backend}): {text[:50]}... -> {translated_text[:50]}..."
            )

            return {
                "translated_text": translated_text,
                "infer_time": infer_time,
                "tokens_used": tokens_used,
                "source_language": source_language,
                "target_language": target_language,
                "backend": self._backend,
            }

        except Exception as e:
            self.logger.exception(f"Translation error: {e}")
            return {
                "translated_text": text,
                "infer_time": 0.0,
                "tokens_used": 0,
                "error": str(e),
                "source_language": source_language,
                "target_language": target_language,
                "backend": self._backend if hasattr(self, '_backend') else "unknown",
            }

    def _translate_with_seq2seq(self, text: str, t0: float) -> tuple[str, int, float]:
        """Перевод с использованием seq2seq модели"""
        import torch

        inputs = self.tokenizer(text, return_tensors="pt", padding=True, truncation=True, max_length=512)
        if self.use_gpu and torch.cuda.is_available():
            inputs = {k: v.cuda() for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=self.max_tokens,
                num_beams=4,
                early_stopping=True,
            )

        infer_time = time.perf_counter() - t0
        translated_text = self.tokenizer.decode(outputs[0], skip_special_tokens=True).strip()
        tokens_used = len(outputs[0])

        return translated_text, tokens_used, infer_time

    def _translate_with_causal_lm(self, prompt: str, t0: float) -> tuple[str, int, float]:
        """Перевод с использованием causal language model"""
        import torch

        if hasattr(self.tokenizer, "apply_chat_template") and self.tokenizer.chat_template:
            messages = [
                {
                    "role": "system",
                    "content": "You are a precise translation engine. Return only the translated text.",
                },
                {"role": "user", "content": prompt},
            ]
            model_input = self.tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
            )
        else:
            model_input = prompt

        inputs = self.tokenizer(model_input, return_tensors="pt")
        if self.use_gpu and torch.cuda.is_available():
            inputs = {k: v.cuda() for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=self.max_tokens,
                temperature=0.3,
                top_p=0.95,
                do_sample=True,
                pad_token_id=self.tokenizer.eos_token_id,
            )

        infer_time = time.perf_counter() - t0
        generated_tokens = outputs[0][inputs["input_ids"].shape[-1]:]
        translated_text = self.tokenizer.decode(generated_tokens, skip_special_tokens=True).strip()
        tokens_used = len(outputs[0])

        return translated_text, tokens_used, infer_time

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
