# GidRecBot/bot/config.py
import sys
import os

# Добавляем путь к shared
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from shared.config import config
    # Для обратной совместимости экспортируем переменные
    BOT_TOKEN = config.BOT_TOKEN
    API_BASE_URL = config.API_BASE_URL
    MODERATOR_TG_ID = config.MODERATOR_TG_ID
    ADMIN_TG_ID = config.ADMIN_TG_ID
except ImportError:
    # Fallback для разработки
    from dotenv import load_dotenv
    load_dotenv()
    
    BOT_TOKEN = os.getenv("BOT_TOKEN", "")
    API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8001")
    MODERATOR_TG_ID = int(os.getenv("MODERATOR_TG_ID", 987654321))
    ADMIN_TG_ID = int(os.getenv("ADMIN_TG_ID", 999999999))
    
    # Создаем config для совместимости
    class Config:
        def __init__(self):
            self.BOT_TOKEN = BOT_TOKEN
            self.API_BASE_URL = API_BASE_URL
            self.MODERATOR_TG_ID = MODERATOR_TG_ID
            self.ADMIN_TG_ID = ADMIN_TG_ID
    
    config = Config()

__all__ = ['config', 'BOT_TOKEN', 'API_BASE_URL', 'MODERATOR_TG_ID', 'ADMIN_TG_ID']