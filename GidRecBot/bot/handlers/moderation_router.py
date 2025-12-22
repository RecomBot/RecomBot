# bot/handlers/moderation_router.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from ..utils.http_client import http_client
import logging

router = Router()
logger = logging.getLogger(__name__)

# 🎯 Mock-данные для модерации (временно)
MOCK_REVIEWS = [
    {
        "id": 1,
        "place_name": "Кофейня у Патриарших",
        "user_username": "@user123",
        "text": "Восхитительно! Блины горячие, начинка сочная. Вернусь обязательно!"
    },
    {
        "id": 2,
        "place_name": "Музей современного искусства",
        "user_username": "@user456",
        "text": "Интересные выставки, но дорого. Билет — 1200₽."
    }
]

@router.message(Command("modqueue", ignore_mention=True))
async def cmd_modqueue(message: Message):
    """Показать очередь на модерацию (mock)"""
    try:
        # 🎯 Mock: возвращаем фиксированный список
        reviews = MOCK_REVIEWS
        
        if not reviews:
            await message.answer("✅ Нет отзывов на модерации.")
            return
        
        text = "🟡 *Очередь на модерацию:*\n"
        for review in reviews:
            text += (
                f"\n• *{review['place_name']}*\n"
                f"  👤 {review['user_username']}\n"
                f"  💬 _«{review['text'][:60]}...»_\n"
                f"  [✅ Одобрить] [❌ Отклонить]\n"
            )
        
        await message.answer(text, parse_mode="Markdown")
        
    except Exception as e:
        logger.exception("❌ Ошибка /modqueue")
        await message.answer("❌ Ошибка получения очереди.")

@router.message(Command("approve", ignore_mention=True))
async def cmd_approve(message: Message):
    """Команда: /approve 123"""
    args = message.text.split()
    if len(args) < 2:
        await message.answer("ℹ️ Использование: `/approve <id>`", parse_mode="Markdown")
        return
    
    try:
        review_id = int(args[1])
        # 🎯 Mock: всегда одобряем
        await message.answer(f"✅ Отзыв #{review_id} одобрен!", parse_mode="Markdown")
    except ValueError:
        await message.answer("❌ ID должен быть числом.")
    except Exception as e:
        logger.exception("❌ Ошибка одобрения")
        await message.answer("❌ Ошибка одобрения.")

@router.message(Command("reject", ignore_mention=True))
async def cmd_reject(message: Message):
    """Команда: /reject 123"""
    args = message.text.split()
    if len(args) < 2:
        await message.answer("ℹ️ Использование: `/reject <id>`", parse_mode="Markdown")
        return
    
    try:
        review_id = int(args[1])
        # 🎯 Mock: всегда отклоняем
        await message.answer(f"❌ Отзыв #{review_id} отклонён.", parse_mode="Markdown")
    except ValueError:
        await message.answer("❌ ID должен быть числом.")
    except Exception as e:
        logger.exception("❌ Ошибка отклонения")
        await message.answer("❌ Ошибка отклонения.")