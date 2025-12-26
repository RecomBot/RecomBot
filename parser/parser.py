# parser/simple_parser.py
"""
Парсер через HTTP запросы (без Selenium)
"""
import asyncio
import logging
from datetime import datetime
import uuid
import aiohttp
from typing import List, Dict

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select

from .config import config
from .models import Place, SourceType, PlaceCategory

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class HTTPParser:
    """Парсер через HTTP API"""
    
    def __init__(self):
        self.db_engine = None
        self.async_session = None
        
    async def initialize(self):
        """Инициализация БД"""
        self.db_engine = create_async_engine(config.DATABASE_URL, echo=False)
        self.async_session = async_sessionmaker(
            self.db_engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
    
    async def fetch_places_from_api(self) -> List[Dict]:
        """Получение мест из тестового API или создание моковых данных"""
        # Здесь можно подключиться к реальному API
        # Для демо используем статические данные
        
        return [
            {
                "name": "Кофейня у Патриарших",
                "description": "Уютное место с домашней выпечкой и кофе из зерен собственной обжарки",
                "category": PlaceCategory.CAFE,
                "city": "Moscow",
                "address": "Тверская улица, 12",
                "rating": 4.7,
                "rating_count": 128,
                "price_level": 3,
                "source": SourceType.YANDEX_AFISHA,
                "external_id": "yandex_afisha_001",
                "external_url": "https://afisha.yandex.ru/moscow/concert"
            },
            # ... остальные места
        ]
    
    async def save_places(self, places: List[Dict]) -> int:
        """Сохранение мест в БД"""
        saved = 0
        async with self.async_session() as session:
            for place_data in places:
                try:
                    # Проверяем, существует ли уже
                    result = await session.execute(
                        select(Place).where(Place.external_id == place_data["external_id"])
                    )
                    if result.scalar_one_or_none():
                        continue
                    
                    place = Place(id=uuid.uuid4(), **place_data)
                    session.add(place)
                    saved += 1
                except Exception as e:
                    logger.error(f"Error saving place: {e}")
            
            await session.commit()
        
        return saved
    
    async def run(self):
        """Основной метод"""
        await self.initialize()
        
        logger.info("🔄 Получение данных...")
        places = await self.fetch_places_from_api()
        
        logger.info(f"📥 Найдено {len(places)} мест")
        
        saved = await self.save_places(places)
        logger.info(f"💾 Сохранено {saved} мест")
        
        await self.close()
    
    async def close(self):
        """Закрытие"""
        if self.db_engine:
            await self.db_engine.dispose()


async def main():
    parser = HTTPParser()
    await parser.run()


if __name__ == "__main__":
    asyncio.run(main())