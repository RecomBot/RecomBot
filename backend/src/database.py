# backend/src/database.py
"""
Модуль для работы с базой данных: модели, подключение, сессии
"""

import uuid
import os
import sys
from typing import AsyncGenerator
from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, Text, Float, Boolean, JSON, DateTime,
    ForeignKey, BigInteger, func, Index
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base, relationship

# Универсальный импорт config
def get_settings():
    """Универсальная функция для получения настроек"""
    try:
        # Попытка 1: Импорт из config.py в той же директории
        from config import settings
        return settings
    except ImportError:
        try:
            # Попытка 2: Добавить родительскую директорию в путь
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from config import settings
            return settings
        except ImportError:
            # Fallback: настройки из переменных окружения
            class Settings:
                DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/travel_db")
                REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
                OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "https://ollama.com")
                OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3-coder:480b-cloud")
                OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY", "")
                JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your_super_secret_jwt_key_change_this_in_production_123")
                JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
                ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
            return Settings()

settings = get_settings()

# Базовый класс для моделей
Base = declarative_base()

# ========== МОДЕЛИ SQLALCHEMY ==========

class User(Base):
    """Модель пользователя"""
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    telegram_id = Column(BigInteger, unique=True, nullable=True, index=True)
    username = Column(String(100), nullable=True, index=True)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    role = Column(String(20), default="user", index=True)  # user, moderator, admin
    preferences = Column(JSON, default=dict)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Связи
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
    name = Column(String(200), nullable=False, index=True)
    description = Column(Text, nullable=True)
    category = Column(String(50), nullable=False, index=True)
    address = Column(Text, nullable=True)
    city = Column(String(100), nullable=True, index=True)
    price_level = Column(Integer, default=1, index=True)
    tags = Column(JSON, default=list)
    rating = Column(Float, default=0.0, index=True)
    is_active = Column(Boolean, default=True, index=True)
    
    # Модерация мест
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    moderation_status = Column(String(20), default="active", index=True)
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
    
    # Составные индексы для быстрого поиска
    __table_args__ = (
        Index('idx_place_search', 'name', 'category', 'city'),
        Index('idx_place_rating', 'rating', 'is_active'),
    )


class Review(Base):
    """Модель отзыва пользователя"""
    __tablename__ = "reviews"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    place_id = Column(UUID(as_uuid=True), ForeignKey("places.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Содержимое отзыва
    rating = Column(Integer, nullable=False)  # 1-5
    text = Column(Text, nullable=False)
    
    # LLM анализ
    llm_check = Column(JSON, nullable=True)
    summary = Column(Text, nullable=True)
    sentiment_score = Column(Float, nullable=True)
    
    # Модерация
    moderation_status = Column(String(20), default="pending", index=True)
    moderated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    moderated_at = Column(DateTime(timezone=True), nullable=True)
    moderation_notes = Column(Text, nullable=True)
    
    # Взаимодействия
    helpful_count = Column(Integer, default=0)
    reported_count = Column(Integer, default=0)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Связи
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
    __table_args__ = (
        Index('idx_review_user_place', 'user_id', 'place_id'),
        Index('idx_review_status_date', 'moderation_status', 'created_at'),
    )


# ========== ПОДКЛЮЧЕНИЕ К БАЗЕ ДАННЫХ ==========

# Создаем асинхронный движок
engine = create_async_engine(settings.DATABASE_URL, echo=True)

# Создаем фабрику сессий
AsyncSessionLocal = sessionmaker(
    engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Зависимость для получения сессии базы данных"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# Экспортируем важные объекты
__all__ = [
    'Base',
    'User',
    'Place', 
    'Review',
    'engine',
    'AsyncSessionLocal',
    'get_db',
]