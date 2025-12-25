# backend/src/config_parser.py
import os
from dotenv import load_dotenv

load_dotenv()

class ParserConfig:
    """Конфигурация для парсера"""
    
    # Database
    DATABASE_URL = os.getenv(
        "DATABASE_URL", 
        "postgresql+asyncpg://postgres:postgres@postgres:5432/travel_db"
    )
    
    # Настройки парсера
    PARSE_INTERVAL_HOURS = int(os.getenv("PARSE_INTERVAL_HOURS", "24"))
    PLACE_EXPIRY_DAYS = int(os.getenv("PLACE_EXPIRY_DAYS", "30"))
    
    # URL для парсинга Яндекс.Афиши
    URLS = {
        "concert": "https://afisha.yandex.ru/moscow/concert",
        "theatre": "https://afisha.yandex.ru/moscow/theatre",
        "art": "https://afisha.yandex.ru/moscow/art",
        "cinema": "https://afisha.yandex.ru/moscow/cinema",
    }
    
    # Категории для парсинга Яндекс.Карт
    YANDEX_MAPS_CATEGORIES = {
        "park": "парк",
        "cafe": "кофейня", 
        "restaurant": "ресторан",
        "museum": "музей",
        "cinema": "кинотеатр",
        "theatre": "театр",
        "bar": "бар",
        "mall": "торговый центр"
    }
    
    # Лимиты
    AFISHA_LIMIT_PER_CATEGORY = 10
    MAPS_LIMIT_PER_CATEGORY = 15
    
    # Города
    CITIES = ["Москва"]
    
    # Настройки Selenium
    SELENIUM_HEADLESS = os.getenv("SELENIUM_HEADLESS", "True").lower() == "true"
    SELENIUM_TIMEOUT = int(os.getenv("SELENIUM_TIMEOUT", "30"))
    
    # LLM настройки (используем из main_single)
    LLM_ENABLED = True
    LLM_TEMPERATURE = 0.1
    LLM_MAX_TOKENS = 2000
    
    @classmethod
    def print_config(cls):
        print("=" * 50)
        print("PARSER CONFIGURATION:")
        print(f"DATABASE_URL: {cls.DATABASE_URL[:50]}...")
        print(f"AFISHA_URLS: {list(cls.AFISHA_URLS.keys())}")
        print(f"MAPS_CATEGORIES: {list(cls.YANDEX_MAPS_CATEGORIES.keys())}")
        print(f"LLM_ENABLED: {cls.LLM_ENABLED}")
        print("=" * 50)

config = ParserConfig()