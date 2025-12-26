# backend/src/schemas/review.py
"""
Pydantic схемы для отзывов
"""

from uuid import UUID
from typing import Optional
from pydantic import BaseModel, Field


class ReviewBase(BaseModel):
    """Базовая схема отзыва"""
    place_id: UUID
    rating: int = Field(..., ge=1, le=5)
    text: str = Field(..., min_length=10, max_length=2000)


class ReviewCreate(ReviewBase):
    """Схема для создания отзыва"""
    
    class Config:
        json_schema_extra = {
            "example": {
                "place_id": "123e4567-e89b-12d3-a456-426614174000",
                "rating": 5,
                "text": "Отличное место! Очень вкусный кофе."
            }
        }


class ReviewResponse(ReviewBase):
    """Схема для ответа с отзывом"""
    id: UUID
    user_id: UUID
    summary: Optional[str] = None
    moderation_status: str
    created_at: str
    helpful_count: int = 0
    
    class Config:
        from_attributes = True


class ReviewModeration(BaseModel):
    """Схема для модерации отзыва"""
    status: str = Field(..., pattern="^(approved|rejected)$")
    notes: Optional[str] = None