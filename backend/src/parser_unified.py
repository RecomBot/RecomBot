# backend/src/parser_unified.py
import asyncio
import re
import logging
import urllib.parse
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from uuid import uuid4, UUID
import os

from dotenv import load_dotenv
import pandas as pd

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Импортируем модели из main_single
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, func, and_, text
import sys
from pathlib import Path

# Добавляем путь для импорта
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

from config_parser import config
from main_single import Place, User

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ========== СОЗДАНИЕ ДВИЖКА БД ==========
engine = create_async_engine(config.DATABASE_URL, echo=True)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# ========== SELENIUM ДЛЯ DOCKER ==========

def create_driver() -> webdriver.Chrome:
    """Создание драйвера Selenium для Docker"""
    options = Options()
    
    # Обязательные параметры для Docker
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    
    if config.SELENIUM_HEADLESS:
        options.add_argument("--headless=new")
    
    # User-Agent
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    # Дополнительные параметры для стабильности
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    # Бинарный путь к Chrome в Docker
    options.binary_location = "/usr/bin/google-chrome"
    
    # Создаем сервис с явным указанием пути к chromedriver
    service = Service(executable_path="/usr/local/bin/chromedriver")
    
    try:
        driver = webdriver.Chrome(service=service, options=options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        driver.implicitly_wait(10)
        logger.info("✅ Chrome драйвер успешно создан в Docker")
        return driver
    except Exception as e:
        logger.error(f"❌ Ошибка создания Chrome драйвера: {e}")
        
        # Fallback: попробуем без service
        try:
            driver = webdriver.Chrome(options=options)
            logger.info("✅ Chrome драйвер создан (fallback)")
            return driver
        except Exception as e2:
            logger.error(f"❌ Fallback также не сработал: {e2}")
            raise

# ========== УТИЛИТЫ ==========

def make_correct_url(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    m = re.search(r"(https?://\S+\.(?:jpg|jpeg|png|gif|webp))", url)
    return m.group(1) if m else None

def replace_illegal_characters(text: str) -> str:
    if isinstance(text, str):
        return "".join(ch if ch.isprintable() else " " for ch in text)
    return text

# ========== ПАРСИНГ ==========

async def parse_list_page(driver: webdriver.Chrome, url: str, category: str) -> pd.DataFrame:
    """Парсинг страницы с мероприятиями"""
    logger.info(f"Парсим URL: {url} (категория: {category})")
    
    try:
        driver.get(url)
        await asyncio.sleep(5)  # Даем время для загрузки
        
        items = []
        
        # ПЕРВЫЙ ПУТЬ: ищем структурированные карточки
        selectors = [
            "[data-test-id='eventCard-root']",
            "[data-event-id]",
            ".event-card",
            ".card",
            "article[class*='event']"
        ]
        
        cards = []
        for selector in selectors:
            found_cards = driver.find_elements(By.CSS_SELECTOR, selector)
            if found_cards:
                cards = found_cards
                logger.info(f"Найдено {len(cards)} карточек с селектором: {selector}")
                try:
                    first_card = cards[0]
                    logger.info(f"  Текст: {first_card.text[:100]}...")
                    logger.info(f"  HTML атрибуты: {first_card.get_attribute('outerHTML')[:200]}...")
                    
                    # Пробуем найти ссылку в карточке
                    link = first_card.find_element(By.TAG_NAME, "a")
                    logger.info(f"  Ссылка: {link.get_attribute('href')}")
                    logger.info(f"  Название ссылки: {link.text[:50]}")
                except Exception as e:
                    logger.error(f"Ошибка при анализе карточки: {e}")
                break
        
        if cards:
            # Обработка структурированных карточек
            for card in cards[:20]:  # Берём первые 20 карточек
                try:
                    # Ищем ссылку в карточке
                    link_elements = card.find_elements(By.TAG_NAME, "a")
                    if not link_elements:
                        continue
                    
                    link = link_elements[0]
                    href = link.get_attribute("href")
                    if not href:
                        continue
                    
                    # СПОСОБ 1: Ищем название в атрибуте data-event-id (у карточки)
                    event_id = card.get_attribute("data-event-id")
                    
                    # СПОСОБ 2: Ищем название в тексте всей карточки
                    card_text = card.text.strip()
                    
                    # Извлекаем название из текста карточки
                    name = "Неизвестное мероприятие"
                    if card_text:
                        # Пытаемся найти строку с заглавными буквами (название)
                        lines = card_text.split('\n')
                        for line in lines:
                            line_stripped = line.strip()
                            # Ищем строку, которая выглядит как название
                            if (len(line_stripped) > 5 and 
                                not line_stripped[0].isdigit() and  # Не начинается с цифры
                                not '₽' in line_stripped and        # Не содержит знак рубля
                                not '%' in line_stripped and        # Не содержит процент
                                not line_stripped.lower().startswith('от') and  # Не начинается с "от"
                                not any(word in line_stripped.lower() for word in ['декабря', 'января', 'февраля'])):  # Не содержит месяц
                                name = line_stripped[:100]  # Ограничиваем длину
                                break
                    
                    # Если не нашли в тексте, используем часть URL как название
                    if name == "Неизвестное мероприятие" and href:
                        # Извлекаем название из URL: /moscow/concert/global-winter-fest -> global-winter-fest
                        url_parts = href.split('/')
                        if len(url_parts) > 0:
                            last_part = url_parts[-1]
                            if '?' in last_part:
                                last_part = last_part.split('?')[0]
                            # Заменяем дефисы на пробелы и делаем первую букву заглавной
                            name = ' '.join(word.capitalize() for word in last_part.replace('-', ' ').split())
                    
                    # Получаем изображение
                    img_url = None
                    img_elements = card.find_elements(By.TAG_NAME, "img")
                    if img_elements:
                        img_url = img_elements[0].get_attribute("src") or img_elements[0].get_attribute("data-src")
                    
                    # Получаем описание из текста карточки
                    description = ""
                    if card_text:
                        # Берем первые 200 символов текста карточки как описание
                        description = card_text[:200]
                    
                    items.append({
                        "name": name,
                        "description": description,
                        "image": img_url,
                        "url": href,
                        "category": category,
                        "city": "Москва",
                        "source": "yandex_afisha"
                    })
                    
                    logger.debug(f"Добавлено мероприятие: {name}")
                    
                except Exception as e:
                    logger.debug(f"Ошибка при обработке карточки: {e}")
                    continue
        else:
            # ВТОРОЙ ПУТЬ: если карточек нет, ищем все ссылки на события
            logger.warning(f"Структурированные карточки не найдены, ищем ссылки...")
            
            all_links = driver.find_elements(By.TAG_NAME, "a")
            logger.info(f"Всего ссылок на странице: {len(all_links)}")
            
            for link in all_links[:100]:  # Ограничиваем количество
                try:
                    href = link.get_attribute("href")
                    if not href:
                        continue
                    
                    # Фильтруем только ссылки на мероприятия
                    if not any(keyword in href.lower() for keyword in ["/event/", "/concert/", "/theatre/", "/movie/", "/art/", "/excursion/"]):
                        continue
                    
                    # Получаем текст ссылки как название
                    name = link.text.strip()
                    if not name or len(name) < 3:
                        # Пробуем получить название из других атрибутов
                        name = link.get_attribute("aria-label") or link.get_attribute("title") or "Мероприятие"
                    
                    # Извлекаем город из URL или текста
                    city = "Москва"
                    if "moscow" in href.lower() or "москв" in name.lower():
                        city = "Москва"
                    elif "spb" in href.lower() or "санкт-петербург" in name.lower():
                        city = "Санкт-Петербург"
                    
                    items.append({
                        "name": name[:200],  # Ограничиваем длину
                        "description": f"Ссылка на мероприятие в категории {category}",
                        "image": None,
                        "url": href,
                        "category": category,
                        "city": city,
                        "source": "yandex_afisha"
                    })
                    
                except Exception as e:
                    continue
        
        df = pd.DataFrame(items)
        if df.empty:
            logger.warning(f"Не удалось собрать данные для {url}")
            return df
        
        # Очистка данных
        df["description"] = df["description"].apply(replace_illegal_characters)
        df["image"] = df["image"].apply(make_correct_url)
        df = df.drop_duplicates(subset=["name", "category", "city"])
        
        logger.info(f"Собрано {len(df)} записей для категории {category}")
        logger.info(f"Примеры найденных мест: {df['name'].head(3).tolist() if not df.empty else 'нет'}")
        
        return df
        
    except Exception as e:
        logger.error(f"Ошибка при парсинге {url}: {e}")
        return pd.DataFrame()

# ========== СОХРАНЕНИЕ В БД ==========

async def get_or_create_parser_user(session: AsyncSession) -> User:
    """Получение или создание пользователя для парсера"""
    try:
        # Ищем пользователя парсера
        result = await session.execute(
            select(User).where(User.telegram_id == 999999998)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            user = User(
                id=uuid4(),
                telegram_id=999999998,
                username="yandex_parser",
                first_name="Парсер",
                last_name="Яндекс Афиши",
                role="moderator",
                preferences={"parser": True, "source": "yandex_afisha"},
                is_active=True
            )
            session.add(user)
            await session.flush()
            logger.info("✅ Создан пользователь для парсера Яндекс Афиши")
        
        return user
        
    except Exception as e:
        logger.error(f"Ошибка получения пользователя парсера: {e}")
        raise

async def save_places_to_db(df: pd.DataFrame, session: AsyncSession):
    """Сохранение мест в БД"""
    if df.empty:
        logger.warning("Нет данных для сохранения")
        return
    
    logger.info(f"Пытаемся сохранить {len(df)} записей в БД")
    logger.info(f"Первые 3 записи: {df[['name', 'category', 'city']].head(3).to_dict('records')}")

    try:
        parser_user = await get_or_create_parser_user(session)
        expired_at = datetime.utcnow() + timedelta(days=config.PLACE_EXPIRY_DAYS)
        
        saved_count = 0
        updated_count = 0
        
        for _, row in df.iterrows():
            try:
                # Ищем место от парсера с таким же названием и категорией
                result = await session.execute(
                    select(Place).where(
                        and_(
                            Place.name == row["name"],
                            Place.category == row["category"],
                            Place.city == row["city"],
                            Place.created_by == parser_user.id
                        )
                    )
                )
                existing_place = result.scalar_one_or_none()
                
                if existing_place:
                    # Обновляем
                    existing_place.description = row["description"] or existing_place.description
                    if not existing_place.tags:
                        existing_place.tags = []
                    if "parsed" not in existing_place.tags:
                        existing_place.tags.append("parsed")
                    existing_place.expired_at = expired_at
                    existing_place.updated_at = func.now()
                    updated_count += 1
                else:
                    # Создаем новое
                    place = Place(
                        id=uuid4(),
                        name=row["name"],
                        description=row["description"],
                        category=row["category"],
                        city=row["city"],
                        address=None,
                        price_level=2,
                        tags=["parsed", row["category"], "event", "yandex_afisha"],
                        rating=0.0,
                        is_active=True,
                        expired_at=expired_at,
                        created_by=parser_user.id,
                        moderation_status="active",
                        moderation_reason="Автоматически спарсено из Яндекс Афиши"
                    )
                    session.add(place)
                    saved_count += 1
                    
            except Exception as e:
                logger.error(f"Ошибка при сохранении места '{row['name']}': {e}")
                continue
        
        await session.commit()
        logger.info(f"✅ Сохранено в БД: новых={saved_count}, обновлено={updated_count}")
        return saved_count, updated_count
        
    except Exception as e:
        logger.error(f"Ошибка при сохранении данных: {e}")
        await session.rollback()
        raise

async def cleanup_expired_places(session: AsyncSession):
    """Очистка просроченных мест"""
    try:
        current_time = datetime.utcnow()
        parser_user = await get_or_create_parser_user(session)
        
        # Находим просроченные места от парсера
        result = await session.execute(
            select(Place).where(
                and_(
                    Place.expired_at.isnot(None),
                    Place.expired_at < current_time,
                    Place.created_by == parser_user.id,
                    Place.is_active == True
                )
            )
        )
        expired_places = result.scalars().all()
        
        if expired_places:
            for place in expired_places:
                place.is_active = False
                place.moderation_status = "expired"
                place.moderation_reason = f"Срок действия истек {place.expired_at}"
            
            await session.commit()
            logger.info(f"Деактивировано {len(expired_places)} просроченных мест от парсера")
        else:
            logger.info("Нет просроченных мест от парсера для очистки")
            
    except Exception as e:
        logger.error(f"Ошибка при очистке просроченных мест: {e}")
        await session.rollback()

# ========== ОСНОВНАЯ ФУНКЦИЯ ==========

async def run_parser():
    """Основная функция парсера"""
    logger.info("=" * 50)
    logger.info("Запуск парсера Яндекс Афиши в Docker...")
    
    # Проверяем доступность Chrome
    try:
        import subprocess
        result = subprocess.run(['which', 'google-chrome'], capture_output=True, text=True)
        if result.returncode == 0:
            logger.info(f"✅ Chrome найден: {result.stdout.strip()}")
        else:
            logger.warning("⚠️ Chrome не найден в системе")
        
        result = subprocess.run(['which', 'chromedriver'], capture_output=True, text=True)
        if result.returncode == 0:
            logger.info(f"✅ ChromeDriver найден: {result.stdout.strip()}")
        else:
            logger.warning("⚠️ ChromeDriver не найден в системе")
    except Exception as e:
        logger.warning(f"Не удалось проверить Chrome: {e}")
    
    # Проверяем подключение к БД (НЕ создаём таблицы!)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("✅ Подключение к БД установлено")
    except Exception as e:
        logger.error(f"❌ Ошибка подключения к БД: {e}")
        return
    
    # Создаем драйвер
    driver = None
    try:
        driver = create_driver()
        
        # Тестовая страница для проверки драйвера
        driver.get("https://www.google.com")
        if "Google" in driver.title:
            logger.info("✅ Chrome драйвер работает корректно")
        else:
            logger.warning("⚠️ Chrome драйвер загрузился, но страница не как ожидалось")
        
        all_data = pd.DataFrame()
        
        # Парсим все категории
        for category, url in config.URLS.items():
            try:
                logger.info(f"Начинаем парсинг категории: {category}")
                df = await parse_list_page(driver, url, category)
                if not df.empty:
                    all_data = pd.concat([all_data, df], ignore_index=True)
                    logger.info(f"Категория {category}: собрано {len(df)} мероприятий")
                else:
                    logger.warning(f"Категория {category}: не удалось собрать данные")
                
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.error(f"Ошибка при парсинге категории {category}: {e}")
                continue
        
        if all_data.empty:
            logger.warning("⚠️ Не удалось собрать данные ни с одной страницы")
            return
        
        logger.info(f"Всего собрано {len(all_data)} мероприятий")
        
        # Сохраняем в БД
        async with AsyncSessionLocal() as session:
            saved, updated = await save_places_to_db(all_data, session)
            await cleanup_expired_places(session)
            
            # Статистика
            result = await session.execute(
                select(func.count(Place.id)).where(Place.is_active == True)
            )
            total_active = result.scalar() or 0
            
            logger.info("=" * 50)
            logger.info(f"✅ Парсинг завершен успешно!")
            logger.info(f"📊 Статистика:")
            logger.info(f"   - Новых мест сохранено: {saved}")
            logger.info(f"   - Существующих обновлено: {updated}")
            logger.info(f"   - Всего активных мест в БД: {total_active}")
            logger.info("=" * 50)
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка парсера: {e}", exc_info=True)
    finally:
        if driver:
            try:
                driver.quit()
                logger.info("Selenium драйвер закрыт")
            except:
                pass

async def scheduled_parser():
    """Запуск парсера по расписанию"""
    logger.info(f"🔄 Планировщик парсера запущен. Интервал: {config.PARSE_INTERVAL_HOURS} часов")
    
    while True:
        try:
            await run_parser()
        except Exception as e:
            logger.error(f"Ошибка в scheduled_parser: {e}")
        
        logger.info(f"⏳ Следующий запуск через {config.PARSE_INTERVAL_HOURS} часов...")
        await asyncio.sleep(config.PARSE_INTERVAL_HOURS * 3600)

# ========== ЗАПУСК ==========

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Парсер мероприятий Яндекс Афиши")
    parser.add_argument("--once", action="store_true", help="Запустить один раз")
    parser.add_argument("--schedule", action="store_true", help="Запустить по расписанию")
    parser.add_argument("--test", action="store_true", help="Тестовый режим")
    
    args = parser.parse_args()
    
    if args.test:
        # Тестовый запуск
        logger.info("🧪 ТЕСТОВЫЙ РЕЖИМ")
        asyncio.run(run_parser())
    elif args.once:
        asyncio.run(run_parser())
    elif args.schedule:
        asyncio.run(scheduled_parser())
    else:
        asyncio.run(run_parser())