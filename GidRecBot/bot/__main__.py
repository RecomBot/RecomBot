# bot/__main__.py
import asyncio
import logging
from .bot import dp, bot
from .middlewares.logging import LoggingMiddleware
from .handlers.main_router import router as main_router
from .handlers.register_router import router as register_router
from .handlers.llm_router import router as llm_router          
from .handlers.review_router import router as review_router
from .handlers.fallback_router import router as fallback_router
from .handlers.moderation_router import router as moderation_router
from .utils.http_client import http_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

logging.info("🔌 Подключаем middleware и роутеры")
dp.message.middleware(LoggingMiddleware())


dp.include_router(main_router)
dp.include_router(register_router)
dp.include_router(llm_router)         
dp.include_router(review_router)
dp.include_router(moderation_router) 
dp.include_router(fallback_router)

async def main():
    logging.info("🚀 Бот запускается...")
    try:
        await dp.start_polling(bot)
    finally:
        await http_client.close()

if __name__ == "__main__":
    asyncio.run(main())