# backend/src/yandex_maps_llm_parser_full.py
import asyncio
import logging
import sys
import json
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from uuid import uuid4

# НАСТРОЙКА ЛОГГИРОВАНИЯ
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

logger.info("=" * 60)
logger.info("🤖 ПОЛНЫЙ LLM-ПАРСЕР Яндекс.Карт (3 категории)")
logger.info("=" * 60)

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    logger.info("✅ Selenium импортирован успешно")
except ImportError as e:
    logger.error(f"❌ Ошибка импорта Selenium: {e}")
    sys.exit(1)

try:
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import select, and_
    logger.info("✅ SQLAlchemy импортирован успешно")
except ImportError as e:
    logger.error(f"❌ Ошибка импорта SQLAlchemy: {e}")
    sys.exit(1)

try:
    from config_parser import config
    logger.info("✅ Конфиг импортирован успешно")
except ImportError as e:
    logger.error(f"❌ Ошибка импорта конфига: {e}")
    sys.exit(1)

try:
    from main_single import Place, User
    logger.info("✅ Модели БД импортированы успешно")
except ImportError as e:
    logger.error(f"❌ Ошибка импорта моделей: {e}")
    sys.exit(1)

try:
    from llm_processor import LLMProcessor
    logger.info("✅ LLMProcessor импортирован успешно")
except ImportError as e:
    logger.error(f"❌ Ошибка импорта LLMProcessor: {e}")
    sys.exit(1)

# Используем тот же движок БД
engine = create_async_engine(config.DATABASE_URL, echo=True)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

def create_yandex_maps_driver() -> webdriver.Chrome:
    """Создание драйвера для Яндекс.Карт"""
    logger.info("Создаём драйвер для Яндекс.Карт...")
    
    try:
        options = Options()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--headless=new")
        
        # Яндекс.Карты требуют правильный User-Agent
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        # Дополнительные параметры для стабильности
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        # Бинарный путь к Chrome в Docker
        options.binary_location = "/usr/bin/google-chrome"
        
        # Создаем сервис с явным указанием пути к chromedriver
        service = Service(executable_path="/usr/local/bin/chromedriver")
        
        driver = webdriver.Chrome(service=service, options=options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        # Увеличиваем таймауты для Яндекс.Карт
        driver.set_page_load_timeout(30)
        driver.implicitly_wait(10)
        
        logger.info("✅ Драйвер для Яндекс.Карт создан успешно")
        return driver
        
    except Exception as e:
        logger.error(f"❌ Ошибка создания драйвера: {e}")
        raise

async def collect_organization_links_by_category(driver: webdriver.Chrome, category: str, city: str, limit: int = 10) -> List[str]:
    """
    Собираем ссылки на организации по категории
    """
    logger.info(f"🔗 Собираем ссылки для категории: {category} в {city}")
    
    # Маппинг категорий на русские запросы
    category_map = {
        "park": "парк",
        "cafe": "кофейня",
        "restaurant": "ресторан",
        "museum": "музей",
        "bar": "бар",
        "cinema": "кинотеатр",
        "theatre": "театр",
        "mall": "торговый центр"
    }
    
    query = category_map.get(category, category)
    
    # Формируем URL для поиска
    if category == "park":
        # Для парков используем координаты Москвы
        search_url = f"https://yandex.ru/maps/213/moscow/search/{query}/?ll=37.617698%2C55.755863&z=12"
    else:
        # Для остальных - просто поиск в Москве
        from urllib.parse import quote
        encoded_query = quote(f"{query} {city}")
        search_url = f"https://yandex.ru/maps/213/moscow/search/{encoded_query}/"
    
    logger.info(f"  📄 Открываем страницу поиска: {search_url[:80]}...")
    
    try:
        driver.get(search_url)
        await asyncio.sleep(5)
        
        # Прокручиваем для загрузки результатов
        logger.info("  📜 Прокручиваем страницу...")
        for i in range(4):  # Увеличили прокрутки для большего количества результатов
            driver.execute_script("window.scrollBy(0, 1500);")
            await asyncio.sleep(2)
        
        # Ищем ссылки на карточки организаций
        unique_urls = {}
        
        # Ищем все ссылки на странице
        all_links = driver.find_elements(By.TAG_NAME, "a")
        logger.info(f"  🔍 Найдено {len(all_links)} ссылок на странице")
        
        for link in all_links:
            try:
                href = link.get_attribute('href')
                if href and ('/maps/org/' in href or '/org/' in href):
                    # Нормализуем URL
                    clean_url = href.split('?')[0].split('#')[0]
                    
                    # Извлекаем ID организации
                    org_pattern = r'/org/([^/]+)/(\d+)/?'
                    match = re.search(org_pattern, clean_url)
                    
                    if match:
                        org_name = match.group(1)
                        org_id = match.group(2)
                        
                        # Ключ для уникальности
                        unique_key = f"{org_name}_{org_id}"
                        
                        # Базовый URL карточки
                        base_url = f"https://yandex.ru/maps/org/{org_name}/{org_id}/"
                        
                        # Фильтрация по категории (особенно для парков)
                        if category == "park":
                            # Проверяем по названию ссылки, что это парк, а не ЖК
                            url_lower = base_url.lower()
                            exclude_keywords = ['zhiloy', 'complex', 'sales', 'ofis_prodazh', 'novostroyk']
                            
                            if not any(keyword in url_lower for keyword in exclude_keywords):
                                if unique_key not in unique_urls:
                                    unique_urls[unique_key] = base_url
                        else:
                            # Для других категорий добавляем все
                            if unique_key not in unique_urls:
                                unique_urls[unique_key] = base_url
                        
                        if len(unique_urls) >= limit * 3:  # Больше ссылок для отбора
                            break
                            
            except Exception as e:
                continue
        
        # Возвращаем ограниченное количество ссылок
        result = list(unique_urls.values())[:limit]
        logger.info(f"✅ Собрано {len(result)} уникальных ссылок для {category}")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Ошибка при сборе ссылок для {category}: {e}")
        return []

async def get_page_html_for_llm(driver: webdriver.Chrome, url: str) -> str:
    """
    Получаем HTML-контент страницы для LLM
    """
    logger.info(f"  🌐 Получаем HTML со страницы: {url[:60]}...")
    
    try:
        driver.set_page_load_timeout(15)
        driver.get(url)
        await asyncio.sleep(2)
        
        # Получаем HTML всей страницы
        html_content = driver.page_source
        
        # Извлекаем только важные секции
        important_sections = []
        
        # Ищем заголовок
        try:
            title_elements = driver.find_elements(By.XPATH, "//h1 | //*[contains(@class, 'title')]")
            for elem in title_elements[:2]:
                try:
                    html = elem.get_attribute('outerHTML')
                    if html and len(html) > 10:
                        important_sections.append(f"<TITLE>{html}</TITLE>")
                except:
                    continue
        except:
            pass
        
        # Ищем адрес
        try:
            address_elements = driver.find_elements(By.XPATH, 
                "//*[contains(@class, 'address') or contains(@class, 'адрес') or contains(@class, 'business-contacts')]")
            for elem in address_elements[:3]:
                try:
                    html = elem.get_attribute('outerHTML')
                    if html and len(html) > 20:
                        important_sections.append(f"<ADDRESS>{html}</ADDRESS>")
                except:
                    continue
        except:
            pass
        
        # Ищем время работы
        try:
            hours_elements = driver.find_elements(By.XPATH,
                "//*[contains(@class, 'hours') or contains(@class, 'расписание') or " +
                "contains(@class, 'время') or contains(@class, 'timetable') or " +
                "contains(@class, 'working')]")
            for elem in hours_elements[:3]:
                try:
                    html = elem.get_attribute('outerHTML')
                    if html and len(html) > 20:
                        important_sections.append(f"<HOURS>{html}</HOURS>")
                except:
                    continue
        except:
            pass
        
        if important_sections:
            final_html = "\n".join(important_sections)
            logger.info(f"  📝 Извлечено {len(important_sections)} важных HTML-секций")
        else:
            # Берем первые 4000 символов
            final_html = html_content[:4000]
        
        return final_html
        
    except Exception as e:
        logger.error(f"  ❌ Ошибка получения HTML: {e}")
        return ""
    finally:
        driver.set_page_load_timeout(30)

async def extract_data_with_llm(html_content: str, url: str, category: str, city: str) -> Optional[Dict[str, Any]]:
    """
    Используем LLM для извлечения структурированных данных из HTML
    """
    try:
        from main_single import LLMService
        
        # Инициализируем LLM сервис и процессор
        llm_service = LLMService()
        llm_processor = LLMProcessor(llm_service)  # ← Добавьте
        
        # Подготавливаем сырые данные для LLMProcessor
        raw_data = {
            "name": "Извлечь из HTML",
            "category": category,
            "city": city,
            "address": "Извлечь из HTML",
            "description": f"{category} в {city}",
            "html_content": html_content[:6000],
            "url": url,
            "source": "yandex_maps"
        }
        
        # Обрабатываем через LLMProcessor
        processed_data = await llm_processor.process_event_data(raw_data)
        
        if processed_data.get("is_active", False):
            # Преобразуем в формат для сохранения
            place_data = {
                "name": processed_data["name"],
                "address": processed_data.get("address", ""),
                "working_hours": processed_data.get("working_hours", ""),
                "category": category,
                "city": city,
                "price_level": processed_data.get("price_level", 2),
                "avg_check": processed_data.get("avg_check", "не указан"),
                "tags": processed_data.get("tags", []),
                "source": "yandex_maps_llm_full",
                "url": url
            }
            
            logger.info(f"✅ LLM извлекла: {place_data['name']}")
            if place_data.get("working_hours"):
                logger.info(f"   🕐 Время работы: {place_data['working_hours'][:80]}...")
            if place_data.get("price_level"):
                logger.info(f"   💰 Уровень цен: {place_data['price_level']}/3")
                
            return place_data
        else:
            logger.warning(f"ℹ️ LLM определила как невалидное: {processed_data.get('validation_reason')}")
            return None
        
    except Exception as e:
        logger.error(f"❌ Ошибка вызова LLM: {e}")
        return None

async def parse_category_with_llm(driver: webdriver.Chrome, category: str, city: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Основная функция парсинга категории через LLM
    """
    logger.info(f"🤖 Запускаем парсинг {category} через LLM...")
    
    # 1. Собираем ссылки
    logger.info("📋 ЭТАП 1: Сбор ссылок...")
    urls = await collect_organization_links_by_category(driver, category, city, limit)
    
    if not urls:
        logger.warning(f"❌ Не удалось собрать ссылки для {category}")
        return []
    
    logger.info(f"✅ Собрано {len(urls)} ссылок для {category}")
    
    # 2. Парсим каждую ссылку через LLM
    logger.info("🤖 ЭТАП 2: Парсинг через LLM...")
    all_places = []
    seen_names = set()
    
    for i, url in enumerate(urls):
        logger.info(f"  [{i+1}/{len(urls)}] Обрабатываем {category}...")
        
        try:
            # Получаем HTML страницы
            html_content = await get_page_html_for_llm(driver, url)
            
            if not html_content or len(html_content) < 50:
                logger.warning("    ⚠️ Не удалось получить HTML или он слишком короткий")
                continue
            
            # Извлекаем данные через LLM
            place_data = await extract_data_with_llm(html_content, url, category, city)
            
            if place_data:
                # Проверяем на дубликаты
                name_lower = place_data["name"].lower()
                if name_lower in seen_names:
                    logger.info(f"    ⚠️ Дубликат пропущен: {place_data['name']}")
                    continue
                
                seen_names.add(name_lower)
                all_places.append(place_data)
                logger.info(f"    ✅ Успешно: {place_data['name']}")
                
                if place_data.get("address"):
                    logger.info(f"       📍 {place_data['address'][:60]}...")
                if place_data.get("working_hours"):
                    logger.info(f"       🕐 {place_data['working_hours'][:60]}...")
                
                # Если набрали нужное количество - выходим
                if len(all_places) >= limit:
                    logger.info(f"    🎯 Достигнут лимит в {limit} мест для {category}")
                    break
            else:
                logger.warning("    ⚠️ LLM не смогла извлечь данные")
            
            # Пауза между запросами
            if i < len(urls) - 1:
                await asyncio.sleep(2)
                
        except Exception as e:
            logger.error(f"    ❌ Ошибка обработки: {e}")
            continue
    
    logger.info(f"🎉 Завершено. Найдено {len(all_places)} мест для категории {category}")
    return all_places

async def get_or_create_full_parser_user(session: AsyncSession) -> User:
    """Получение или создание пользователя для полного парсера"""
    try:
        result = await session.execute(
            select(User).where(User.telegram_id == 999999900)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            user = User(
                id=uuid4(),
                telegram_id=999999900,
                username="yandex_maps_full",
                first_name="Парсер",
                last_name="Яндекс Карты (полный)",
                role="moderator",
                preferences={"parser": True, "source": "yandex_maps_full"},
                is_active=True
            )
            session.add(user)
            await session.flush()
            logger.info("✅ Создан пользователь для полного парсера")
        
        return user
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения пользователя: {e}")
        raise

async def save_places_to_db_full(places: List[Dict[str, Any]], session: AsyncSession):
    """Сохранение мест в БД с временем работы"""
    if not places:
        logger.warning("⚠️ Нет данных для сохранения")
        return 0, 0
    
    try:
        parser_user = await get_or_create_full_parser_user(session)
        expired_at = datetime.utcnow() + timedelta(days=90)
        
        saved_count = 0
        updated_count = 0
        
        for place_data in places:
            try:
                # Используем price_level из LLM, если есть, иначе определяем по категории
                price_level = place_data.get("price_level")
                if not price_level:
                    price_level_map = {
                        "park": 1,
                        "cafe": 2,
                        "restaurant": 3,
                        "museum": 2,
                        "bar": 3,
                        "cinema": 2,
                        "theatre": 3,
                        "mall": 2,
                        "other": 2
                    }
                    price_level = price_level_map.get(place_data["category"], 2)
                
                # Создаем описание
                description = f"{place_data['category']} в {place_data['city']}"
                if place_data.get("working_hours"):
                    description += f". Часы работы: {place_data['working_hours']}"
                if place_data.get("avg_check") and place_data["avg_check"] != "не указан":
                    description += f". Средний чек: {place_data['avg_check']}"
                
                # Проверяем существование места
                result = await session.execute(
                    select(Place).where(
                        and_(
                            Place.name == place_data["name"],
                            Place.category == place_data["category"],
                            Place.city == place_data["city"],
                            Place.created_by == parser_user.id
                        )
                    )
                )
                existing_place = result.scalar_one_or_none()
                
                if existing_place:
                    # Обновляем существующее место
                    existing_place.description = description[:500]
                    existing_place.address = place_data.get("address") or existing_place.address
                    existing_place.price_level = price_level
                    
                    # ОБНОВЛЯЕМ ВРЕМЯ РАБОТЫ
                    if place_data.get("working_hours"):
                        existing_place.working_hours = place_data["working_hours"]
                    
                    # Обновляем теги
                    existing_tags = set(existing_place.tags or [])
                    new_tags = set(place_data.get("tags", []))
                    existing_place.tags = list(existing_tags.union(new_tags))
                    
                    existing_place.expired_at = expired_at
                    existing_place.updated_at = datetime.utcnow()
                    updated_count += 1
                    
                    logger.debug(f"📝 Обновлено место: {place_data['name']}")
                else:
                    # Создаём новое место
                    place = Place(
                        id=uuid4(),
                        name=place_data["name"],
                        description=description[:500],
                        category=place_data["category"],
                        address=place_data.get("address", ""),
                        city=place_data["city"],
                        price_level=price_level,
                        tags=place_data.get("tags", ["yandex_maps_llm", place_data["category"], place_data["city"].lower()]),
                        rating=0.0,
                        working_hours=place_data.get("working_hours", ""),
                        is_active=True,
                        expired_at=expired_at,
                        created_by=parser_user.id,
                        moderation_status="active",
                        moderation_reason="Спарсено через LLM с Яндекс.Карт"
                    )
                    session.add(place)
                    saved_count += 1
                    
                    logger.info(f"💾 Сохранено новое место: {place_data['name']}")
                    if place_data.get("working_hours"):
                        logger.info(f"   🕐 Время работы: {place_data['working_hours'][:80]}...")
                    if price_level:
                        logger.info(f"   💰 Уровень цен: {price_level}/3")
                    
            except Exception as e:
                logger.error(f"❌ Ошибка сохранения места '{place_data.get('name', 'unknown')}': {e}")
                continue
        
        await session.commit()
        logger.info(f"✅ Сохранено в БД: новых={saved_count}, обновлено={updated_count}")
        return saved_count, updated_count
        
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения данных: {e}")
        await session.rollback()
        raise

async def run_full_llm_parser():
    """Полный запуск LLM-парсера для всех категорий"""
    logger.info("=" * 60)
    logger.info("🚀 ЗАПУСК ПОЛНОГО LLM-ПАРСЕРА (10x3 категории)")
    logger.info("=" * 60)
    
    driver = None
    
    try:
        driver = create_yandex_maps_driver()
        
        # Категории для парсинга: (категория, город, количество)
        categories_to_parse = [
            ("park", "Москва", 10),
            ("cafe", "Москва", 10),
            ("restaurant", "Москва", 10),
        ]
        
        all_places = []
        
        for category, city, limit in categories_to_parse:
            try:
                logger.info(f"\n{'🌳' if category == 'park' else '☕' if category == 'cafe' else '🍽️'} Парсим {category} в {city} (лимит: {limit})...")
                
                # Парсим категорию через LLM
                places = await parse_category_with_llm(driver, category, city, limit)
                
                if places:
                    all_places.extend(places)
                    logger.info(f"✅ Для {category} найдено {len(places)} мест")
                    
                    # Логируем результаты
                    logger.info(f"📊 Результаты для {category}:")
                    for i, place in enumerate(places[:3], 1):  # Показываем первые 3
                        logger.info(f"   {i}. {place['name']}")
                        if place.get('working_hours'):
                            logger.info(f"      🕐 {place['working_hours'][:60]}...")
                else:
                    logger.warning(f"⚠️ Не найдено мест для {category}")
                
                # Пауза между категориями
                if category != categories_to_parse[-1][0]:  # Если не последняя категория
                    logger.info(f"⏳ Пауза 5 секунд перед следующей категорией...")
                    await asyncio.sleep(5)
                
            except Exception as e:
                logger.error(f"❌ Ошибка при парсинге {category}: {e}")
                continue
        
        if not all_places:
            logger.warning("⚠️ Не удалось найти ни одного места")
            return
        
        logger.info(f"\n📊 ВСЕГО найдено {len(all_places)} мест по всем категориям")
        
        # Группируем по категориям для статистики
        from collections import Counter
        category_counts = Counter([p["category"] for p in all_places])
        logger.info("📈 Статистика по категориям:")
        for category, count in category_counts.items():
            logger.info(f"   • {category}: {count} мест")
        
        # Сохраняем все места в БД
        async with AsyncSessionLocal() as session:
            saved, updated = await save_places_to_db_full(all_places, session)
            
            # Дополнительная статистика
            parser_user = await get_or_create_full_parser_user(session)
            
            # Места от этого парсера
            result = await session.execute(
                select(Place).where(Place.created_by == parser_user.id)
            )
            total_places = len(result.scalars().all())
            
            # Все активные места
            result = await session.execute(
                select(Place).where(Place.is_active == True)
            )
            total_active = len(result.scalars().all())
            
            # Места с временем работы
            result = await session.execute(
                select(Place).where(
                    and_(
                        Place.created_by == parser_user.id,
                        Place.working_hours != None,
                        Place.working_hours != ""
                    )
                )
            )
            places_with_hours = len(result.scalars().all())
            
            logger.info("=" * 60)
            logger.info("🎉 ПАРСИНГ ЗАВЕРШЁН УСПЕШНО!")
            logger.info(f"📈 ИТОГОВАЯ СТАТИСТИКА:")
            logger.info(f"   • Новых мест сохранено: {saved}")
            logger.info(f"   • Обновлено мест: {updated}")
            logger.info(f"   • Всего мест от LLM-парсера: {total_places}")
            logger.info(f"   • Из них с временем работы: {places_with_hours}")
            logger.info(f"   • Всего активных мест в БД: {total_active}")
            logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {e}", exc_info=True)
    finally:
        if driver:
            try:
                driver.quit()
                logger.info("✅ Драйвер закрыт")
            except:
                pass

async def run_test_llm_parser():
    """Тестовый запуск LLM-парсера"""
    logger.info("=" * 60)
    logger.info("🧪 ТЕСТ LLM-ПАРСЕРА (по 3 места каждой категории)")
    logger.info("=" * 60)
    
    driver = None
    
    try:
        driver = create_yandex_maps_driver()
        
        categories_to_parse = [
            ("park", "Москва", 3),
            ("cafe", "Москва", 3),
            ("restaurant", "Москва", 3),
        ]
        
        all_places = []
        
        for category, city, limit in categories_to_parse:
            try:
                logger.info(f"\nПарсим {category} в {city}...")
                places = await parse_category_with_llm(driver, category, city, limit)
                
                if places:
                    all_places.extend(places)
                    logger.info(f"✅ Найдено {len(places)} мест")
                    
                    # Показываем результаты
                    for place in places:
                        logger.info(f"   • {place['name']}")
                        if place.get('working_hours'):
                            logger.info(f"     🕐 {place['working_hours'][:60]}...")
                else:
                    logger.warning(f"⚠️ Не найдено мест")
                
                await asyncio.sleep(3)
                
            except Exception as e:
                logger.error(f"❌ Ошибка: {e}")
                continue
        
        if all_places:
            # Тестовое сохранение
            async with AsyncSessionLocal() as session:
                saved, updated = await save_places_to_db_full(all_places, session)
                logger.info(f"🧪 Тест завершён. Сохранено: {saved}, Обновлено: {updated}")
        else:
            logger.warning("🧪 Не удалось найти места для теста")
            
    except Exception as e:
        logger.error(f"❌ Ошибка в тесте: {e}")
    finally:
        if driver:
            driver.quit()

async def main():
    """Главная функция"""
    try:
        await run_full_llm_parser()
    except Exception as e:
        logger.error(f"❌ Ошибка в main(): {e}")
        raise

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Полный LLM-парсер Яндекс.Карт")
    parser.add_argument("--test", action="store_true", help="Тестовый режим (по 3 места каждой категории)")
    parser.add_argument("--once", action="store_true", help="Полный запуск (10x3 категории)")
    
    args = parser.parse_args()
    
    if args.test:
        logger.info("🧪 ЗАПУСК В ТЕСТОВОМ РЕЖИМЕ")
        asyncio.run(run_test_llm_parser())
    elif args.once:
        logger.info("🚀 ЗАПУСК ПОЛНОГО LLM-ПАРСЕРА")
        asyncio.run(main())
    else:
        # По умолчанию тестовый режим
        logger.info("🧪 ЗАПУСК В ТЕСТОВОМ РЕЖИМЕ (по умолчанию)")
        asyncio.run(run_test_llm_parser())