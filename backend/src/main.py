# backend/src/main.py
"""
Главный файл FastAPI приложения
"""

import logging
import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Универсальный импорт config
try:
    from config import settings
except ImportError:
    # Добавляем родительскую директорию в путь
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from config import settings

# Импорты из созданных модулей
from database import Base, engine
from routers import (
    auth_router,
    places_router,
    reviews_router,
    moderation_router,
    recommendations_router
)

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    # Startup
    logger.info("Запуск приложения...")
    
    try:
        # Создание таблиц
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("✅ Таблицы базы данных созданы")
        
        # Проверка подключения к Ollama
        try:
            from services.llm_service import LLMService
            llm_service = LLMService()
            is_connected = await llm_service.client.test_connection()
            if is_connected:
                logger.info(f"✅ Ollama подключен, модель: {settings.OLLAMA_MODEL}")
            else:
                logger.warning("⚠️  Ollama не доступен. Проверьте API ключ и интернет-соединение")
        except ImportError as e:
            logger.warning(f"⚠️  Не удалось импортировать LLMService: {e}")
        
        # Создание тестовых данных
        await create_test_data()
        logger.info("✅ Тестовые данные созданы")
        
        # Обновление рейтингов всех мест
        try:
            from utils.rating_updater import update_all_place_ratings
            from database import get_db
            async for db in get_db():
                await update_all_place_ratings(db)
                break
        except ImportError as e:
            logger.warning(f"⚠️  Не удалось обновить рейтинги: {e}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка при запуске: {e}")
    
    yield  # Приложение работает
    
    # Shutdown
    logger.info("Остановка приложения...")


async def create_test_data():
    """Создание тестовых данных"""
    try:
        from sqlalchemy.ext.asyncio import AsyncSession
        from sqlalchemy import select
        
        from database import engine, Place
        from dependencies import get_or_create_user_by_role
        
        async with AsyncSession(engine) as session:
            try:
                # Создаем тестового пользователя
                test_user = await get_or_create_user_by_role(session, "user")
                
                # Создаем тестовые места если их нет
                result = await session.execute(select(Place))
                places = result.scalars().all()
                
                if not places:
                    test_places = [
                        Place(
                            name="Кофейня Central Perk",
                            description="Уютная кофейня с лучшим кофе в городе",
                            category="cafe",
                            address="ул. Центральная, 10",
                            city="Москва",
                            price_level=2,
                            tags=["кофе", "десерты", "wi-fi", "уютно"],
                            created_by=test_user.id
                        ),
                        # ... остальные места
                    ]
                    
                    for place in test_places:
                        session.add(place)
                    
                    await session.flush()
                
                await session.commit()
                    
            except Exception as e:
                logger.error(f"Ошибка создания тестовых данных: {e}")
                await session.rollback()
    except ImportError as e:
        logger.warning(f"⚠️  Не удалось создать тестовые данные: {e}")


# Создание приложения FastAPI
app = FastAPI(
    title="Travel Recommendation API",
    description="API для системы рекомендаций мест отдыха с интеграцией LLM",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключение роутеров
app.include_router(auth_router, prefix="/api/v1/auth", tags=["Аутентификация"])
app.include_router(places_router, prefix="/api/v1/places", tags=["Места"])
app.include_router(reviews_router, prefix="/api/v1/reviews", tags=["Отзывы"])
app.include_router(moderation_router, prefix="/api/v1/moderation", tags=["Модерация"])
app.include_router(recommendations_router, prefix="/api/v1/recommendations", tags=["Рекомендации"])


async def create_test_data():
    """Создание тестовых данных"""
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy import select
    
    async with AsyncSession(engine) as session:
        try:
            # Создаем тестового пользователя
            test_user = await get_or_create_user_by_role(session, "user")
            
            # Создаем тестовые места если их нет
            result = await session.execute(select(Place))
            places = result.scalars().all()
            
            if not places:
                test_places = [
                    Place(
                        name="Кофейня Central Perk",
                        description="Уютная кофейня с лучшим кофе в городе",
                        category="cafe",
                        address="ул. Центральная, 10",
                        city="Москва",
                        price_level=2,
                        tags=["кофе", "десерты", "wi-fi", "уютно"],
                        created_by=test_user.id
                    ),
                    Place(
                        name="Ресторан Итальянская кухня",
                        description="Аутентичная итальянская пицца и паста",
                        category="restaurant",
                        address="ул. Итальянская, 5",
                        city="Москва",
                        price_level=3,
                        tags=["итальянская кухня", "пицца", "паста", "романтично"],
                        created_by=test_user.id
                    ),
                    Place(
                        name="Парк Горького",
                        description="Большой городской парк для прогулок",
                        category="park",
                        address="Крымский Вал, 9",
                        city="Москва",
                        price_level=1,
                        tags=["парк", "прогулки", "природа", "бесплатно"],
                        created_by=test_user.id
                    )
                ]
                
                for place in test_places:
                    session.add(place)
                
                await session.flush()
            
            await session.commit()
                
        except Exception as e:
            logger.error(f"Ошибка создания тестовых данных: {e}")
            await session.rollback()


# ========== ОСНОВНЫЕ ЭНДПОИНТЫ ==========

@app.get("/")
async def root():
    return {
        "message": "Travel Recommendation API with Ollama is running!",
        "docs": "/docs",
        "version": "2.0.0",
        "llm": "Ollama Cloud",
        "note": "Используется модульная структура"
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "travel-recommendation-api"}


@app.get("/llm-status")
async def llm_status():
    """Проверка статуса Ollama"""
    llm_service = LLMService()
    
    # Проверяем подключение
    is_connected = await llm_service.client.test_connection()
    
    # Делаем тестовый запрос если подключение есть
    test_result = None
    if is_connected:
        test_result = await llm_service.summarize_review("Отличное место, рекомендую!", 5)
    
    return {
        "llm": "Ollama",
        "model": settings.OLLAMA_MODEL,
        "base_url": settings.OLLAMA_BASE_URL,
        "connected": is_connected,
        "test_successful": test_result is not None and len(test_result) > 0,
        "test_result": test_result[:100] + "..." if test_result else None,
    }


@app.get("/test")
async def test_endpoint():
    """Тестовый эндпоинт для проверки работы"""
    return {
        "status": "ok",
        "message": "API работает корректно",
        "endpoints": {
            "create_place": "POST /api/v1/places/",
            "create_review": "POST /api/v1/reviews/",
            "get_places": "GET /api/v1/places/",
            "get_recommendations": "GET /api/v1/recommendations/personal",
            "llm_status": "GET /llm-status"
        }
    }