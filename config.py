import os
import logging
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Токен бота - ОБЯЗАТЕЛЬНО из переменных окружения
BOT_TOKEN = os.getenv('BOT_TOKEN')

if not BOT_TOKEN or BOT_TOKEN == 'YOUR_BOT_TOKEN_HERE':
    raise ValueError("BOT_TOKEN is not set in environment variables!")

# Настройки базы данных - используем путь, доступный для записи на Railway
DATABASE_PATH = os.getenv('DATABASE_PATH', 'data/bot_database.db')

# Убеждаемся, что папка для данных существует
os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)

# Настройки для парсинга
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
REQUEST_TIMEOUT = 30

# Настройки калькулятора
DEFAULT_DESTINATION = os.getenv('DEFAULT_DESTINATION', 'russia')
EXCHANGE_RATE_API = os.getenv('EXCHANGE_RATE_API', 'https://api.exchangerate-api.com/v4/latest/USD')

# Курсы валют (KRW/USD)
EXCHANGE_RATE = 1300

# Режим отладки
DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'

# Контакты компании
COMPANY_INFO = {
    "name": "Korean Auto Export Co.",
    "phone": "+82 10-5512-1710",
    "email": os.getenv('COMPANY_EMAIL', 'vamp.09.94@gmail.com'),
    "telegram": "@koreanautobot",
    "address": os.getenv('COMPANY_ADDRESS', 'Sosan')
}

# Настройки DeepSeek (OpenRouter)
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')
DEEPSEEK_MODEL = "deepseek/deepseek-chat"

# Настройки DeepSeek (OpenRouter)
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')
DEEPSEEK_MODEL = "deepseek/deepseek-chat"

# Параметры доставки
SHIPPING_PORTS = {
    "busan_vladivostok": {"price": 800, "days": 10},
    "busan_novorossiysk": {"price": 2500, "days": 35},
    "busan_st_petersburg": {"price": 3000, "days": 45},
    "busan_astana": {"price": 2000, "days": 30}
}

# Логирование
LOG_LEVEL = "INFO"
LOG_FILE = "logs/bot.log"

# Создаем папку для логов
os.makedirs("logs", exist_ok=True)

# Настройки для Railway
RAILWAY_ENVIRONMENT = os.getenv('RAILWAY_ENVIRONMENT', False)