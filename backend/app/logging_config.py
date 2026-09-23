"""
Конфигурация логирования для приложения.

Использует стандартный модуль logging с уровнями:
  DEBUG    - отладочная информация (разработчик)
  INFO     - информационные сообщения о штатной работе
  WARNING  - предупреждения о нештатных ситуациях
  ERROR    - ошибки выполнения операций
  CRITICAL - критические ошибки, угрожающие работе приложения

Особенности:
  - SQLAlchemy логи выведены на уровень WARNING (SQL-запросы только при ошибках)
  - Uvicorn логи выведены на уровень WARNING (HTTP-запросы в dev, ошибки в prod)
  - Цветной вывод для консоли (ANSI-коды)
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

# Цвета для консоли (ANSI)
COLORS = {
    "DEBUG": "\033[36m",    # Cyan
    "INFO": "\033[32m",     # Green
    "WARNING": "\033[33m",  # Yellow
    "ERROR": "\033[31m",    # Red
    "CRITICAL": "\033[35m", # Magenta
    "RESET": "\033[0m",     # Reset
}


class ColorFormatter(logging.Formatter):
    """Форматтер с цветным выводом для консоли."""

    def format(self, record: logging.LogRecord) -> str:
        color = COLORS.get(record.levelname, "")
        record.levelname = f"{color}{record.levelname}{COLORS['RESET']}"
        return super().format(record)


def setup_logging(level: str = "INFO") -> None:
    """
    Настраивает логирование приложения.

    Args:
        level: Базовый уровень логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    # --- Console handler (stderr) с цветами ---
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(ColorFormatter(LOG_FORMAT, datefmt=DATE_FORMAT))

    # --- Rotating file handler (макс. 10 МБ, 5 файлов) ---
    try:
        from logging.handlers import RotatingFileHandler

        file_handler = RotatingFileHandler(
            LOG_DIR / "app.log",
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
    except ImportError:
        # Fallback для старых версий Python
        file_handler = logging.FileHandler(
            LOG_DIR / "app.log", encoding="utf-8", mode="a"
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))

    # Корневой логгер
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    # --- Отключаем SQL-запросы на уровне INFO ---
    # SQL-запросы полезны только при отладке (DEBUG)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    # --- Uvicorn: HTTP-запросы только на INFO в dev, ошибки в prod ---
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

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
