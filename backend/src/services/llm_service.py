# backend/src/services/llm_service.py
"""
Сервис для работы с LLM (Ollama Cloud)
"""

import json
import re
import logging
import os
import sys
from typing import Optional, Dict, Any
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

# Универсальный импорт config
def get_settings():
    """Универсальная функция для получения настроек"""
    try:
        # Попытка 1: Импорт из config.py из родительской директории
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from config import settings
        return settings
    except ImportError:
        # Fallback: настройки из переменных окружения
        class Settings:
            OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "https://ollama.com")
            OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3-coder:480b-cloud")
            OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY", "")
        return Settings()

settings = get_settings()

# Универсальный импорт database
try:
    from ..database import User, Review
except ImportError:
    try:
        from database import User, Review
    except ImportError:
        # Для сервиса эти модели не критичны, можно импортировать позже
        pass

logger = logging.getLogger(__name__)


class OllamaCloudClient:
    """Клиент для работы с облачной моделью через Ollama.com"""
    
    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None, 
                 api_key: Optional[str] = None):
        self.base_url = base_url or settings.OLLAMA_BASE_URL
        self.model = model or settings.OLLAMA_MODEL
        self.api_key = api_key or settings.OLLAMA_API_KEY
        logger.info(f"Ollama Cloud client initialized: {self.model}")
    
    async def _call_api(self, prompt: str, temperature: float = 0.1, 
                       max_tokens: int = 500) -> Optional[str]:
        """Вызов облачного Ollama API"""
        try:
            headers = {}
            if self.api_key:
                headers['Authorization'] = f'Bearer {self.api_key}'
            
            data = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "options": {"temperature": temperature, "num_predict": max_tokens}
            }
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/chat",
                    json=data,
                    headers=headers,
                    timeout=60.0
                )
                
                if response.status_code == 200:
                    result = response.json()
                    return result.get("message", {}).get("content", "").strip()
                else:
                    logger.error(f"Ollama Cloud API error: {response.status_code} - {response.text}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error calling Ollama Cloud API: {e}")
            return None
    
    async def check_review_content(self, text: str) -> Dict[str, Any]:
        """Проверка отзыва на содержание"""
        prompt = f"""Ты - строгий модератор русскоязычных отзывов о заведениях. 
        Твоя задача - анализировать текст и выявлять нарушения по следующим категориям:
        
        КАТЕГОРИИ НАРУШЕНИЙ:
        1. Ненормативная лексика - любые формы нецензурных выражений
        2. Оскорбления - прямые или косвенные унизительные высказывания в адрес людей
        3. Угрозы - выражения, содержащие намерение причинить вред
        4. Спам и реклама - коммерческие предложения, ссылки, рекламный контент
        5. Флуд - бессодержательные или повторяющиеся сообщения
        6. Дискриминация - высказывания, унижающие достоинство по признакам расы, пола и т.д.
        
        ИНСТРУКЦИЯ:
        1. Внимательно проанализируй текст отзыва
        2. Определи, есть ли нарушения по указанным категориям
        3. Принимай решение на основе общего тона и содержания
        4. Будь строг, но справедлив
        
        Отзыв для анализа: "{text}"
        
        ВЕРНИ ТОЛЬКО JSON БЕЗ ЛИШНИХ СЛОВ, ОБЪЯСНЕНИЙ ИЛИ ФОРМАТИРОВАНИЯ:
        {{
            "is_appropriate": true/false,
            "reason": "конкретная причина на русском (2-3 слова)",
            "confidence": число от 0.0 до 1.0,
            "found_issues": ["список найденных проблем"] или [],
            "suggested_action": "approve" или "reject"
        }}
        """
        
        response = await self._call_api(prompt, temperature=0.1, max_tokens=300)
        
        if not response:
            return self._create_fallback_response("Ollama Cloud не ответил")
        
        # Извлекаем JSON из ответа
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        
        # Если не удалось распарсить JSON, анализируем текстовый ответ
        return self._analyze_text_response(response)
    
    def _create_fallback_response(self, reason: str) -> Dict[str, Any]:
        """Создает fallback ответ при ошибке"""
        return {
            "is_appropriate": True,  # По умолчанию разрешаем
            "reason": reason,
            "confidence": 0.5,
            "found_issues": []
        }
    
    def _analyze_text_response(self, response: str) -> Dict[str, Any]:
        """Анализирует текстовый ответ если JSON не получен"""
        response_lower = response.lower()
        
        if any(word in response_lower for word in ["не подходит", "не одобряю", "отклонить", "нецензурн", "оскорблен"]):
            return {
                "is_appropriate": False,
                "reason": "Модель рекомендует отклонить",
                "confidence": 0.7,
                "found_issues": ["определено_моделью"]
            }
        
        if any(word in response_lower for word in ["подходит", "одобряю", "принять", "хороший"]):
            return {
                "is_appropriate": True,
                "reason": "Модель рекомендует принять",
                "confidence": 0.7,
                "found_issues": []
            }
        
        return {
            "is_appropriate": True,
            "reason": "Не удалось определить решение модели",
            "confidence": 0.3,
            "found_issues": []
        }
    
    async def summarize_review(self, text: str, rating: int) -> Optional[str]:
        """Суммаризация отзыва"""
        prompt = f"""Ты - помощник для создания кратких, информативных выжимок из отзывов.
        
        Создай ОБЪЕКТИВНУЮ выжимку в 1-2 предложениях на русском языке.
        Не копируй текст, а анализируй и выдели самое важное.
        
        Контекст: отзыв о заведении питания/отдыха.
        Рейтинг: {rating}/5
        Полный текст отзыва: "{text}"
        
        ВАЖНО: 
        1. Сохрани ключевую мысль
        2. Укажи общий тон (позитивный/негативный/нейтральный)
        3. Выдели конкретные плюсы/минусы если есть
        
        Пример хорошей выжимки: "Пользователь рекомендует заведение за вкусный кофе и дружелюбный персонал, но отмечает высокие цены."
        
        Выжимка (только текст):"""
        
        response = await self._call_api(prompt, temperature=0.2, max_tokens=150)
        
        if response:
            response = response.strip()
            response = response.replace('"', '').replace("'", "")
            return response
        
        return None
    
    async def generate_recommendations(self, preferences: Dict[str, Any], 
                                      review_history: str = "",
                                      categories: list = None,
                                      city: str = "",
                                      budget: str = "") -> Optional[str]:
        """Генерация рекомендаций"""
        if categories is None:
            categories = []
            
        prompt = f"""Ты консультант по местам отдыха. Пользователь ищет рекомендации.

Предпочтения: {preferences}
История отзывов: {review_history}
Категории интересов: {categories}
Город: {city}
Бюджет: {budget}

Предложи 3-5 рекомендаций с кратким обоснованием. Будь дружелюбным и полезным."""
        
        return await self._call_api(prompt, temperature=0.7, max_tokens=800)
    
    async def test_connection(self) -> bool:
        """Проверяет подключение к Ollama Cloud"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                headers = {}
                if self.api_key:
                    headers['Authorization'] = f'Bearer {self.api_key}'
                
                response = await client.get(
                    f"{self.base_url}/api/tags",
                    headers=headers
                )
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Connection test error: {e}")
            return False


class LLMService:
    """Сервис для работы с LLM"""
    
    def __init__(self):
        self.client = OllamaCloudClient()
        self._connection_tested = False
    
    async def _ensure_connection(self):
        """Проверяет и логирует статус подключения"""
        if not self._connection_tested:
            if not settings.OLLAMA_API_KEY:
                logger.warning("⚠️  OLLAMA_API_KEY не установлен. Работа без авторизации")
            
            is_connected = await self.client.test_connection()
            if is_connected:
                logger.info("✅ Подключение к Ollama Cloud установлено")
            else:
                logger.warning("⚠️  Ollama Cloud не доступен. Проверьте API ключ и интернет-соединение")
            self._connection_tested = True
    
    async def check_review_content(self, text: str) -> dict:
        """Проверка отзыва на содержание"""
        await self._ensure_connection()
        
        try:
            result = await self.client.check_review_content(text)
            return result
        except Exception as e:
            logger.error(f"Error in LLM check: {e}")
            return {
                "is_appropriate": True,
                "reason": f"Ошибка проверки: {str(e)[:50]}",
                "confidence": 0.5,
                "found_issues": []
            }
    
    async def summarize_review(self, text: str, rating: int) -> str:
        """Суммаризация отзыва"""
        await self._ensure_connection()
        
        try:
            summary = await self.client.summarize_review(text, rating)
            if summary and len(summary) > 10:
                return summary
        except Exception as e:
            logger.error(f"Error in LLM summarization: {e}")
        
        # Минимальный fallback
        words = text.split()
        if len(words) > 20:
            return " ".join(words[:20]) + "..."
        return text
    
    async def generate_recommendations(self, user_id: UUID, db: AsyncSession) -> Optional[str]:
        """Генерация персонализированных рекомендаций"""
        await self._ensure_connection()
        
        try:
            # Получаем пользователя и его предпочтения
            user_result = await db.execute(
                select(User).where(User.id == user_id)
            )
            user = user_result.scalar_one_or_none()
            
            if not user:
                return None
            
            # Получаем историю отзывов пользователя
            reviews_result = await db.execute(
                select(Review)
                .where(Review.user_id == user_id)
                .order_by(Review.created_at.desc())
                .limit(5)
            )
            reviews = reviews_result.scalars().all()
            
            review_history = "\n".join([
                f"Рейтинг {r.rating}/5: {r.text[:50]}..."
                for r in reviews
            ]) if reviews else "Нет истории отзывов"
            
            # Генерируем рекомендации
            recommendations = await self.client.generate_recommendations(
                preferences=user.preferences or {},
                review_history=review_history,
                categories=user.preferences.get("categories", []) if user.preferences else [],
                city=user.preferences.get("city", "") if user.preferences else "",
                budget=user.preferences.get("budget", "") if user.preferences else ""
            )
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
            return None