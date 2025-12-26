# GidRecBot/bot/middlewares/user_middleware.py (НОВЫЙ ФАЙЛ)
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from typing import Callable, Dict, Any, Awaitable
from ..utils.user_manager import get_or_create_user
import logging

logger = logging.getLogger(__name__)

class UserMiddleware(BaseMiddleware):
    """Middleware для автоматического создания/получения пользователя"""
    
    async def __call__(
        self,
        handler: Callable,
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        
        # Получаем информацию о пользователе из события
        if isinstance(event, Message):
            user = event.from_user
        elif isinstance(event, CallbackQuery):
            user = event.from_user
        else:
            return await handler(event, data)
        
        # Гарантируем, что пользователь существует в backend
        backend_user = await get_or_create_user(
            tg_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name or ""
        )
        
        if backend_user:
            # Сохраняем информацию о пользователе в данных
            data["backend_user"] = backend_user
            logger.debug(f"Пользователь {user.id} готов: {backend_user.get('id')}")
        else:
            logger.warning(f"Не удалось создать/получить пользователя {user.id}")
            # Создаем минимальный объект пользователя для продолжения работы
            data["backend_user"] = {
                "telegram_id": user.id,
                "username": user.username,
                "first_name": user.first_name,
                "role": "user",
                "permissions": {
                    "can_view_places": True,
                    "can_create_reviews": True,
                    "can_get_recommendations": True
                }
            }
        
        # Продолжаем обработку
        return await handler(event, data)