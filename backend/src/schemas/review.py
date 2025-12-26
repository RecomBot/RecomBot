# backend/src/schemas/review.py
from typing import Optional
from uuid import UUID
from pydantic import Field, field_validator
from .base import BaseSchema, TimestampSchema
from shared.models.enums import ModerationStatus
from .user import UserResponse
from .place import PlaceResponse

class ReviewBase(BaseSchema):
    """Базовая схема отзыва"""
    rating: int = Field(..., ge=1, le=5)
    text: str = Field(..., min_length=10, max_length=500)

class ReviewCreate(ReviewBase):
    """Схема для создания отзыва"""
    place_id: UUID
    
    @field_validator("text")
    @classmethod
    def validate_text(cls, v):
        # Базовые проверки текста
        if len(v.strip()) < 10:
            raise ValueError("Текст отзыва должен содержать минимум 10 символов")
        return v.strip()

class ReviewUpdate(BaseSchema):
    """Схема для обновления отзыва (модерация)"""
    moderation_status: Optional[ModerationStatus] = None
    moderation_notes: Optional[str] = None

class ReviewResponse(TimestampSchema):
    """Схема ответа с отзывом"""
    id: UUID
    user_id: UUID
    place_id: UUID
    rating: int
    text: str
    summary: Optional[str]
    moderation_status: ModerationStatus
    moderated_by: Optional[UUID]
    moderation_notes: Optional[str]
    llm_check: Optional[dict]

class ReviewWithRelationsResponse(ReviewResponse):
    """Отзыв с связанными данными"""
    user: UserResponse
    place: PlaceResponse
    moderator: Optional[UserResponse] = None