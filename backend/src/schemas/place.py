# backend/src/schemas/place.py
"""
Pydantic схемы для мест
"""

from uuid import UUID
from typing import Optional, List
from pydantic import BaseModel, Field


class PlaceBase(BaseModel):
    """Базовая схема места"""
    name: str
    description: Optional[str] = None
    category: str
    address: Optional[str] = None
    city: Optional[str] = None


class PlaceCreate(PlaceBase):
    """Схема для создания места"""
    price_level: int = Field(1, ge=1, le=5)
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


class PlaceUpdate(BaseModel):
    """Схема для обновления места"""
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    price_level: Optional[int] = Field(None, ge=1, le=5)
    tags: Optional[List[str]] = None
    is_active: Optional[bool] = None


class PlaceResponse(PlaceBase):
    """Схема для ответа с местом"""
    id: UUID
    price_level: int
    tags: List[str]
    rating: float = 0.0
    review_count: Optional[int] = None
    is_active: bool = True
    
    class Config:
        from_attributes = True


class PlaceStats(BaseModel):
    """Схема для статистики места"""
    place_id: UUID
    name: str
    current_rating: float
    total_reviews: int
    rating_distribution: dict
    recent_reviews: list