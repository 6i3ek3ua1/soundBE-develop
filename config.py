import os
import logging
from types import SimpleNamespace

def load_config(init_file=".init") -> SimpleNamespace:
    config_vars = {}

    # Значения по умолчанию
    defaults = {
        "LOG_LEVEL": "INFO",
        "UI_PORT": "8000",
        "AUDIO_DEVICE": "",
        "WHISPER_LANGUAGE": "en",
        "TRANSLATION_MODEL": "Qwen/Qwen2.5-1.5B-Instruct",
        "TARGET_LANGUAGE": "English",
        "PRELOAD_MODELS": "1",
        "TTS_ENABLED": "0",
        "TTS_LANGUAGE": "en",
        "USE_VLLM": "false",
    }

    if os.path.exists(init_file):
        with open(init_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                if "=" in line:
                    key, value = line.split("=", 1)
                    config_vars[key.strip()] = value.strip()

    # Применяем значения по умолчанию, если не заданы
    for key, default_value in defaults.items():
        if key not in config_vars:
            config_vars[key] = default_value

    # Environment variables should win over values from .init. This lets Docker
    # Compose override runtime settings without rebuilding the image.
    for key, value in os.environ.items():
        config_vars[key] = value

    try:
        log_level_str = config_vars.get("LOG_LEVEL", "INFO").upper()
        config_vars["LOG_LEVEL"] = getattr(logging, log_level_str, logging.INFO)
    except Exception:
        pass

    return SimpleNamespace(**config_vars)
