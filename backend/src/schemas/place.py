# backend/src/schemas/place.py
from typing import Optional
from uuid import UUID
from pydantic import Field, field_validator
from .base import BaseSchema, TimestampSchema
from shared.models.enums import PlaceCategory, SourceType

class PlaceBase(BaseSchema):
    """Базовая схема места"""
    name: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    category: PlaceCategory
    city: str = Field(default="Moscow")
    address: Optional[str] = None
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    price_level: int = Field(default=2, ge=1, le=5)
    source: SourceType = Field(default=SourceType.USER)

class PlaceCreate(PlaceBase):
    """Схема для создания места"""
    external_id: Optional[str] = None
    external_url: Optional[str] = None

class PlaceUpdate(BaseSchema):
    """Схема для обновления места"""
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[PlaceCategory] = None
    address: Optional[str] = None
    price_level: Optional[int] = None
    is_active: Optional[bool] = None

class PlaceResponse(TimestampSchema):
    """Схема ответа с местом"""
    id: UUID
    name: str
    description: Optional[str]
    category: PlaceCategory
    city: str
    address: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    price_level: int
    rating: float = Field(ge=0, le=5)
    rating_count: int = Field(ge=0)
    source: SourceType
    external_url: Optional[str]
    is_active: bool

class PlaceListResponse(BaseSchema):
    """Схема для списка мест с пагинацией"""
    places: list[PlaceResponse]
    total: int
    page: int
    page_size: int
    has_next: bool