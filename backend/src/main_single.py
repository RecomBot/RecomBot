# backend/src/main_single.py
import sys
import os
import httpx
import json
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime
import re
from datetime import datetime, timedelta
# from ollama import AsyncClient as OllamaAsyncClient
# from ollama import Client as OllamaSyncClient
from ollama import AsyncClient as OllamaCloudClient

# Добавляем путь к src в sys.path для корректных импортов
current_dir = Path(__file__).parent
src_path = str(current_dir)
if src_path not in sys.path:
    sys.path.insert(0, src_path)

# Загружаем .env В САМОМ НАЧАЛЕ
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, APIRouter, Depends, HTTPException, Query, Body, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from sqlalchemy import (
    Column, Integer, String, Text, Float, Boolean, JSON, DateTime,
    ForeignKey, select, insert, update, BigInteger, UniqueConstraint, func
)
from uuid import UUID as UUIDType
import uuid
from sqlalchemy.dialects.postgresql import UUID
import logging

# Импортируем настройки
try:
    from config import settings
except ImportError:
    # Fallback если config.py нет
    class Settings:
        DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@postgres:5432/travel_db")
        OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/api")
        OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen:0.5b")
    
    settings = Settings()

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_CURRENT_TEST_USER_ID = UUIDType('11111111-1111-1111-1111-111111111111')  # По умолчанию обычный пользователь

def get_current_test_user_id() -> UUIDType:
    """Получение ID текущего тестового пользователя"""
    return _CURRENT_TEST_USER_ID

def set_current_test_user_id(user_id: UUIDType):
    """Установка ID текущего тестового пользователя"""
    global _CURRENT_TEST_USER_ID
    _CURRENT_TEST_USER_ID = user_id
    logger.info(f"Установлен текущий пользователь: {user_id}")

# ========== МОДЕЛИ SQLALCHEMY ==========
Base = declarative_base()

class User(Base):
    """Модель пользователя"""
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    telegram_id = Column(BigInteger, unique=True, nullable=True)
    username = Column(String(100), nullable=True)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    role = Column(String(20), default="user")  # user, moderator, admin
    preferences = Column(JSON, default=dict)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Связи - УКАЗЫВАЕМ foreign_keys явно
    reviews = relationship(
        "Review", 
        back_populates="user", 
        cascade="all, delete-orphan",
        foreign_keys="Review.user_id"
    )

class Place(Base):
    """Модель места"""
    __tablename__ = "places"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(50), nullable=False)
    address = Column(Text, nullable=True)
    city = Column(String(100), nullable=True)
    price_level = Column(Integer, default=1)
    tags = Column(JSON, default=list)
    rating = Column(Float, default=0.0)
    working_hours = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    expired_at = Column(DateTime(timezone=True), nullable=True, index=True)
    
    # Модерация мест
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    moderation_status = Column(String(20), default="active")
    moderation_reason = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Связи
    reviews = relationship(
        "Review", 
        back_populates="place", 
        cascade="all, delete-orphan",
        foreign_keys="Review.place_id"
    )

class Review(Base):
    """Модель отзыва пользователя"""
    __tablename__ = "reviews"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    place_id = Column(UUID(as_uuid=True), ForeignKey("places.id", ondelete="CASCADE"), nullable=False)
    
    # Содержимое отзыва
    rating = Column(Integer, nullable=False)  # 1-5
    text = Column(Text, nullable=False)
    
    # LLM анализ
    llm_check = Column(JSON, nullable=True)
    summary = Column(Text, nullable=True)
    sentiment_score = Column(Float, nullable=True)
    
    # Модерация
    moderation_status = Column(String(20), default="pending")
    moderated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    moderated_at = Column(DateTime(timezone=True), nullable=True)
    moderation_notes = Column(Text, nullable=True)
    
    # Взаимодействия
    helpful_count = Column(Integer, default=0)
    reported_count = Column(Integer, default=0)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Связи - УКАЗЫВАЕМ foreign_keys явно
    user = relationship(
        "User", 
        back_populates="reviews",
        foreign_keys=[user_id]
    )
    place = relationship(
        "Place", 
        back_populates="reviews",
        foreign_keys=[place_id]
    )
    
    # Constraints
    # __table_args__ = (
    #     UniqueConstraint('user_id', 'place_id', name='unique_user_place_review'),
    # )

# ========== ПОДКЛЮЧЕНИЕ К БАЗЕ ДАННЫХ ==========
DATABASE_URL = settings.DATABASE_URL
logger.info(f"Using database URL: {DATABASE_URL}")
logger.info(f"Ollama config: {settings.OLLAMA_MODEL} at {settings.OLLAMA_BASE_URL}")

engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_db():
    """Получение сессии базы данных"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

async def update_place_rating(db: AsyncSession, place_id: UUIDType):
    """Обновляет средний рейтинг места на основе всех одобренных отзывов"""
    try:
        # Получаем все одобренные отзывы для места
        result = await db.execute(
            select(Review.rating)
            .where(
                Review.place_id == place_id,
                Review.moderation_status == "approved"
            )
        )
        ratings = result.scalars().all()
        
        # Также получаем количество отзывов для информации
        count_result = await db.execute(
            select(func.count(Review.id))
            .where(
                Review.place_id == place_id,
                Review.moderation_status == "approved"
            )
        )
        review_count = count_result.scalar()
        
        if not ratings:
            # Если отзывов нет - рейтинг 0.0
            avg_rating = 0.0
        else:
            # Рассчитываем средний рейтинг с округлением до 1 знака после запятой
            avg_rating = round(sum(ratings) / len(ratings), 1)
        
        # Обновляем рейтинг места
        await db.execute(
            update(Place)
            .where(Place.id == place_id)
            .values(rating=avg_rating)
        )
        
        logger.info(f"Обновлен рейтинг места {place_id}: {avg_rating} (на основе {review_count} отзывов)")
        return {
            "place_id": place_id,
            "rating": avg_rating,
            "review_count": review_count
        }
        
    except Exception as e:
        logger.error(f"Ошибка обновления рейтинга места {place_id}: {e}")
        raise

# ========== УТИЛИТЫ ДЛЯ ТЕСТИРОВАНИЯ ==========
async def get_or_create_test_user(db: AsyncSession, role: str = "user"):
    """Получение или создание тестового пользователя (совместимость со старым кодом)"""
    return await get_or_create_user_by_role(db, role)

async def get_or_create_user_by_role(db: AsyncSession, role: str = "user"):
    """Получение или создание пользователя с указанной ролью"""
    try:
        # Определяем UUID в зависимости от роли
        role_uuid_map = {
            "user": UUIDType('11111111-1111-1111-1111-111111111111'),
            "moderator": UUIDType('22222222-2222-2222-2222-222222222222'),
            "admin": UUIDType('33333333-3333-3333-3333-333333333333')
        }
        
        user_uuid = role_uuid_map.get(role, role_uuid_map["user"])
        
        # Пробуем найти пользователя
        result = await db.execute(select(User).where(User.id == user_uuid))
        user = result.scalar_one_or_none()
        
        if not user:
            # Создаем нового пользователя с указанной ролью
            if role == "moderator":
                user = User(
                    id=user_uuid,
                    telegram_id=987654321,
                    username=f"test_{role}",
                    first_name=f"Тестовый {role}",
                    last_name="",
                    role=role,
                    preferences={},
                    is_active=True
                )
            elif role == "admin":
                user = User(
                    id=user_uuid,
                    telegram_id=999999999,
                    username=f"test_{role}",
                    first_name=f"Тестовый {role}",
                    last_name="",
                    role=role,
                    preferences={},
                    is_active=True
                )
            else:  # user
                user = User(
                    id=user_uuid,
                    telegram_id=123456789,
                    username="test_user",
                    first_name="Тестовый",
                    last_name="Пользователь",
                    role=role,
                    preferences={"categories": ["cafe", "restaurant"], "city": "Москва"},
                    is_active=True
                )
            
            db.add(user)
            await db.flush()
            await db.refresh(user)
            logger.info(f"Создан тестовый пользователь с ролью {role}: ID={user.id}")
        else:
            # Обновляем роль существующего пользователя
            user.role = role
            await db.flush()
            logger.info(f"Роль пользователя {user.id} обновлена на {role}")
        
        return user
        
    except Exception as e:
        logger.error(f"Ошибка получения/создания пользователя по роли: {e}")
        raise

async def create_test_moderator(db: AsyncSession):
    """Создание тестового модератора"""
    try:
        from uuid import UUID as UUIDType
        moderator_uuid = UUIDType('22222222-2222-2222-2222-222222222222')
        # Пробуем найти модератора
        result = await db.execute(
            select(User).where(User.id == moderator_uuid)
        )
        moderator = result.scalar_one_or_none()
        
        if not moderator:
            # Создаем тестового модератора
            moderator = User(
                id=moderator_uuid,  # Другой ID чтобы не конфликтовать с user
                telegram_id=987654321,
                username="test_moderator",
                first_name="Тестовый",
                last_name="Модератор",
                role="moderator",
                preferences={},
                is_active=True
            )
            db.add(moderator)
            await db.commit()
            await db.refresh(moderator)
            logger.info(f"✅ Создан тестовый модератор ID={moderator.id}")
        
        return moderator
        
    except Exception as e:
        logger.error(f"Ошибка создания модератора: {e}")
        raise

# ========== OLLAMA CLIENT ==========
# ========== OLLAMA CLOUD CLIENT ==========
class OllamaCloudClientWrapper:
    """Клиент для работы с облачной моделью через Ollama.com"""
    
    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None, api_key: Optional[str] = None):
        self.base_url = base_url or settings.OLLAMA_BASE_URL
        self.model = model or settings.OLLAMA_MODEL
        self.api_key = api_key or settings.OLLAMA_API_KEY
        
        # Создаем клиент
        self.client = OllamaCloudClient(
            host=self.base_url,
            headers={'Authorization': f'Bearer {self.api_key}'} if self.api_key else None
        )
        
        logger.info(f"Ollama Cloud client initialized: {self.model}")
    
    async def _call_api(self, prompt: str, temperature: float = 0.1, max_tokens: int = 500) -> Optional[str]:
        """Вызов облачного Ollama API"""
        try:
            response = await self.client.chat(
                model=self.model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                options={
                    "temperature": temperature,
                    "num_predict": max_tokens
                },
                stream=False
            )
            
            return response['message']['content'].strip()
            
        except Exception as e:
            logger.error(f"Error calling Ollama Cloud API: {e}")
            
            # Fallback: пытаемся использовать прямой HTTP запрос
            try:
                return await self._fallback_call(prompt, temperature, max_tokens)
            except:
                return None
    
    async def _fallback_call(self, prompt: str, temperature: float = 0.1, max_tokens: int = 500) -> Optional[str]:
        """Fallback HTTP запрос если библиотека не работает"""
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                headers = {}
                if self.api_key:
                    headers['Authorization'] = f'Bearer {self.api_key}'
                
                data = {
                    "model": self.model,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens
                    }
                }
                
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
            logger.error(f"Fallback call error: {e}")
            return None
    
    async def check_review_content(self, text: str) -> Dict[str, Any]:
        """Проверка отзыва на содержание"""
        prompt = f"""Ты - строгий модератор русскоязычных отзывов о заведениях. 
        Твоя задача - выявлять ВСЕ нарушения, включая:
        1. Нецензурную лексику, мат, обсценную лексику
        2. Оскорбления в любой форме (прямые, косвенные, сленговые)
        3. Угрозы, агрессию
        4. Спам, рекламу, флуд
        5. Неуважительные высказывания о персонале
        
        ВАЖНО: В русском языке есть много завуалированных оскорблений. Будь внимателен!
        
        Отзыв для анализа: "{text}"
        
        ВЕРНИ ТОЛЬКО JSON БЕЗ ЛИШНИХ СЛОВ:
        {{
            "is_appropriate": true/false,
            "reason": "конкретная причина на русском",
            "confidence": число от 0.0 до 1.0,
            "found_issues": ["список найденных проблем"] или [],
            "suggested_action": "approve" или "reject"
        }}
        
        Примеры оскорбительных фраз которые нужно отклонять:
        - "конченый", "дебил" и другие
        - Любые производные от матерных слов
        - "администратор идиот", "официантка тупая"
        """
        
        response = await self._call_api(prompt, temperature=0.1, max_tokens=300)
        
        if not response:
            return self._create_fallback_response("Ollama Cloud не ответил")
        
        # Извлекаем JSON из ответа
        import re
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
        
        # Модель сказала что не подходит?
        if any(word in response_lower for word in ["не подходит", "не одобряю", "отклонить", "нецензурн", "оскорблен"]):
            return {
                "is_appropriate": False,
                "reason": "Модель рекомендует отклонить",
                "confidence": 0.7,
                "found_issues": ["определено_моделью"]
            }
        
        # Модель сказала что подходит?
        if any(word in response_lower for word in ["подходит", "одобряю", "принять", "хороший"]):
            return {
                "is_appropriate": True,
                "reason": "Модель рекомендует принять",
                "confidence": 0.7,
                "found_issues": []
            }
        
        # Не поняли ответ модели
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
            # Очищаем ответ от возможных кавычек и пояснений
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
            # Пробуем получить список моделей
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
    
    async def get_available_models(self) -> list:
        """Получает список доступных моделей"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                headers = {}
                if self.api_key:
                    headers['Authorization'] = f'Bearer {self.api_key}'
                
                response = await client.get(
                    f"{self.base_url}/api/tags",
                    headers=headers
                )
                if response.status_code == 200:
                    models = response.json().get("models", [])
                    return [model.get("name") for model in models if model.get("name")]
                return []
        except Exception as e:
            logger.error(f"Error getting available models: {e}")
            return []

# ========== LLM СЕРВИС ==========
class LLMService:
    """Сервис для работы с локальной моделью Ollama"""
    
    def __init__(self):
        self.client = OllamaCloudClientWrapper()
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
        
    async def analyze_search_query(self, query: str, db: AsyncSession) -> Dict[str, Any]:
        """Анализирует поисковый запрос и определяет критерии поиска"""
        try:
            # Получаем все категории из базы данных
            categories_result = await db.execute(
                select(Place.category).distinct().where(Place.is_active == True)
            )
            available_categories = [c[0] for c in categories_result.all()]
            
            # Получаем все города из базы данных
            cities_result = await db.execute(
                select(Place.city).distinct().where(Place.is_active == True)
            )
            available_cities = [c[0] for c in cities_result.all() if c[0]]
            
            # Получаем популярные теги
            places_result = await db.execute(
                select(Place.tags).where(Place.is_active == True).limit(50)
            )
            all_tags = []
            for tags in places_result.scalars().all():
                if tags:
                    all_tags.extend(tags)
            
            popular_tags = list(set(all_tags))[:20]  # Топ 20 тегов
            
            prompt = f"""Ты - умный помощник для поиска мест отдыха и развлечений.

    ПОЛЬЗОВАТЕЛЬ ИЩЕТ: "{query}"

    ТВОЯ ЗАДАЧА:
    1. Определи КАТЕГОРИЮ (выбери одну из доступных)
    2. Определи ГОРОД (если указан)
    3. Извлеки КЛЮЧЕВЫЕ СЛОВА для поиска
    4. Определи ПРИОРИТЕТ сортировки

    ДОСТУПНЫЕ КАТЕГОРИИ: {available_categories}
    ДОСТУПНЫЕ ГОРОДА: {available_cities}
    ПОПУЛЯРНЫЕ ТЕГИ: {popular_tags}

    ПРАВИЛА:
    - Если город не указан, используй "Москва" по умолчанию
    - Если категория не ясна, выбери наиболее подходящую
    - Ключевые слова должны быть релевантны запросу

    ПРИМЕРЫ:
    Запрос: "хочу в уютное кафе с Wi-Fi"
    Ответ: {{"category": "cafe", "city": "Москва", "keywords": ["уютное", "wi-fi", "кофе", "интернет"], "sort_by": "rating"}}

    Запрос: "романтический ресторан с видом на Москву"
    Ответ: {{"category": "restaurant", "city": "Москва", "keywords": ["романтический", "вид", "панорамный", "ужин"], "sort_by": "rating"}}

    Запрос: "где погулять в парке сегодня"
    Ответ: {{"category": "park", "city": "Москва", "keywords": ["прогулка", "природа", "отдых", "зелень"], "sort_by": "reviews"}}

    Запрос: "интересный музей для детей"
    Ответ: {{"category": "museum", "city": "Москва", "keywords": ["интересный", "дети", "семейный", "образовательный"], "sort_by": "rating"}}

    ВЕРНИ ТОЛЬКО JSON:
    {{
        "category": "название категории или null",
        "city": "город или null",
        "keywords": ["список", "ключевых", "слов"],
        "sort_by": "rating|reviews|random",
        "reasoning": "краткое объяснение почему выбраны такие параметры"
    }}"""
            
            response = await self.client._call_api(prompt, temperature=0.1, max_tokens=500)
            
            if not response:
                return {"category": None, "city": "Москва", "keywords": [], "sort_by": "rating", "reasoning": "LLM не ответил"}
            
            # Извлекаем JSON из ответа
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                try:
                    result = json.loads(json_match.group())
                    return result
                except json.JSONDecodeError:
                    pass
            
            # Если не удалось распарсить JSON
            return {"category": None, "city": "Москва", "keywords": [], "sort_by": "rating", "reasoning": "Не удалось распарсить ответ LLM"}
            
        except Exception as e:
            logger.error(f"Ошибка анализа запроса: {e}")
            return {"category": None, "city": "Москва", "keywords": [], "sort_by": "rating", "reasoning": f"Ошибка: {str(e)}"}

# ========== МОДЕЛИ PYDANTIC ==========
class PlaceCreate(BaseModel):
    """Модель для создания места"""
    name: str
    description: Optional[str] = None
    category: str
    address: Optional[str] = None
    city: Optional[str] = None
    price_level: int = 1
    tags: List[str] = []
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "Кофейня Уютная",
                "description": "Маленькая уютная кофейня",
                "category": "cafe",
                "address": "ул. Центральная, 15",
                "city": "Москва",
                "price_level": 2,
                "tags": ["кофе", "десерты", "wi-fi"]
            }
        }

class PlaceResponse(BaseModel):
    """Модель для ответа с местом"""
    id: UUIDType
    name: str
    description: Optional[str] = None
    category: str
    address: Optional[str] = None
    city: Optional[str] = None
    price_level: int = 1
    tags: List[str] = []
    rating: float = 0.0
    review_count: Optional[int] = None
    
    class Config:
        from_attributes = True

class ReviewCreate(BaseModel):
    """Модель для создания отзыва"""
    place_id: UUIDType
    rating: int = Field(..., ge=1, le=5)
    text: str = Field(..., min_length=10, max_length=2000)
    
    class Config:
        json_schema_extra = {
            "example": {
                "place_id": 1,
                "rating": 5,
                "text": "Отличное место! Очень вкусный кофе."
            }
        }

class ReviewResponse(BaseModel):
    """Модель для ответа с отзывом"""
    id: UUIDType
    user_id: UUIDType
    place_id: UUIDType
    rating: int
    text: str
    summary: Optional[str] = None
    moderation_status: str
    moderation_reason: Optional[str] = None
    llm_check: Optional[Dict[str, Any]] = None
    created_at: str
    helpful_count: int = 0
    action: Optional[str] = None
    place_rating_updated: Optional[bool] = None
    
    class Config:
        from_attributes = True

class ReviewModeration(BaseModel):
    """Модель для модерации отзыва"""
    status: str = Field(..., pattern="^(approved|rejected)$")
    notes: Optional[str] = None

class RecommendationRequest(BaseModel):
    """Модель для запроса рекомендаций"""
    categories: Optional[List[str]] = None
    city: Optional[str] = None
    budget: Optional[str] = None

# ========== СОЗДАНИЕ ПРИЛОЖЕНИЯ ==========
app = FastAPI(
    title="Travel Recommendation API",
    description="API для системы рекомендаций мест отдыха с локальной LLM (Ollama)",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========== РОУТЕРЫ ==========
auth_router = APIRouter()
places_router = APIRouter()
reviews_router = APIRouter()
recommendations_router = APIRouter()
moderation_router = APIRouter()
parser_router = APIRouter()

# ========== ЗАВИСИМОСТИ ДЛЯ ПРОВЕРКИ РОЛЕЙ ==========
async def get_current_user(
    telegram_id: int = Query(..., description="Telegram ID пользователя"),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Получение текущего пользователя"""
    try:
        # Ищем пользователя по telegram_id
        result = await db.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            # Если пользователь не найден, создаем его
            # (в реальном приложении нужно получать данные из запроса)
            logger.info(f"Пользователь с telegram_id={telegram_id} не найден, создаем...")
            
            # Для тестирования создаем минимального пользователя
            # В реальном приложении данные должны приходить из запроса
            new_user = User(
                telegram_id=telegram_id,
                username=f"user_{telegram_id}",
                first_name=f"User_{telegram_id}",
                role="user",
                preferences={},
                is_active=True
            )
            
            db.add(new_user)
            await db.commit()
            await db.refresh(new_user)
            user = new_user
            logger.info(f"Создан пользователь: telegram_id={telegram_id}, id={user.id}")
        
        if not user.is_active:
            raise HTTPException(status_code=403, detail="Пользователь заблокирован")
        
        # Устанавливаем текущего пользователя для совместимости со старым кодом
        set_current_test_user_id(user.id)
        
        return user
        
    except Exception as e:
        logger.error(f"Ошибка получения пользователя telegram_id={telegram_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def require_role(allowed_roles: List[str]):
    """Декоратор для проверки ролей"""
    def role_checker(current_user: User = Depends(get_current_user)):
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=f"Доступ запрещен. Требуемые роли: {', '.join(allowed_roles)}"
            )
        return current_user
    return role_checker

# Сокращения для удобства
require_moderator = require_role(["moderator", "admin"])
require_admin = require_role(["admin"])
require_any = require_role(["user", "moderator", "admin"])  # Все авторизованные

# ========== АУТЕНТИФИКАЦИЯ (УПРОЩЕННАЯ) ==========
class TelegramUserCreate(BaseModel):
    """Модель для создания пользователя из Telegram"""
    telegram_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: str = "user"

@auth_router.post("/create-telegram-user")
async def create_telegram_user(
    user_data: TelegramUserCreate,
    db: AsyncSession = Depends(get_db)
):
    """Создание/получение пользователя из Telegram"""
    try:
        # Проверяем, существует ли пользователь
        result = await db.execute(
            select(User).where(User.telegram_id == user_data.telegram_id)
        )
        existing_user = result.scalar_one_or_none()
        
        if existing_user:
            # Обновляем существующего пользователя (если информация изменилась)
            updated = False
            
            if user_data.username and existing_user.username != user_data.username:
                existing_user.username = user_data.username
                updated = True
                
            if user_data.first_name and existing_user.first_name != user_data.first_name:
                existing_user.first_name = user_data.first_name
                updated = True
                
            if user_data.last_name and existing_user.last_name != user_data.last_name:
                existing_user.last_name = user_data.last_name
                updated = True
                
            if updated:
                existing_user.updated_at = func.now()
                await db.commit()
                await db.refresh(existing_user)
                action = "updated"
            else:
                action = "exists"
            
            logger.info(f"Пользователь {user_data.telegram_id} уже существует")
        else:
            # Создаем нового пользователя
            new_user = User(
                telegram_id=user_data.telegram_id,
                username=user_data.username,
                first_name=user_data.first_name,
                last_name=user_data.last_name,
                role=user_data.role,
                preferences={},
                is_active=True
            )
            
            db.add(new_user)
            await db.commit()
            await db.refresh(new_user)
            
            existing_user = new_user
            action = "created"
            logger.info(f"Создан новый пользователь: {user_data.telegram_id}")
        
        # Формируем ответ
        return {
            "id": existing_user.id,
            "telegram_id": existing_user.telegram_id,
            "username": existing_user.username,
            "first_name": existing_user.first_name,
            "last_name": existing_user.last_name,
            "role": existing_user.role,
            "is_active": existing_user.is_active,
            "action": action,
            "permissions": {
                "can_view_places": True,
                "can_create_reviews": True,
                "can_get_recommendations": True,
                "can_moderate": existing_user.role in ["moderator", "admin"]
            }
        }
            
    except Exception as e:
        logger.error(f"Ошибка создания пользователя {user_data.telegram_id}: {e}")
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@auth_router.get("/telegram-user/{telegram_id}")
async def get_telegram_user(
    telegram_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Получение пользователя по telegram_id"""
    try:
        result = await db.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        return {
            "id": user.id,
            "telegram_id": user.telegram_id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "role": user.role,
            "is_active": user.is_active,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "permissions": {
                "can_view_places": True,
                "can_create_reviews": True,
                "can_get_recommendations": True,
                "can_moderate": user.role in ["moderator", "admin"]
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения пользователя {telegram_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
@auth_router.get("/test-user")
async def get_test_user_info(
    db: AsyncSession = Depends(get_db)
):
    """Получение информации о тестовом пользователе"""
    user = await get_or_create_test_user(db)
    return {
        "id": user.id,
        "telegram_id": user.telegram_id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "role": user.role,
        "preferences": user.preferences
    }

@auth_router.get("/current")
async def get_current_user_info(
    db: AsyncSession = Depends(get_db)
):
    """Получение информации о текущем пользователе"""
    current_user_id = get_current_test_user_id()
    
    result = await db.execute(select(User).where(User.id == current_user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="Текущий пользователь не найден")
    
    return {
        "id": user.id,
        "telegram_id": user.telegram_id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "role": user.role,
        "preferences": user.preferences,
        "is_active": user.is_active,
        "note": "Это текущий пользователь для всех запросов"
    }
    
@auth_router.post("/switch-role/{role}")
async def switch_role(
    role: str,
    db: AsyncSession = Depends(get_db)
):
    """Переключение роли тестового пользователя (для тестирования)"""
    allowed_roles = ["user", "moderator", "admin"]
    
    if role not in allowed_roles:
        raise HTTPException(status_code=400, detail=f"Роль должна быть одна из: {allowed_roles}")
    
    # Получаем или создаем пользователя с указанной ролью
    user = await get_or_create_user_by_role(db, role)
    
    # Устанавливаем его как текущего пользователя
    set_current_test_user_id(user.id)
    
    await db.commit()
    
    return {
        "success": True,
        "message": f"Переключен на пользователя с ролью {role}",
        "user_id": user.id,
        "username": user.username,
        "new_role": role,
        "note": f"Теперь все запросы будут выполняться от пользователя {user.username}"
    }

@auth_router.get("/permissions")
async def get_permissions(
    current_user: User = Depends(get_current_user)
):
    """Получение списка доступных действий для текущего пользователя"""
    permissions = {
        "can_view_places": True,
        "can_view_place_details": True,
        "can_create_reviews": True,
        "can_view_own_reviews": True,
        "can_get_recommendations": True,
        "can_create_places": current_user.role in ["moderator", "admin"],
        "can_delete_reviews": current_user.role in ["moderator", "admin"],
        "can_moderate_reviews": current_user.role in ["moderator", "admin"],
        "can_view_moderation": current_user.role in ["moderator", "admin"],
        "can_manage_users": current_user.role == "admin",  # для будущего
    }
    
    return {
        "user": {
            "id": current_user.id,
            "username": current_user.username,
            "role": current_user.role
        },
        "permissions": permissions
    }

# ========== МЕСТА ==========
@places_router.get("/")
async def get_places(
    category: Optional[str] = None,
    city: Optional[str] = None,
    min_rating: Optional[float] = Query(None, ge=0.0, le=5.0),
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """Получение списка мест"""
    try:
        query = select(Place).where(Place.is_active == True)
        
        if category:
            query = query.where(Place.category == category)
        if city:
            query = query.where(Place.city == city)
        if min_rating is not None:
            query = query.where(Place.rating >= min_rating)
        
        query = query.offset(offset).limit(limit)
        result = await db.execute(query)
        places = result.scalars().all()
        
        places_response = []
        for p in places:
            # Получаем количество отзывов для каждого места
            count_result = await db.execute(
                select(func.count(Review.id))
                .where(
                    Review.place_id == p.id,
                    Review.moderation_status == "approved"
                )
            )
            review_count = count_result.scalar()
            
            places_response.append({
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "category": p.category,
                "address": p.address,
                "city": p.city,
                "price_level": p.price_level,
                "tags": p.tags,
                "rating": p.rating,
                "review_count": review_count  # ДОБАВЛЕНО
            })
        
        return {
            "places": places_response,
            "total": len(places)
        }
        
    except Exception as e:
        logger.error(f"Ошибка получения мест: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@places_router.get("/{place_id}", response_model=PlaceResponse)
async def get_place(
    place_id: UUIDType, 
    db: AsyncSession = Depends(get_db)
):
    """Получение конкретного места"""
    try:
        result = await db.execute(
            select(Place).where(Place.id == place_id, Place.is_active == True)
        )
        place = result.scalar_one_or_none()
        
        if not place:
            raise HTTPException(status_code=404, detail="Место не найдено")
        
        # Получаем количество отзывов
        count_result = await db.execute(
            select(func.count(Review.id))
            .where(
                Review.place_id == place_id,
                Review.moderation_status == "approved"
            )
        )
        review_count = count_result.scalar()
        
        # Создаем response с дополнительными полями
        response = PlaceResponse.from_orm(place)
        response_dict = response.dict()
        response_dict["review_count"] = review_count
        
        return response_dict
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения места: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@places_router.get("/{place_id}/stats")
async def get_place_stats(
    place_id: UUIDType,
    db: AsyncSession = Depends(get_db)
):
    """Получение статистики по месту"""
    try:
        # Проверяем существует ли место
        place_result = await db.execute(
            select(Place).where(Place.id == place_id, Place.is_active == True)
        )
        place = place_result.scalar_one_or_none()
        
        if not place:
            raise HTTPException(status_code=404, detail="Место не найдено")
        
        # Получаем распределение рейтингов
        rating_distribution = await db.execute(
            select(Review.rating, func.count(Review.id))
            .where(
                Review.place_id == place_id,
                Review.moderation_status == "approved"
            )
            .group_by(Review.rating)
            .order_by(Review.rating)
        )
        
        distribution = {str(rating): count for rating, count in rating_distribution}
        
        # Получаем общее количество отзывов
        count_result = await db.execute(
            select(func.count(Review.id))
            .where(
                Review.place_id == place_id,
                Review.moderation_status == "approved"
            )
        )
        total_reviews = count_result.scalar()
        
        # Получаем последние отзывы
        recent_reviews_result = await db.execute(
            select(Review)
            .where(
                Review.place_id == place_id,
                Review.moderation_status == "approved"
            )
            .order_by(Review.created_at.desc())
            .limit(5)
        )
        recent_reviews = recent_reviews_result.scalars().all()
        
        return {
            "place_id": place_id,
            "name": place.name,
            "current_rating": place.rating,
            "total_reviews": total_reviews,
            "rating_distribution": distribution,
            "recent_reviews": [
                {
                    "id": r.id,
                    "rating": r.rating,
                    "summary": r.summary,
                    "created_at": r.created_at.isoformat()
                }
                for r in recent_reviews
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения статистики места: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
@places_router.post("/", response_model=PlaceResponse, status_code=201)
async def create_place(
    place_data: PlaceCreate,
    current_user: User = Depends(require_moderator),
    db: AsyncSession = Depends(get_db)
):
    """Создание нового места (только для модераторов и администраторов)"""
    try:
        new_place = Place(
            name=place_data.name,
            description=place_data.description,
            category=place_data.category,
            address=place_data.address,
            city=place_data.city,
            price_level=place_data.price_level,
            tags=place_data.tags,
            is_active=True,
            created_by=current_user.id
        )
        
        db.add(new_place)
        await db.flush()
        await db.refresh(new_place)
        
        logger.info(f"Создано место: {new_place.id} - {new_place.name} (создал: {current_user.username})")
        return PlaceResponse.from_orm(new_place)
        
    except Exception as e:
        await db.rollback()
        logger.error(f"Ошибка создания места: {e}")
        raise HTTPException(status_code=400, detail=str(e))

# ========== ОТЗЫВЫ ==========
@reviews_router.post("/", response_model=ReviewResponse, status_code=201)
async def create_review(
    review_data: ReviewCreate,
    telegram_id: int = Query(..., description="Telegram ID пользователя"),
    db: AsyncSession = Depends(get_db)
):
    """Создание отзыва с LLM проверкой"""
    try:
        # Получаем пользователя по Telegram ID
        result = await db.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        current_user = result.scalar_one_or_none()
        
        if not current_user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        # Проверяем место
        place_result = await db.execute(
            select(Place).where(Place.id == review_data.place_id, Place.is_active == True)
        )
        place = place_result.scalar_one_or_none()
        
        if not place:
            raise HTTPException(status_code=404, detail="Место не найдено")
        
        # Проверяем, есть ли активный отзыв
        result = await db.execute(
            select(Review).where(
                Review.user_id == current_user.id,
                Review.place_id == review_data.place_id,
                Review.moderation_status.in_(["approved", "pending", "flagged_by_llm"])
            )
        )
        existing_review = result.scalar_one_or_none()

        if existing_review:
            latest_review = await get_latest_user_review(db, current_user.id, review_data.place_id)
            
            if latest_review and latest_review.moderation_status == "rejected":
                raise HTTPException(
                    status_code=400, 
                    detail=f"Ваш предыдущий отзыв был отклонен. Причина: {latest_review.moderation_notes or 'нарушение правил'}"
                )
            else:
                raise HTTPException(
                    status_code=400, 
                    detail="У вас уже есть активный отзыв на это место"
                )
        
        # LLM проверка (Ollama)
        llm_service = LLMService()
        llm_check = await llm_service.check_review_content(review_data.text)
        summary = await llm_service.summarize_review(review_data.text, review_data.rating)
        
        # Определяем статус модерации на основе LLM проверки
        if llm_check.get("is_appropriate", True):
            moderation_status = "approved"
            should_update_rating = True
        else:
            moderation_status = "flagged_by_llm"
            should_update_rating = False
        
        # Определяем sentiment_score из llm_check
        sentiment_score = llm_check.get("confidence", 0.5)
        if not llm_check.get("is_appropriate", True):
            sentiment_score = 0.0  # Негативный отзыв

        new_review = Review(
            user_id=current_user.id,
            place_id=review_data.place_id,
            rating=review_data.rating,
            text=review_data.text,
            llm_check=llm_check,
            summary=summary,
            sentiment_score=sentiment_score,
            moderation_status=moderation_status
        )
        
        db.add(new_review)
        await db.flush()
        await db.refresh(new_review)

        if should_update_rating:
            rating_update_result = await update_place_rating(db, review_data.place_id)
            logger.info(f"Отзыв {new_review.id} автоматически одобрен, рейтинг места обновлен")
        else:
            logger.info(f"Отзыв {new_review.id} отправлен на модерацию, рейтинг не изменен")

        logger.info(f"Создан отзыв {new_review.id} пользователем {current_user.username}, статус: {moderation_status}")
        return {
            "id": new_review.id,
            "user_id": new_review.user_id,
            "place_id": new_review.place_id,
            "rating": new_review.rating,
            "text": new_review.text,
            "summary": new_review.summary,
            "moderation_status": new_review.moderation_status,
            "moderation_reason": llm_check.get("reason") if not llm_check.get("is_appropriate", True) else None,
            "llm_check": llm_check,
            "created_at": new_review.created_at.isoformat() if new_review.created_at else None,
            "helpful_count": new_review.helpful_count,
            "action": "created",
            "place_rating_updated": should_update_rating
        }
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Ошибка создания отзыва: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def has_active_review(db: AsyncSession, user_id: UUIDType, place_id: UUIDType) -> bool:
    """Проверяет, есть ли у пользователя активный отзыв на место"""
    result = await db.execute(
        select(Review).where(
            Review.user_id == user_id,
            Review.place_id == place_id,
            Review.moderation_status.in_(["approved", "pending"])
        )
    )
    return result.scalar_one_or_none() is not None

async def get_latest_user_review(db: AsyncSession, user_id: UUIDType, place_id: UUIDType) -> Optional[Review]:
    """Получает последний отзыв пользователя на место"""
    result = await db.execute(
        select(Review).where(
            Review.user_id == user_id,
            Review.place_id == place_id
        ).order_by(Review.created_at.desc()).limit(1)
    )
    return result.scalar_one_or_none()

@reviews_router.get("/", response_model=List[ReviewResponse])
async def get_reviews(
    place_id: Optional[UUIDType] = Query(None),
    only_approved: bool = Query(True),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """Получение отзывов"""
    try:
        query = select(Review)
        
        if place_id:
            query = query.where(Review.place_id == place_id)
        if only_approved:
            query = query.where(Review.moderation_status == "approved")
        
        query = query.order_by(Review.created_at.desc()).limit(limit)
        result = await db.execute(query)
        reviews = result.scalars().all()
        
        return [
            ReviewResponse(
                id=r.id,
                user_id=r.user_id,
                place_id=r.place_id,
                rating=r.rating,
                text=r.text,
                summary=r.summary,
                moderation_status=r.moderation_status,
                created_at=r.created_at.isoformat(),
                helpful_count=r.helpful_count
            )
            for r in reviews
        ]
        
    except Exception as e:
        logger.error(f"Ошибка получения отзывов: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@reviews_router.get("/user/{user_id}/place/{place_id}")
async def get_user_review_for_place(
    user_id: UUIDType,
    place_id: UUIDType,
    db: AsyncSession = Depends(get_db)
):
    """Получение всех отзывов пользователя на конкретное место"""
    try:
        result = await db.execute(
            select(Review)
            .where(
                Review.user_id == user_id,
                Review.place_id == place_id
            )
            .order_by(Review.created_at.desc())
        )
        
        reviews = result.scalars().all()
        
        return {
            "user_id": user_id,
            "place_id": place_id,
            "reviews": [
                {
                    "id": r.id,
                    "rating": r.rating,
                    "text": r.text[:100] + "..." if len(r.text) > 100 else r.text,
                    "moderation_status": r.moderation_status,
                    "moderation_notes": r.moderation_notes,
                    "created_at": r.created_at.isoformat(),
                    "summary": r.summary
                }
                for r in reviews
            ],
            "total": len(reviews),
            "has_active_review": any(r.moderation_status in ["approved", "pending"] for r in reviews)
        }
        
    except Exception as e:
        logger.error(f"Ошибка получения отзывов пользователя: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# В main_single.py в reviews_router добавить:

class UserReviewResponse(BaseModel):
    """Модель для ответа с отзывом пользователя"""
    id: UUIDType
    place_id: UUIDType
    place_name: str
    rating: int
    text: str
    summary: Optional[str] = None
    moderation_status: str
    moderation_reason: Optional[str] = None
    created_at: str
    helpful_count: int = 0
    can_edit: bool = Field(default=False, description="Можно ли редактировать отзыв")
    can_delete: bool = Field(default=True, description="Можно ли удалить отзыв")

@reviews_router.get("/user/{telegram_id}/reviews")
async def get_user_reviews(
    telegram_id: int,
    status: Optional[str] = Query(None, description="Фильтр по статусу (approved, pending, rejected, flagged_by_llm)"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """Получение отзывов пользователя по telegram_id"""
    try:
        # Получаем пользователя по telegram_id
        user_result = await db.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = user_result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        # Строим базовый запрос
        query = select(Review).where(Review.user_id == user.id)
        
        # Фильтруем по статусу если указан
        if status:
            query = query.where(Review.moderation_status == status)
        
        # Получаем общее количество для пагинации
        count_query = select(func.count(Review.id)).where(Review.user_id == user.id)
        if status:
            count_query = count_query.where(Review.moderation_status == status)
        
        count_result = await db.execute(count_query)
        total_count = count_result.scalar() or 0
        
        # Получаем отзывы с пагинацией
        query = query.order_by(Review.created_at.desc()).offset(offset).limit(limit)
        result = await db.execute(query)
        reviews = result.scalars().all()
        
        # Собираем ответ с информацией о местах
        user_reviews = []
        for review in reviews:
            # Получаем информацию о месте
            place_result = await db.execute(
                select(Place.name).where(Place.id == review.place_id)
            )
            place_name = place_result.scalar_one_or_none() or "Неизвестное место"
            
            # Определяем можно ли редактировать/удалять отзыв
            can_edit = review.moderation_status in ["pending", "flagged_by_llm"]
            can_delete = True  # Можно удалить всегда
            
            user_reviews.append({
                "id": review.id,
                "place_id": review.place_id,
                "place_name": place_name,
                "rating": review.rating,
                "text": review.text,
                "summary": review.summary,
                "moderation_status": review.moderation_status,
                "moderation_reason": review.moderation_notes,
                "created_at": review.created_at.isoformat() if review.created_at else None,
                "helpful_count": review.helpful_count,
                "can_edit": can_edit,
                "can_delete": can_delete
            })
        
        return {
            "reviews": user_reviews,
            "total": total_count,
            "limit": limit,
            "offset": offset,
            "has_more": (offset + len(reviews)) < total_count
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения отзывов пользователя {telegram_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@reviews_router.delete("/{review_id}")
async def delete_user_review(
    review_id: UUIDType,
    telegram_id: int = Query(..., description="Telegram ID пользователя"),
    db: AsyncSession = Depends(get_db)
):
    """Удаление отзыва пользователя"""
    try:
        # Получаем пользователя
        user_result = await db.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = user_result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        # Получаем отзыв
        review_result = await db.execute(
            select(Review).where(
                Review.id == review_id,
                Review.user_id == user.id
            )
        )
        review = review_result.scalar_one_or_none()
        
        if not review:
            raise HTTPException(status_code=404, detail="Отзыв не найден")
        
        # Сохраняем place_id для обновления рейтинга
        place_id = review.place_id
        
        # Удаляем отзыв
        await db.delete(review)
        await db.flush()
        
        # Обновляем рейтинг места
        await update_place_rating(db, place_id)
        
        await db.commit()
        
        return {
            "success": True,
            "message": "Отзыв удален",
            "review_id": str(review_id),
            "place_id": str(place_id)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Ошибка удаления отзыва {review_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class ModerationNotification(BaseModel):
    """Модель для уведомления о модерации"""
    review_id: UUIDType
    telegram_id: int
    new_status: str
    reason: Optional[str] = None

@reviews_router.post("/notify-moderation")
async def notify_moderation_result(
    notification: ModerationNotification,
    db: AsyncSession = Depends(get_db)
):
    """Получение уведомления от бекенда о результате модерации"""
    # Здесь будет логика отправки уведомления в телеграм
    # Пока просто логируем
    logger.info(f"Уведомление о модерации: review_id={notification.review_id}, "
                f"telegram_id={notification.telegram_id}, status={notification.new_status}")
    
    # В будущем здесь будет вызов API телеграм бота
    return {"status": "notification_received"}

# ========== МОДЕРАЦИЯ ==========
@moderation_router.get("/pending-reviews")
async def get_pending_reviews(
    current_user: User = Depends(require_moderator),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """Отзывы на модерацию"""
    try:
        result = await db.execute(
            select(Review)
            .where(Review.moderation_status.in_(["pending", "flagged_by_llm"]))
            .order_by(Review.created_at.asc())
            .limit(limit)
        )
        
        reviews = result.scalars().all()
        reviews_with_details = []
        
        for review in reviews:
            reviews_with_details.append({
                "id": review.id,
                "user_id": review.user_id,
                "place_id": review.place_id,
                "rating": review.rating,
                "text": review.text,
                "summary": review.summary,
                "llm_check": review.llm_check,
                "moderation_status": review.moderation_status,
                "created_at": review.created_at.isoformat()
            })
        
        return {"reviews": reviews_with_details, "total": len(reviews_with_details)}
        
    except Exception as e:
        logger.error(f"Ошибка получения отзывов на модерацию: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@moderation_router.post("/reviews/{review_id}/approve")
async def approve_review(
    review_id: UUIDType,
    telegram_id: int = Query(..., description="Telegram ID модератора"),
    db: AsyncSession = Depends(get_db)
):
    """Одобрение отзыва"""
    try:
        # Получаем модератора по Telegram ID
        moderator_result = await db.execute(
            select(User).where(
                User.telegram_id == telegram_id,
                User.role.in_(["moderator", "admin"])
            )
        )
        current_user = moderator_result.scalar_one_or_none()
        
        if not current_user:
            raise HTTPException(status_code=403, detail="Доступ запрещен. Требуется роль модератора или администратора")
        
        # Проверяем что пользователь - модератор или админ
        user_result = await db.execute(
            select(User).where(
                User.id == current_user.id,
                User.role.in_(["moderator", "admin"])
            )
        )
        user = user_result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(status_code=403, detail="Только модераторы и администраторы могут одобрять отзывы")
        
        result = await db.execute(
            select(Review).where(Review.id == review_id)
        )
        review = result.scalar_one_or_none()
        
        if not review:
            raise HTTPException(status_code=404, detail="Отзыв не найден")
        
        review.moderation_status = "approved"
        review.moderated_by = current_user.id
        review.moderated_at = func.now()
        
        await update_place_rating(db, review.place_id)
        await db.commit()

        user_result = await db.execute(
            select(User).where(User.id == review.user_id)
        )
        user = user_result.scalar_one_or_none()
        
        if user and user.telegram_id:
            logger.info(f"Отзыв {review_id} одобрен. Нужно уведомить пользователя {user.telegram_id}")
            # Здесь будет вызов к боту
            
        return {"success": True, "message": "Отзыв одобрен", "moderator_id": current_user.id}
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Ошибка одобрения отзыва: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@moderation_router.post("/reviews/{review_id}/reject")
async def reject_review(
    review_id: UUIDType,
    moderation_data: ReviewModeration,
    db: AsyncSession = Depends(get_db)
):
    """Отклонение отзыва"""
    try:
        result = await db.execute(
            select(Review).where(Review.id == review_id)
        )
        review = result.scalar_one_or_none()
        
        if not review:
            raise HTTPException(status_code=404, detail="Отзыв не найден")
        
        # Получаем текущий статус отзыва
        old_status = review.moderation_status

        review.moderation_status = "rejected"
        review.moderated_by = 1  # ID тестового пользователя
        review.moderated_at = func.now()
        review.moderation_notes = moderation_data.notes
        
        # ОБНОВЛЯЕМ РЕЙТИНГ МЕСТА ЕСЛИ ОТЗЫВ БЫЛ ОДОБРЕН РАНЬШЕ
        if old_status == "approved":
            await update_place_rating(db, review.place_id)
            logger.info(f"Отзыв {review_id} отклонен (был одобрен), рейтинг места обновлен")
        else:
            logger.info(f"Отзыв {review_id} отклонен (был в статусе {old_status})")

        await db.commit()

        # TODO: Отправить уведомление пользователю через бота
        # Нужно получить telegram_id пользователя
        user_result = await db.execute(
            select(User).where(User.id == review.user_id)
        )
        user = user_result.scalar_one_or_none()
        
        if user and user.telegram_id:
            logger.info(f"Отзыв {review_id} отклонен. Нужно уведомить пользователя {user.telegram_id}")
            # Здесь будет вызов к боту

        return {
            "success": True, 
            "message": "Отзыв отклонен",
            "old_status": old_status,
            "place_rating_updated": old_status == "approved"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Ошибка отклонения отзыва: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ========== РЕКОМЕНДАЦИИ ==========
@recommendations_router.get("/")
async def get_recommendations(
    category: Optional[str] = None,
    city: Optional[str] = None,
    limit: int = 10,
    db: AsyncSession = Depends(get_db)
):
    """Базовые рекомендации по категориям"""
    try:
        query = select(Place).where(Place.is_active == True)
        
        if category:
            query = query.where(Place.category == category)
        if city:
            query = query.where(Place.city == city)
        
        query = query.order_by(func.random()).limit(limit)
        result = await db.execute(query)
        places = result.scalars().all()
        
        return {
            "recommendations": [
                {
                    "id": p.id,
                    "name": p.name,
                    "category": p.category,
                    "city": p.city,
                    "description": p.description,
                    "price_level": p.price_level
                }
                for p in places
            ],
            "source": "database"
        }
        
    except Exception as e:
        logger.error(f"Ошибка получения рекомендаций: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@recommendations_router.get("/personal")
async def get_personal_recommendations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Персонализированные рекомендации через LLM"""
    try:
        llm_service = LLMService()
        recommendations = await llm_service.generate_recommendations(current_user.id, db)
        
        if recommendations:
            return {
                "success": True,
                "recommendations": recommendations,
                "source": "ollama"
            }
        else:
            # Fallback: простые рекомендации по категориям
            categories = current_user.preferences.get("categories", ["cafe", "restaurant"]) if current_user.preferences else ["cafe"]
            
            places_result = await db.execute(
                select(Place)
                .where(Place.category.in_(categories), Place.is_active == True)
                .limit(5)
            )
            places = places_result.scalars().all()
            
            return {
                "success": True,
                "recommendations": [
                    {"id": p.id, "name": p.name, "category": p.category, "description": p.description}
                    for p in places
                ],
                "source": "database_fallback"
            }
            
    except Exception as e:
        logger.error(f"Ошибка получения рекомендаций: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class IntelligentSearchRequest(BaseModel):
    """Модель для интеллектуального поиска"""
    query: str
    telegram_id: Optional[int] = None
    limit: int = 10

@recommendations_router.post("/intelligent-search")
async def intelligent_search(
    request: IntelligentSearchRequest,
    db: AsyncSession = Depends(get_db)
):
    """Интеллектуальный поиск мест с использованием LLM"""
    try:
        llm_service = LLMService()
        
        # 1. Анализируем запрос с помощью LLM
        analysis = await llm_service.analyze_search_query(request.query, db)
        
        logger.info(f"LLM анализ запроса '{request.query}': {analysis}")
        
        # 2. Строим запрос к базе данных на основе анализа
        query_builder = select(Place).where(Place.is_active == True)
        
        # Фильтр по категории
        if analysis.get("category"):
            query_builder = query_builder.where(Place.category == analysis["category"])
        
        # Фильтр по городу
        city = analysis.get("city", "Москва")
        query_builder = query_builder.where(Place.city == city)
        
        # Получаем все места для фильтрации по ключевым словам
        result = await db.execute(query_builder.limit(100))
        all_places = result.scalars().all()
        
        # 3. Фильтруем места по ключевым словам
        keywords = analysis.get("keywords", [])
        filtered_places = []
        
        for place in all_places:
            if not place:
                continue
            
            # Создаем текст для поиска ключевых слов
            search_text = f"{place.name} {place.description or ''} {' '.join(place.tags or [])}".lower()
            
            # Проверяем наличие ключевых слов
            keyword_matches = 0
            for keyword in keywords:
                if keyword.lower() in search_text:
                    keyword_matches += 1
            
            # Если есть совпадения или ключевых слов нет, включаем место
            if keyword_matches > 0 or not keywords:
                # Добавляем информацию о совпадениях
                place_dict = {
                    "id": place.id,
                    "name": place.name,
                    "description": place.description,
                    "category": place.category,
                    "city": place.city,
                    "address": place.address,
                    "price_level": place.price_level,
                    "tags": place.tags,
                    "rating": place.rating,
                    "review_count": await get_place_review_count(db, place.id),
                    "keyword_matches": keyword_matches
                }
                filtered_places.append(place_dict)
        
        # 4. Сортируем результаты
        sort_by = analysis.get("sort_by", "rating")
        if sort_by == "reviews":
            filtered_places.sort(key=lambda x: (x.get("review_count", 0), x.get("rating", 0)), reverse=True)
        elif sort_by == "random":
            import random
            random.shuffle(filtered_places)
        else:  # rating
            filtered_places.sort(key=lambda x: (x.get("rating", 0), x.get("review_count", 0)), reverse=True)
        
        # 5. Ограничиваем количество результатов
        places_to_return = filtered_places[:request.limit]
        
        # 6. Формируем ответ
        response = {
            "success": True,
            "query": request.query,
            "analysis": analysis,
            "places": places_to_return,
            "total_found": len(filtered_places),
            "total_shown": len(places_to_return),
            "source": "intelligent_search"
        }
        
        return response
        
    except Exception as e:
        logger.error(f"Ошибка интеллектуального поиска: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

async def get_place_review_count(db: AsyncSession, place_id: UUID) -> int:
    """Получает количество одобренных отзывов для места"""
    try:
        result = await db.execute(
            select(func.count(Review.id)).where(
                Review.place_id == place_id,
                Review.moderation_status == "approved"
            )
        )
        return result.scalar() or 0
    except:
        return 0
    
@recommendations_router.post("/chat")
async def get_chat_recommendations(
    request: RecommendationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Рекомендации через чат-интерфейс"""
    try:
        
        # Обновляем предпочтения если переданы
        if request.categories or request.city or request.budget:
            if not current_user.preferences:
                current_user.preferences = {}
            
            if request.categories:
                current_user.preferences["categories"] = request.categories
            if request.city:
                current_user.preferences["city"] = request.city
            if request.budget:
                current_user.preferences["budget"] = request.budget
            
            await db.commit()
        
        # Генерируем рекомендации через LLM
        llm_service = LLMService()
        recommendations = await llm_service.generate_recommendations(current_user.id, db)
        
        if recommendations:
            return {
                "success": True,
                "message": recommendations,
                "type": "llm_recommendations"
            }
        else:
            return {
                "success": True,
                "message": "Пока не могу сгенерировать персонализированные рекомендации. Попробуйте позже или уточните ваши предпочтения.",
                "type": "fallback_message"
            }
            
    except Exception as e:
        logger.error(f"Ошибка получения чат-рекомендаций: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Парсер
@parser_router.get("/status")
async def get_parser_status(db: AsyncSession = Depends(get_db)):
    """Получение статуса парсера"""
    try:
        # Получаем статистику по спарсенным местам
        result = await db.execute(
            select(func.count(Place.id))
            .where(Place.created_by.isnot(None))
        )
        parsed_count = result.scalar() or 0
        
        # Получаем количество активных мест
        result = await db.execute(
            select(func.count(Place.id))
            .where(Place.is_active == True)
        )
        active_count = result.scalar() or 0
        
        # Получаем количество просроченных мест
        result = await db.execute(
            select(func.count(Place.id))
            .where(
                Place.expired_at.isnot(None),
                Place.expired_at < datetime.utcnow()
            )
        )
        expired_count = result.scalar() or 0
        
        return {
            "status": "running",
            "parsed_places": parsed_count,
            "active_places": active_count,
            "expired_places": expired_count,
            "last_check": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Ошибка получения статуса парсера: {e}")
        return {"status": "error", "error": str(e)}

@parser_router.post("/cleanup")
async def cleanup_expired(
    current_user: User = Depends(require_moderator),
    db: AsyncSession = Depends(get_db)
):
    """Ручная очистка просроченных мест"""
    try:
        current_time = datetime.utcnow()
        
        # Находим просроченные места
        result = await db.execute(
            select(Place).where(
                Place.expired_at.isnot(None),
                Place.expired_at < current_time,
                Place.is_active == True
            )
        )
        expired_places = result.scalars().all()
        
        if not expired_places:
            return {"message": "Нет просроченных мест для очистки"}
        
        # Деактивируем
        for place in expired_places:
            place.is_active = False
            place.moderation_status = "expired"
            place.moderation_reason = f"Срок действия истек {place.expired_at}"
        
        await db.commit()
        
        return {
            "message": f"Деактивировано {len(expired_places)} просроченных мест",
            "deactivated_count": len(expired_places),
            "moderator": current_user.username
        }
        
    except Exception as e:
        logger.error(f"Ошибка очистки просроченных мест: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@parser_router.get("/places/expiring-soon")
async def get_expiring_soon(
    days: int = Query(7, ge=1, le=30),
    db: AsyncSession = Depends(get_db)
):
    """Получение мест, срок действия которых скоро истекает"""
    try:
        threshold = datetime.utcnow() + timedelta(days=days)
        
        result = await db.execute(
            select(Place)
            .where(
                Place.expired_at.isnot(None),
                Place.expired_at <= threshold,
                Place.expired_at > datetime.utcnow(),
                Place.is_active == True
            )
            .order_by(Place.expired_at)
        )
        
        places = result.scalars().all()
        
        return {
            "places": [
                {
                    "id": p.id,
                    "name": p.name,
                    "category": p.category,
                    "city": p.city,
                    "expired_at": p.expired_at.isoformat() if p.expired_at else None,
                    "days_left": (p.expired_at - datetime.utcnow()).days if p.expired_at else None
                }
                for p in places
            ],
            "total": len(places),
            "threshold_days": days
        }
        
    except Exception as e:
        logger.error(f"Ошибка получения истекающих мест: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
# ========== ПОДКЛЮЧЕНИЕ РОУТЕРОВ ==========
app.include_router(auth_router, prefix="/api/v1/auth", tags=["Аутентификация"])
app.include_router(places_router, prefix="/api/v1/places", tags=["Места"])
app.include_router(reviews_router, prefix="/api/v1/reviews", tags=["Отзывы"])
app.include_router(moderation_router, prefix="/api/v1/moderation", tags=["Модерация"])
app.include_router(recommendations_router, prefix="/api/v1/recommendations", tags=["Рекомендации"])
app.include_router(parser_router, prefix="/api/v1/parser", tags=["Парсер"])

# ========== ОСНОВНЫЕ ЭНДПОИНТЫ ==========
@app.get("/")
async def root():
    return {
        "message": "Travel Recommendation API with Ollama is running!",
        "docs": "/docs",
        "version": "1.0.0",
        "llm": "Ollama (локальная модель)",
        "note": "Используется тестовый пользователь (ID=1) для всех операций"
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "travel-recommendation-api", "llm": "Ollama"}

@app.get("/llm-status")
async def llm_status():
    """Проверка статуса Ollama"""
    llm_service = LLMService()
    
    # Проверяем подключение
    is_connected = await llm_service.client.test_connection()
    
    # Делаем тестовый запрос если подключение есть
    test_result = None
    if is_connected:
        test_result = await llm_service.summarize_review("Отличное место, рекомендую!", 5)
    
    return {
        "llm": "Ollama",
        "model": settings.OLLAMA_MODEL,
        "base_url": settings.OLLAMA_BASE_URL,
        "connected": is_connected,
        "test_successful": test_result is not None and len(test_result) > 0,
        "test_result": test_result[:100] + "..." if test_result else None,
        "available_models": await llm_service.client.get_available_models() if hasattr(llm_service.client, 'get_available_models') else []
    }

@app.get("/test")
async def test_endpoint():
    """Тестовый эндпоинт для проверки работы"""
    return {
        "status": "ok",
        "message": "API работает корректно",
        "endpoints": {
            "create_place": "POST /api/v1/places/",
            "create_review": "POST /api/v1/reviews/",
            "get_places": "GET /api/v1/places/",
            "get_recommendations": "GET /api/v1/recommendations/personal",
            "llm_status": "GET /llm-status"
        }
    }

# ========== СОЗДАНИЕ ТАБЛИЦ И ТЕСТОВЫХ ДАННЫХ ==========
@app.on_event("startup")
async def startup_event():
    """Создание таблиц и тестовых данных при запуске"""
    import time
    
    logger.info("Запуск инициализации БД...")
    time.sleep(2)
    
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("✅ Таблицы созданы через SQLAlchemy")
        
        # Проверка Ollama
        llm_service = LLMService()
        is_connected = await llm_service.client.test_connection()
        if is_connected:
            logger.info(f"✅ Ollama подключен, модель: {settings.OLLAMA_MODEL}")
        else:
            logger.warning("⚠️  Ollama не доступен. Запустите: 'ollama serve'")
        
        # Создаем тестовые данные
        await create_test_data()
            
    except Exception as e:
        logger.error(f"❌ Ошибка создания таблиц: {e}")

async def create_test_data():
    """Создание тестовых данных"""
    async with AsyncSessionLocal() as session:
        try:
            # Создаем тестового пользователя
            from uuid import UUID as UUIDType
            test_user_uuid = UUIDType('11111111-1111-1111-1111-111111111111')
            
            # Создаем тестового пользователя
            result = await session.execute(select(User).where(User.id == test_user_uuid))
            test_user = result.scalar_one_or_none()
            
            if not test_user:
                test_user = User(
                    id=test_user_uuid,
                    telegram_id=123456789,
                    username="test_user",
                    first_name="Тестовый",
                    last_name="Пользователь",
                    role="user",
                    preferences={"categories": ["cafe", "restaurant"], "city": "Москва"},
                    is_active=True
                )
                session.add(test_user)
                await session.flush()
                logger.info("✅ Создан тестовый пользователь ID=1")
            
            # Создаем тестовые места если их нет
            result = await session.execute(select(Place))
            places = result.scalars().all()
            
            if not places:
                test_places = [
                    Place(
                        name="Кофейня Central Perk",
                        description="Уютная кофейня с лучшим кофе в городе",
                        category="cafe",
                        address="ул. Центральная, 10",
                        city="Москва",
                        price_level=2,
                        tags=["кофе", "десерты", "wi-fi", "уютно"],
                        created_by=test_user.id
                    ),
                    Place(
                        name="Ресторан Итальянская кухня",
                        description="Аутентичная итальянская пицца и паста",
                        category="restaurant",
                        address="ул. Итальянская, 5",
                        city="Москва",
                        price_level=3,
                        tags=["итальянская кухня", "пицца", "паста", "романтично"],
                        created_by=test_user.id
                    ),
                    Place(
                        name="Парк Горького",
                        description="Большой городской парк для прогулок",
                        category="park",
                        address="Крымский Вал, 9",
                        city="Москва",
                        price_level=1,
                        tags=["парк", "прогулки", "природа", "бесплатно"],
                        created_by=test_user.id
                    )
                ]
                
                for place in test_places:
                    session.add(place)
                
                await session.flush()
                logger.info("✅ Созданы тестовые места")
            
            await session.commit()
            logger.info("✅ Тестовые данные созданы")
                
        except Exception as e:
            logger.error(f"Ошибка создания тестовых данных: {e}")
            await session.rollback()

async def update_all_place_ratings(db: AsyncSession):
    """Обновляет рейтинги всех мест (при запуске)"""
    try:
        # Получаем все места
        result = await db.execute(select(Place.id))
        place_ids = result.scalars().all()
        
        for place_id in place_ids:
            await update_place_rating(db, place_id)
        
        await db.commit()
        logger.info(f"Обновлены рейтинги для {len(place_ids)} мест")
        
    except Exception as e:
        logger.error(f"Ошибка обновления рейтингов: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)