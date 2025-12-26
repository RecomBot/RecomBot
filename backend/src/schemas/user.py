# backend/src/schemas/user.py
from typing import Optional
from uuid import UUID
from pydantic import Field, field_validator
from .base import BaseSchema, TimestampSchema
from shared.models.enums import UserRole

class UserBase(BaseSchema):
    """Базовая схема пользователя"""
    telegram_id: int = Field(..., gt=0, description="Telegram ID")
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: UserRole = Field(default=UserRole.USER)

class UserCreate(BaseSchema):
    """Схема для создания пользователя"""
    tg_id: int = Field(..., alias="telegram_id", gt=0)
    location: str = Field(..., min_length=2, max_length=100)
    username: Optional[str] = None
    
    @field_validator("location")
    @classmethod
    def validate_location(cls, v):
        # Нормализуем название города
        location_map = {
            "москва": "Moscow",
            "спб": "Saint Petersburg",
            "питер": "Saint Petersburg",
            "санкт-петербург": "Saint Petersburg",
            "казань": "Kazan",
            "екб": "Yekaterinburg",
            "екатеринбург": "Yekaterinburg",
        }
        return location_map.get(v.lower(), v)

class UserUpdate(BaseSchema):
    """Схема для обновления пользователя"""
    preferences: Optional[dict] = None
    is_active: Optional[bool] = None

class UserResponse(TimestampSchema):
    """Схема ответа с пользователем"""
    id: UUID
    telegram_id: int
    username: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    role: UserRole
    preferences: dict
    is_active: bool