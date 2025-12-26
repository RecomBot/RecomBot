# backend/src/dependencies.py
"""
Зависимости FastAPI для аутентификации и авторизации
"""

from typing import List
from uuid import UUID

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

# Исправляем импорт database
try:
    from .database import get_db, User
except ImportError:
    from database import get_db, User

# Для совместимости со старым кодом пока оставляем тестового пользователя
_CURRENT_TEST_USER_ID = UUID('11111111-1111-1111-1111-111111111111')


def get_current_test_user_id() -> UUID:
    """Получение ID текущего тестового пользователя"""
    return _CURRENT_TEST_USER_ID


def set_current_test_user_id(user_id: UUID):
    """Установка ID текущего тестового пользователя"""
    global _CURRENT_TEST_USER_ID
    _CURRENT_TEST_USER_ID = user_id


async def get_current_user(db: AsyncSession = Depends(get_db)) -> User:
    """Получение текущего пользователя (упрощенная версия)"""
    current_user_id = get_current_test_user_id()
    
    result = await db.execute(select(User).where(User.id == current_user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Пользователь заблокирован")
    
    return user


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


# Утилиты для тестовых пользователей
async def get_or_create_user_by_role(db: AsyncSession, role: str = "user") -> User:
    """Получение или создание пользователя с указанной ролью"""
    from uuid import UUID as UUIDType
    
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
        user_data = {
            "id": user_uuid,
            "role": role,
            "preferences": {},
            "is_active": True
        }
        
        if role == "moderator":
            user_data.update({
                "telegram_id": 987654321,
                "username": f"test_{role}",
                "first_name": f"Тестовый {role}",
                "last_name": "",
            })
        elif role == "admin":
            user_data.update({
                "telegram_id": 999999999,
                "username": f"test_{role}",
                "first_name": f"Тестовый {role}",
                "last_name": "",
            })
        else:  # user
            user_data.update({
                "telegram_id": 123456789,
                "username": "test_user",
                "first_name": "Тестовый",
                "last_name": "Пользователь",
                "preferences": {"categories": ["cafe", "restaurant"], "city": "Москва"},
            })
        
        user = User(**user_data)
        db.add(user)
        await db.flush()
    
    return user


async def get_or_create_test_user(db: AsyncSession, role: str = "user") -> User:
    """Получение или создание тестового пользователя (совместимость)"""
    return await get_or_create_user_by_role(db, role)