import sys
import os
import socket
from logging_tools import logging_tools
from config import load_config
from services.orchestrator import SystemOrchestrator
from services.ui_controller import UIController
import pyfiglet
import argparse


def find_free_port(start_port=8000, max_attempts=10):
    """Найти свободный порт начиная с start_port"""
    import socket
    for port in range(start_port, start_port + max_attempts):
        try:
            # Проверяем, не занят ли порт другим процессом
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as test_sock:
                test_sock.settimeout(1)
                result = test_sock.connect_ex(('localhost', port))
                if result != 0:  # Порт свободен
                    # Дополнительная проверка - пытаемся забиндиться
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as bind_sock:
                        bind_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                        bind_sock.bind(('', port))
                        return port
        except OSError:
            continue
    raise OSError(f"Не удалось найти свободный порт в диапазоне {start_port}-{start_port + max_attempts - 1}")


def main():
    """Главная функция приложения"""
    parser = argparse.ArgumentParser(
        description="SoundBE - Система распознавания и перевода речи в реальном времени"
    )
    parser.add_argument(
        "--no-ui",
        action="store_true",
        help="Запустить без веб-интерфейса (только командная строка)",
    )
    parser.add_argument(
        "--device",
        type=int,
        help="ID устройства захвата аудио",
    )
    parser.add_argument(
        "--ui-port",
        type=int,
        help="Порт для веб-интерфейса (по умолчанию из конфига или 8000)",
    )
    parser.add_argument(
        "--auto-port",
        action="store_true",
        help="Автоматически найти свободный порт",
    )

    args = parser.parse_args()

    # Загружаем конфиг и логгер
    config = load_config()
    logger = logging_tools.get_logger(
        "",
        level=config.LOG_LEVEL,
        file=getattr(config, "LOG_FILE", "soundbe.log"),
    )

    # Определяем порт для UI
    ui_port = args.ui_port
    if ui_port is None:
        ui_port = int(getattr(config, "UI_PORT", 8000))

    if args.auto_port:
        try:
            ui_port = find_free_port(ui_port)
            logger.info(f"Найден свободный порт: {ui_port}")
        except OSError as e:
            logger.error(f"Не удалось найти свободный порт: {e}")
            return 1

    # Выводим приветствие
    print(pyfiglet.figlet_format("SoundBe"))
    logger.info("=" * 60)
    logger.info("SoundBE - Система распознавания и перевода речи")
    logger.info("=" * 60)

    if not args.no_ui:
        logger.info(f"UI port: {ui_port}")

    # Создаём оркестратор системы
    logger.info("Initializing system...")
    orchestrator = SystemOrchestrator(logger=logger, config=config)

    # Если включен UI
    if not args.no_ui:
        logger.info("Starting web UI...")
        ui_controller = UIController(logger=logger, orchestrator=orchestrator)

        try:
            ui_controller.start(port=ui_port)
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
