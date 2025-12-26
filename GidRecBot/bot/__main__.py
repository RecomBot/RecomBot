# GidRecBot/bot/__main__.py - добавить проверку перед запуском
import asyncio
import logging
from .bot import dp, bot
from .utils.http_client import http_client
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

async def check_api_connection():
    """Проверка подключения к API перед запуском бота"""
    logger.info("🔌 Проверка подключения к API...")
    
    max_retries = 5
    retry_delay = 5
    
    for attempt in range(max_retries):
        try:
            # Пробуем получить health status
            is_healthy = await http_client.check_api_health()
            if is_healthy:
                logger.info("✅ API доступен!")
                return True
            else:
                logger.warning(f"⚠️ API не здоров. Попытка {attempt + 1}/{max_retries}")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось подключиться к API. Попытка {attempt + 1}/{max_retries}: {e}")
        
        if attempt < max_retries - 1:
            logger.info(f"⏳ Ожидание {retry_delay} секунд перед повторной попыткой...")
            await asyncio.sleep(retry_delay)
    
    logger.error("❌ Не удалось подключиться к API после всех попыток")
    return False

async def main():
    logging.info("🚀 Бот запускается...")
    
    # Проверяем подключение к API
    if not await check_api_connection():
        logger.error("❌ Бот не может запуститься без подключения к API")
        await http_client.close()
        sys.exit(1)
    
    # Проверяем LLM статус
    try:
        llm_status = await http_client.llm_status()
        logger.info(f"🤖 LLM статус: {llm_status.get('status', 'unknown')}")
    except Exception as e:
        logger.warning(f"⚠️ Не удалось проверить LLM статус: {e}")
    
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"❌ Ошибка в боте: {e}")
    finally:
        await http_client.close()

if __name__ == "__main__":
    asyncio.run(main())