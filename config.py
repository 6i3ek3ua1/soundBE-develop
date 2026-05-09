import os
import logging
from types import SimpleNamespace

def load_config(init_file=".init") -> SimpleNamespace:
    config_vars = {}

    if os.path.exists(init_file):
        with open(init_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                if "=" in line:
                    key, value = line.split("=", 1)
                    config_vars[key.strip()] = value.strip()

    for key, value in os.environ.items():
        if key not in config_vars:
            config_vars[key] = value

    try:
        log_level_str = config_vars.get("LOG_LEVEL", "INFO").upper()
        config_vars["LOG_LEVEL"] = getattr(logging, log_level_str, logging.INFO)
    except Exception:
        pass

    return SimpleNamespace(**config_vars)