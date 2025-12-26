# backend/src/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
from .database import create_tables
from .routers import (
    health,
    auth,
    places,
    reviews,
    recommendations,
    moderation
)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Создание приложения
app = FastAPI(
    title="Travel Recommendation API",
    version="1.0.0",
    description="API для персонализированных рекомендаций мест отдыха и развлечений",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене указать конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключение роутеров
app.include_router(health.router)
app.include_router(auth.router, prefix="/api/v1")
app.include_router(places.router, prefix="/api/v1")
app.include_router(reviews.router, prefix="/api/v1")
app.include_router(recommendations.router, prefix="/api/v1")

@app.on_event("startup")
async def startup_event():
    """Действия при запуске приложения"""
    logger.info("🚀 Запуск Travel Recommendation API...")
    
    # Создаем таблицы (только для разработки!)
    try:
        await create_tables()
        logger.info("✅ Таблицы БД созданы/проверены")
    except Exception as e:
        logger.error(f"❌ Ошибка при создании таблиц: {e}")
        # В продакшене используем миграции Alembic
    
    logger.info("✅ Приложение готово к работе")

@app.on_event("shutdown")
async def shutdown_event():
    """Действия при остановке приложения"""
    logger.info("🛑 Остановка приложения...")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True  # Только для разработки
    )