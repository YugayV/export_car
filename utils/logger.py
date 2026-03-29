import logging
import os
from datetime import datetime

def setup_logger(name, log_file='logs/bot.log', level=logging.INFO):
    """Настройка логгера"""
    
    # Создаем директорию для логов если её нет
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    
    # Формат логов
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Хендлер для файла
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(formatter)
    
    # Хендлер для консоли
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    # Создаем логгер
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger