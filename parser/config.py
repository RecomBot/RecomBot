# parser/config.py
import os
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field

# Корень проекта
PROJECT_ROOT = Path(__file__).parent.parent


class ParserConfig(BaseSettings):
    """Конфигурация парсера"""
    
    # Парсинг
    PARSE_CATEGORIES: list[str] = Field(
        default=["concert", "theatre", "art", "cinema", "excursions", "quest"],
        description="Категории для парсинга"
    )
    PARSE_CITY: str = Field(
        default="Moscow",
        description="Город для парсинга"
    )
    MAX_PAGES_PER_CATEGORY: int = Field(
        default=3,
        description="Максимальное количество страниц для парсинга в каждой категории"
    )
    
    # Задержки и ограничения
    REQUEST_DELAY: float = Field(
        default=2.0,
        description="Задержка между запросами (секунды)"
    )
    PAGE_LOAD_TIMEOUT: int = Field(
        default=30,
        description="Таймаут загрузки страницы (секунды)"
    )
    
    # Selenium настройки
    SELENIUM_HEADLESS: bool = Field(
        default=True,
        description="Запуск браузера в headless режиме"
    )
    SELENIUM_WINDOW_SIZE: tuple[int, int] = Field(
        default=(1920, 1080),
        description="Размер окна браузера"
    )
    
    # БД
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/travel_db",
        validation_alias="DATABASE_URL"
    )
    
    # Логирование
    LOG_LEVEL: str = Field(
        default="INFO",
        description="Уровень логирования"
    )
    
    class Config:
        env_file = PROJECT_ROOT / ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


# Глобальный экземпляр конфигурации
config = ParserConfig()