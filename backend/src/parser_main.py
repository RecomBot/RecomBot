# backend/src/parser_main.py
import asyncio
import logging
from datetime import datetime
import signal
import sys

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

async def run_afisha_parser():
    """Запуск парсера Яндекс.Афиши"""
    logger.info("🎭 Запуск парсера Яндекс.Афиши...")
    try:
        from parser_unified import run_parser as run_afisha
        await run_afisha()
        logger.info("✅ Парсер Яндекс.Афиши завершил работу")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка парсера Яндекс.Афиши: {e}")
        return False

async def run_maps_parser():
    """Запуск парсера Яндекс.Карт"""
    logger.info("🗺️ Запуск парсера Яндекс.Карт...")
    try:
        from first_yandex_maps_llm_parser_full import run_full_llm_parser as run_maps
        await run_maps()
        logger.info("✅ Парсер Яндекс.Карт завершил работу")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка парсера Яндекс.Карт: {e}")
        return False

async def run_all_parsers():
    """Запуск всех парсеров последовательно"""
    logger.info("=" * 60)
    logger.info("🚀 ЗАПУСК ВСЕХ ПАРСЕРОВ")
    logger.info(f"Время начала: {datetime.now().isoformat()}")
    logger.info("=" * 60)
    
    # Запускаем парсер Яндекс.Карт (реже обновляется)
    maps_success = await run_maps_parser()
    
    if maps_success:
        logger.info("✅ Парсер Яндекс.Карт успешно выполнен")
    else:
        logger.warning("⚠️ Парсер Яндекс.Карт завершился с ошибками")
    
    # Запускаем парсер Яндекс.Афиши (чаще обновляется)
    afisha_success = await run_afisha_parser()
    
    if afisha_success:
        logger.info("✅ Парсер Яндекс.Афиши успешно выполнен")
    else:
        logger.warning("⚠️ Парсер Яндекс.Афиши завершился с ошибками")
    
    logger.info("=" * 60)
    logger.info(f"Время завершения: {datetime.now().isoformat()}")
    if maps_success and afisha_success:
        logger.info("🎉 Все парсеры успешно завершены!")
    else:
        logger.warning("⚠️ Некоторые парсеры завершились с ошибками")
    logger.info("=" * 60)

async def scheduled_parsers():
    """Запуск парсеров по расписанию"""
    logger.info("🔄 Планировщик парсеров запущен")
    
    # Конфигурация интервалов
    INTERVAL_AFISHA = 6 * 3600  # 6 часов для мероприятий
    INTERVAL_MAPS = 24 * 3600   # 24 часа для заведений
    
    while True:
        try:
            current_time = datetime.now()
            logger.info(f"⏰ Начинаем цикл парсинга в {current_time.strftime('%H:%M:%S')}")
            
            # Всегда запускаем Яндекс.Афишу
            await run_afisha_parser()
            
            # Яндекс.Карты запускаем раз в сутки, в 3 часа ночи
            if current_time.hour == 3:
                logger.info("🌙 Запускаем ночной парсинг Яндекс.Карт...")
                await run_maps_parser()
            else:
                logger.info(f"⏳ Яндекс.Карты будут запущены в 3:00 (сейчас {current_time.hour}:{current_time.minute})")
            
            logger.info(f"💤 Ожидаем {INTERVAL_AFISHA//3600} часов до следующего запуска...")
            await asyncio.sleep(INTERVAL_AFISHA)
            
        except Exception as e:
            logger.error(f"❌ Ошибка в планировщике: {e}")
            await asyncio.sleep(300)  # Пауза 5 минут при ошибке

def signal_handler(signum, frame):
    """Обработчик сигналов для graceful shutdown"""
    logger.info("🛑 Получен сигнал завершения, останавливаю парсеры...")
    sys.exit(0)

if __name__ == "__main__":
    import argparse
    
    # Настройка обработчиков сигналов
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    parser = argparse.ArgumentParser(description="Главный планировщик парсеров")
    parser.add_argument("--once", action="store_true", help="Запустить все парсеры один раз")
    parser.add_argument("--schedule", action="store_true", help="Запустить по расписанию")
    parser.add_argument("--afisha-only", action="store_true", help="Только Яндекс.Афиша")
    parser.add_argument("--maps-only", action="store_true", help="Только Яндекс.Карты")
    
    args = parser.parse_args()
    
    try:
        if args.once:
            asyncio.run(run_all_parsers())
        elif args.schedule:
            asyncio.run(scheduled_parsers())
        elif args.afisha_only:
            asyncio.run(run_afisha_parser())
        elif args.maps_only:
            asyncio.run(run_maps_parser())
        else:
            # По умолчанию - один раз все парсеры
            asyncio.run(run_all_parsers())
            
    except KeyboardInterrupt:
        logger.info("👋 Завершение работы по запросу пользователя")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        sys.exit(1)