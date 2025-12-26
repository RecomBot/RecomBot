# backend/src/routers/auth.py
"""
Роутер для аутентификации и управления пользователями
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

# Универсальные импорты
try:
    from ..database import get_db, User
    from ..schemas.user import UserPermissions, UserResponse
    from ..dependencies import (
        get_current_user, 
        require_any,
        get_or_create_test_user,
        get_or_create_user_by_role,
        set_current_test_user_id
    )
except ImportError:
    from database import get_db, User
    from schemas.user import UserPermissions, UserResponse
    from dependencies import (
        get_current_user, 
        require_any,
        get_or_create_test_user,
        get_or_create_user_by_role,
        set_current_test_user_id
    )

router = APIRouter()


@router.get("/test-user")
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


@router.get("/current")
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """Получение информации о текущем пользователе"""
    return {
        "id": current_user.id,
        "telegram_id": current_user.telegram_id,
        "username": current_user.username,
        "first_name": current_user.first_name,
        "last_name": current_user.last_name,
        "role": current_user.role,
        "preferences": current_user.preferences,
        "is_active": current_user.is_active,
        "note": "Это текущий пользователь для всех запросов"
    }


@router.post("/switch-role/{role}")
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


@router.get("/permissions")
async def get_permissions(
    current_user: User = Depends(get_current_user)
):
    """Получение списка доступных действий для текущего пользователя"""
    permissions = UserPermissions(
        can_create_places=current_user.role in ["moderator", "admin"],
        can_delete_reviews=current_user.role in ["moderator", "admin"],
        can_moderate_reviews=current_user.role in ["moderator", "admin"],
        can_view_moderation=current_user.role in ["moderator", "admin"],
        can_manage_users=current_user.role == "admin",
    )
    
    return {
        "user": {
            "id": current_user.id,
            "username": current_user.username,
            "role": current_user.role
        },
        "permissions": permissions.dict()
    }