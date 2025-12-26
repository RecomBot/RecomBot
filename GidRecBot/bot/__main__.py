# bot/__main__.py
import asyncio
import logging
from .bot import dp, bot
from .notifications import init_notification_service
from .middlewares.logging import LoggingMiddleware
from .middlewares.user_middleware import UserMiddleware
from .handlers.main_router import router as main_router
from .handlers.register_router import router as register_router
from .handlers.llm_router import router as llm_router          
from .handlers.search_router import router as search_router
from .handlers.review_router import router as review_router
from .handlers.user_reviews_router import router as user_reviews_router
from .handlers.popular_router import router as popular_router
from .handlers.fallback_router import router as fallback_router
from .handlers.moderation_router import router as moderation_router
from .utils.http_client import http_client
from .utils.user_manager import switch_user_role

# Инициализируем сервис уведомлений
notification_service = init_notification_service(bot)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Подключаем middleware
dp.message.middleware(LoggingMiddleware())
dp.callback_query.middleware(LoggingMiddleware())
dp.message.middleware(UserMiddleware())
dp.callback_query.middleware(UserMiddleware())

# Подключаем роутеры
dp.include_router(main_router)
dp.include_router(register_router)
dp.include_router(search_router)
dp.include_router(popular_router)
dp.include_router(llm_router)         
dp.include_router(review_router)
dp.include_router(moderation_router) 
dp.include_router(fallback_router)
dp.include_router(user_reviews_router)

async def on_startup():
    """Действия при запуске бота"""
    logger.info("🚀 Бот запускается...")
    
    # Проверяем подключение к API
    try:
        # Простая проверка доступности API
        response = await http_client.get_places(limit=1)
        if response:
            logger.info("✅ API бэкенда доступен")
        else:
            logger.warning("⚠️ API бэкенда не отвечает")
    except Exception as e:
        logger.error(f"❌ Ошибка подключения к API: {e}")

async def on_shutdown():
    """Действия при остановке бота"""
    logger.info("🛑 Бот останавливается...")
    await http_client.close()

async def main():
    # Выполняем startup действия
    await on_startup()
    
    try:
        # Запускаем polling
        logger.info("📡 Начинаю polling...")
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
    finally:
        # Выполняем shutdown действия
        await on_shutdown()

if __name__ == "__main__":
    asyncio.run(main())