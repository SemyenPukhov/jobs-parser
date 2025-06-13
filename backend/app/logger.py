import logging
import sys
from logging.handlers import RotatingFileHandler
import os

# Получаем окружение из переменных среды
ENV = os.getenv("ENVIRONMENT", "dev").upper()

# Лог-файл
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / f"{ENV.lower()}_scraper.log"

# Настройка форматирования с учетом окружения
class EnvironmentFormatter(logging.Formatter):
    def format(self, record):
        # Добавляем префикс окружения к сообщению
        record.msg = f"[{ENV}] {record.msg}"
        return super().format(record)

# Настройка логгера
logger = logging.getLogger("scraper")
logger.setLevel(logging.INFO)

# Создаем форматтер
formatter = EnvironmentFormatter(
    "%(asctime)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# Хендлер для файла
file_handler = RotatingFileHandler(
    LOG_FILE,
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5
)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Хендлер для консоли
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# Отключаем передачу логов родительским логгерам
logger.propagate = False

# Переопределяем методы логирования для добавления уровня логирования
def _log_with_level(level, msg, *args, **kwargs):
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL
    }
    numeric_level = level_map.get(level, logging.INFO)
    return logger.log(numeric_level, msg, *args, **kwargs)

logger.debug = lambda msg, *args, **kwargs: _log_with_level("DEBUG", msg, *args, **kwargs)
logger.info = lambda msg, *args, **kwargs: _log_with_level("INFO", msg, *args, **kwargs)
logger.warning = lambda msg, *args, **kwargs: _log_with_level("WARNING", msg, *args, **kwargs)
logger.error = lambda msg, *args, **kwargs: _log_with_level("ERROR", msg, *args, **kwargs)
logger.critical = lambda msg, *args, **kwargs: _log_with_level("CRITICAL", msg, *args, **kwargs)
