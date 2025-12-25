# backend/src/llm_processor.py
import json
import re
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple
from uuid import uuid4

logger = logging.getLogger(__name__)

class LLMProcessor:
    """Обработчик данных через LLM"""
    
    def __init__(self, llm_service):
        self.llm_service = llm_service
    
    async def process_event_data(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Обработка данных мероприятия через LLM
        Возвращает структурированные данные с правильными полями
        """
        try:
            prompt = f"""Ты помощник для структурирования данных о мероприятиях.

ИСХОДНЫЕ ДАННЫЕ:
{json.dumps(raw_data, ensure_ascii=False, indent=2)}

ЗАДАЧА:
1. Извлеки ЧИСТОЕ НАЗВАНИЕ мероприятия (без дат, цен, лишних слов)
2. Определи ТИП МЕРОПРИЯТИЯ (event - временное, place - постоянное)
3. Извлеки ДАТУ и ВРЕМЯ начала
4. Определи СРЕДНИЙ ЧЕК (если есть цены)
5. Извлечи АДРЕС
6. Создай КРАТКОЕ ОПИСАНИЕ (1-2 предложения)

ПРАВИЛА:
- Для КОНЦЕРТОВ, ТЕАТРОВ, КИНО (определенные сеансы) - это временные мероприятия (event)
- Для КАФЕ, РЕСТОРАНОВ, ПАРКОВ, КИНОТЕАТРОВ - это постоянные места (place)

ВРЕМЯ РАБОТЫ:
- Для мероприятий: указывай время начала события
- Для мест: указывай расписание работы если есть

СРЕДНИЙ ЧЕК (price_level):
- до 500 руб: уровень 1 (дешево)
- 500-2000 руб: уровень 2 (средне)
- от 2000 руб: уровень 3 (дорого)

ДАТА ИСТЕЧЕНИЯ (expired_at):
- Для мероприятий: время начала мероприятия
- Для мест: null (вечное)

ВЕРНИ ТОЛЬКО JSON:
{{
    "name": "чистое название",
    "category": "категория",
    "city": "город",
    "address": "адрес или null",
    "description": "краткое описание",
    "working_hours": "расписание работы (для мест); дата и время начала (для мероприятий)",
    "price_level": 1|2|3,
    "avg_check": "средний чек в рублях",
    "tags": ["список", "тегов"],
    "is_active": true/false,
    "validation_reason": "причина"
}}

Пример для концерта:
{{
    "name": "Баста — Guf",
    "category": "concert",
    "city": "Москва",
    "address": "Большая спортивная арена «Лужники», Москва",
    "description": "Совместный концерт известных рэп-исполнителей",
    "working_hours": "2026-08-28 19:00:00",
    "price_level": 3,
    "avg_check": "от 1500 руб",
    "tags": ["концерт", "рэп", "музыка", "мероприятие"],
    "is_active": true,
    "validation_reason": "Есть название, дата и цена"
}}

Пример для кафе:
{{
    "name": "Кофейня Starbucks",
    "category": "cafe",
    "city": "Москва",
    "address": "ул. Тверская, 10, Москва",
    "description": "Сетевая кофейня с кофе и десертами",
    "working_hours": "Пн-Пт: 8:00-22:00, Сб-Вс: 9:00-23:00",
    "price_level": 2,
    "avg_check": "300-500 руб",
    "tags": ["кофейня", "кофе", "десерты", "кафе"],
    "is_active": true,
    "validation_reason": "Есть название, адрес и расписание"
}}"""
            
            response = await self.llm_service.client._call_api(
                prompt, 
                temperature=0.1, 
                max_tokens=2000
            )
            
            if not response:
                logger.error("LLM не ответил")
                return self._create_fallback_data(raw_data)
            
            # Извлекаем JSON
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                try:
                    result = json.loads(json_match.group())
                    if result.get("is_active", False):
                        return result
                    else:
                        logger.warning(f"LLM отклонил данные: {result.get('validation_reason')}")
                except json.JSONDecodeError as e:
                    logger.error(f"Ошибка парсинга JSON: {e}")
            
            return self._create_fallback_data(raw_data)
            
        except Exception as e:
            logger.error(f"Ошибка LLM обработки: {e}")
            return self._create_fallback_data(raw_data)
    
    def _create_fallback_data(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Создает fallback данные если LLM не сработал"""
        # Определяем тип по категории
        event_categories = ["concert", "theatre", "art", "cinema", "excursions", "quest"]
        is_event = raw_data.get("category") in event_categories
        
        return {
            "name": raw_data.get("name", "Неизвестное место"),
            "category": raw_data.get("category", "other"),
            "city": raw_data.get("city", "Москва"),
            "address": raw_data.get("address"),
            "description": raw_data.get("description", ""),
            "working_hours": None,
            "price_level": 2,
            "avg_check": "не указан",
            "tags": ["parsed", raw_data.get("category", "other")],
            "is_active": True,
            "validation_reason": "fallback после ошибки LLM"
        }
    
    def parse_datetime_string(self, datetime_str: str) -> Optional[datetime]:
        """Парсит строку с датой и временем в datetime"""
        if not datetime_str:
            return None
        
        try:
            # Пробуем разные форматы
            formats = [
                "%Y-%m-%d %H:%M:%S",
                "%d.%m.%Y %H:%M",
                "%d %B %Y %H:%M",  # 28 августа 2026 19:00
            ]
            
            for fmt in formats:
                try:
                    return datetime.strptime(datetime_str, fmt)
                except ValueError:
                    continue
            
            return None
        except Exception as e:
            logger.error(f"Ошибка парсинга даты '{datetime_str}': {e}")
            return None
    
    def calculate_expired_at(self, event_type: str, event_datetime: Optional[str]) -> Optional[datetime]:
        """Вычисляет expired_at на основе типа и даты"""
        if event_type == "event" and event_datetime:
            # Для мероприятий - время начала + 1 день (на всякий случай)
            dt = self.parse_datetime_string(event_datetime)
            if dt:
                return dt + timedelta(days=1)
        
        # Для постоянных мест - через 90 дней (будет обновляться при парсинге)
        if event_type == "place":
            return datetime.utcnow() + timedelta(days=90)
        
        return None