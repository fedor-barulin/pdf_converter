from loguru import logger
import sys
import os

# Создаем папку для логов, если ее нет
os.makedirs("logs", exist_ok=True)

# Настройка логирования и аудита (Enterprise compliance)
logger.remove()
# Вывод в консоль
logger.add(sys.stdout, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>")
# Файл для аудита с ротацией
logger.add("logs/audit.log", rotation="10 MB", retention="30 days", level="INFO", format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}")

def get_logger():
    return logger
