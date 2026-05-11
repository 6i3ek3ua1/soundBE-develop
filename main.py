import sys
import os
from logging_tools import logging_tools
from config import load_config
from services.orchestrator import SystemOrchestrator
from services.ui_controller import UIController
import pyfiglet
import argparse


def main():
    """Главная функция приложения"""
    parser = argparse.ArgumentParser(
        description="SoundBE - Система распознавания и перевода речи в реальном времени"
    )
    parser.add_argument(
        "--no-ui",
        action="store_true",
        help="Запустить без веб-интерфейса (только команд­ная строка)",
    )
    parser.add_argument(
        "--device",
        type=int,
        help="ID устройства захвата аудио",
    )
    parser.add_argument(
        "--ui-port",
        type=int,
        default=8000,
        help="Порт для веб-интерфейса (по умолчанию 8000)",
    )

    args = parser.parse_args()

    # Загружаем конфиг и логгер
    config = load_config()
    logger = logging_tools.get_logger(
        "",
        level=config.LOG_LEVEL,
        file=getattr(config, "LOG_FILE", "soundbe.log"),
    )

    # Выводим приветствие
    print(pyfiglet.figlet_format("SoundBe"))
    logger.info("=" * 60)
    logger.info("SoundBE - Система распознавания и перевода речи")
    logger.info("=" * 60)

    # Создаём оркестратор системы
    logger.info("Initializing system...")
    orchestrator = SystemOrchestrator(logger=logger, config=config)

    # Если включен UI
    if not args.no_ui:
        logger.info("Starting web UI...")
        ui_controller = UIController(logger=logger, orchestrator=orchestrator)

        try:
            ui_controller.start(debug=False, port=args.ui_port)
        except KeyboardInterrupt:
            logger.info("UI interrupted by user")
        except Exception as e:
            logger.exception(f"UI error: {e}")
    else:
        # Запуск без UI - прямой захват
        logger.info("Running in headless mode...")
        try:
            orchestrator.start(device_idx=args.device)
        except KeyboardInterrupt:
            logger.info("System interrupted by user")
        except Exception as e:
            logger.exception(f"System error: {e}")


if __name__ == "__main__":
    main()
