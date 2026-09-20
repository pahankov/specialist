"""
Конфигурация логирования для приложения.

Использует стандартный модуль logging с уровнями:
  DEBUG    - отладочная информация (разработчик)
  INFO     - информационные сообщения о штатной работе
  WARNING  - предупреждения о нештатных ситуациях
  ERROR    - ошибки выполнения операций
  CRITICAL - критические ошибки, угрожающие работе приложения
"""

import logging
import sys
from pathlib import Path

# Директория для файлов логов
LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

# Форматирование логов
LOG_FORMAT = "[%(asctime)s] %(levelname)s %(name)s: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(level: str = "INFO") -> None:
    """
    Настраивает корневой логгер приложения.

    Args:
        level: Базовый уровень логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    # Базовый уровень
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Форматтер
    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    # Корневой логгер
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Очистка предыдущих handler'ов
    root_logger.handlers.clear()

    # --- Console handler (stderr) ---
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # --- Rotating file handler (макс. 10 МБ, 5 файлов) ---
    # Пишем всё в файл, включая DEBUG
    try:
        from logging.handlers import RotatingFileHandler

        rotating_handler = RotatingFileHandler(
            LOG_DIR / "app.log",
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding="utf-8",
        )
        rotating_handler.setLevel(logging.DEBUG)
        rotating_handler.setFormatter(formatter)
        root_logger.addHandler(rotating_handler)
    except ImportError:
        # Fallback для старых версий Python
        file_handler = logging.FileHandler(
            LOG_DIR / "app.log", encoding="utf-8", mode="a"
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    # Логируем факт запуска
    root_logger.info("Логирование инициализировано (уровень: %s)", level.upper())


def get_logger(name: str) -> logging.Logger:
    """
    Возвращает именованный логгер.

    Args:
        name: Имя логгера (обычно __name__ модуля)

    Returns:
        Настроенный экземпляр logging.Logger
    """
    return logging.getLogger(name)
