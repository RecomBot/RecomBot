# bot/middlewares/logging.py
import logging
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery

logger = logging.getLogger(__name__)

class LoggingMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        if isinstance(event, Message):
            user = event.from_user
            logger.info(f"[{user.id}@{user.username or 'anon'}] {event.text or '[media]'}")
        elif isinstance(event, CallbackQuery):
            user = event.from_user
            logger.info(f"[{user.id}@{user.username or 'anon'}] Callback: {event.data}")
        
        return await handler(event, data)