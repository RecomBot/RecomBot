# backend/src/schemas/user.py
"""
Pydantic схемы для пользователей
"""

from uuid import UUID
from typing import Optional, Dict, List
from pydantic import BaseModel, Field


class UserBase(BaseModel):
    """Базовая схема пользователя"""
    telegram_id: Optional[int] = None
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class UserCreate(UserBase):
    """Схема для создания пользователя"""
    role: str = "user"
    preferences: Dict = {}


class UserUpdate(BaseModel):
    """Схема для обновления пользователя"""
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    preferences: Optional[Dict] = None
    is_active: Optional[bool] = None


class UserResponse(UserBase):
    """Схема для ответа с пользователем"""
    id: UUID
    role: str
    preferences: Dict
    is_active: bool
    created_at: str
    
    class Config:
        from_attributes = True


class UserPermissions(BaseModel):
    """Схема для прав пользователя"""
    can_view_places: bool = True
    can_view_place_details: bool = True
    can_create_reviews: bool = True
    can_view_own_reviews: bool = True
    can_get_recommendations: bool = True
    can_create_places: bool = False
    can_delete_reviews: bool = False
    can_moderate_reviews: bool = False
    can_view_moderation: bool = False
    can_manage_users: bool = False