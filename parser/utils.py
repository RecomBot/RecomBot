# parser/utils.py
"""
Вспомогательные утилиты для парсера
"""
import re
import logging
from typing import Optional
from urllib.parse import urljoin
import asyncio

logger = logging.getLogger(__name__)


def normalize_text(text: str) -> str:
    """Нормализация текста: удаление лишних пробелов, переносов"""
    if not text:
        return ""
    
    # Заменяем множественные пробелы и переносы
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\n+', ' ', text)
    
    return text.strip()


def extract_age_rating(description: str) -> tuple[str, Optional[int]]:
    """Извлечение возрастного рейтинга из описания"""
    age_pattern = r'(\d{1,2})\+'
    match = re.search(age_pattern, description)
    
    if match:
        age = int(match.group(1))
        # Убираем рейтинг из описания
        clean_desc = re.sub(age_pattern, '', description).strip()
        return clean_desc, age
    
    return description, None


def clean_place_name(name: str) -> str:
    """Очистка названия места от лишних символов"""
    if not name:
        return ""
    
    # Удаляем кавычки, лишние точки
    name = name.replace('"', '').replace("'", "")
    name = re.sub(r'\.{2,}', '.', name)
    
    return name.strip()


def normalize_category(category: str) -> str:
    """Нормализация категории места"""
    category_map = {
        "concert": "concert",
        "концерт": "concert",
        "theatre": "theater",
        "театр": "theater",
        "спектакль": "theater",
        "art": "art",
        "искусство": "art",
        "выставка": "art",
        "cinema": "cinema",
        "кино": "cinema",
        "фильм": "cinema",
        "excursions": "excursion",
        "экскурсия": "excursion",
        "тур": "excursion",
        "quest": "quest",
        "квест": "quest",
        "приключение": "quest"
    }
    
    return category_map.get(category.lower(), "other")


async def safe_request(coro, max_retries: int = 3, delay: float = 1.0):
    """
    Безопасный вызов асинхронной функции с повторными попытками
    """
    for attempt in range(max_retries):
        try:
            return await coro
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
            await asyncio.sleep(delay * (attempt + 1))  # Экспоненциальная задержка


def generate_external_id(source: str, source_id: str) -> str:
    """Генерация уникального внешнего ID"""
    return f"{source}:{source_id}"