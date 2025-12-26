# backend/src/routers/auth.py
from fastapi import APIRouter, Depends, HTTPException, status 
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import uuid4
from ..dependencies import get_db_session
from ..models import User, UserRole
from ..schemas.user import UserCreate, UserResponse
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db_session)
):
    """Регистрация/получение пользователя по Telegram ID"""
    # Проверяем, существует ли пользователь
    result = await db.execute(
        select(User).where(User.telegram_id == user_data.tg_id)
    )
    existing_user = result.scalar_one_or_none()
    
    if existing_user:
        # Обновляем предпочтения, если нужно
        if user_data.location and existing_user.preferences.get('city') != user_data.location:
            existing_user.preferences = existing_user.preferences or {}
            existing_user.preferences['city'] = user_data.location
            await db.commit()
            await db.refresh(existing_user)
        
        return UserResponse.model_validate(existing_user)
    
    # Создаем нового пользователя
    new_user = User(
        id=uuid4(),
        telegram_id=user_data.tg_id,
        username=user_data.username,
        first_name=user_data.username,  # В Telegram боте будет реальное имя
        role=UserRole.USER,
        preferences={"city": user_data.location},
        is_active=True
    )
    
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    logger.info(f"New user registered: {new_user.telegram_id} in {user_data.location}")
    return UserResponse.model_validate(new_user)

@router.get("/by_tg/{telegram_id}", response_model=UserResponse)
async def get_user_by_telegram_id(
    telegram_id: int,
    db: AsyncSession = Depends(get_db_session)
):
    """Получить пользователя по Telegram ID"""
    result = await db.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден"
        )
    
    return UserResponse.model_validate(user)

@router.get("/{user_id}", response_model=UserResponse)
async def get_user_by_id(
    user_id: str,
    db: AsyncSession = Depends(get_db_session)
):
    """Получить пользователя по ID"""
    from uuid import UUID
    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неверный формат ID"
        )
    
    result = await db.execute(
        select(User).where(User.id == user_uuid)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден"
        )
    
    return UserResponse.model_validate(user)