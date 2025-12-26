# bot/handlers/moderation_router.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from ..utils.http_client import http_client
import logging

router = Router()
logger = logging.getLogger(__name__)


@router.message(Command("modqueue", ignore_mention=True))
async def cmd_modqueue(message: Message):
    """Показать очередь на модерацию"""
    try:
        # Получаем очередь на модерацию через API
        reviews = await http_client.get_moderation_queue(
            tg_id=message.from_user.id,
            limit=10
        )
        
        if not reviews:
            await message.answer("✅ *Нет отзывов на модерации.*", parse_mode="Markdown")
            return
        
        text = "🟡 *Очередь на модерацию:*\n\n"
        for review in reviews:
            # Формируем inline-кнопки для действий
            review_id = review.get("id", "")
            place_name = review.get("place", {}).get("name", "Без названия")[:30]
            user_username = f"user_{review.get('user', {}).get('telegram_id', '')}"
            review_text = review.get("text", "")[:60]
            
            text += (
                f"• *{place_name}*\n"
                f"  👤 {user_username}\n"
                f"  ⭐ {review.get('rating', 0)}/5\n"
                f"  💬 _«{review_text}...»_\n"
                f"  📅 {review.get('created_at', '')[:10]}\n\n"
            )
        
        # Добавляем инструкцию
        text += "\n*Используйте команды:*\n"
        text += "`/approve <id>` — одобрить отзыв\n"
        text += "`/reject <id>` — отклонить отзыв\n"
        text += "`/modqueue` — обновить список"
        
        await message.answer(text, parse_mode="Markdown")
        
    except Exception as e:
        logger.exception("❌ Ошибка /modqueue")
        error_msg = str(e)
        if "403" in error_msg:
            await message.answer(
                "❌ *Доступ запрещён!*\n"
                "Эта команда доступна только модераторам и администраторам.",
                parse_mode="Markdown"
            )
        else:
            await message.answer(
                "❌ *Не удалось загрузить очередь модерации.*\n"
                "Попробуйте позже или проверьте подключение к API.",
                parse_mode="Markdown"
            )


@router.message(Command("approve", ignore_mention=True))
async def cmd_approve(message: Message):
    """Команда: /approve <review_id>"""
    args = message.text.split()
    if len(args) < 2:
        await message.answer(
            "ℹ️ *Использование:* `/approve <id_отзыва>`\n\n"
            "Например: `/approве 550e8400-e29b-41d4-a716-446655440000`",
            parse_mode="Markdown"
        )
        return
    
    review_id = args[1].strip()
    
    try:
        # Пытаемся одобрить отзыв через API
        result = await http_client.approve_review(
            tg_id=message.from_user.id,
            review_id=review_id,
            notes=f"Одобрено модератором @{message.from_user.username or message.from_user.id}"
        )
        
        await message.answer(
            f"✅ *Отзыв одобрен!*\n\n"
            f"ID: `{review_id}`\n"
            f"Рейтинг: {result.get('rating', 0)}⭐\n"
            f"Статус: {result.get('moderation_status', 'approved')}",
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.exception(f"❌ Ошибка одобрения отзыва {review_id}")
        error_msg = str(e)
        
        if "403" in error_msg:
            await message.answer(
                "❌ *Доступ запрещён!*\n"
                "Эта команда доступна только модераторам и администраторам.",
                parse_mode="Markdown"
            )
        elif "404" in error_msg:
            await message.answer(
                f"❌ *Отзыв не найден!*\n"
                f"ID `{review_id}` не существует или уже обработан.",
                parse_mode="Markdown"
            )
        elif "400" in error_msg and "уже одобрен" in error_msg:
            await message.answer(
                f"ℹ️ *Отзыв уже одобрен!*\n"
                f"ID: `{review_id}`",
                parse_mode="Markdown"
            )
        else:
            await message.answer(
                f"❌ *Ошибка при одобрении отзыва:*\n`{error_msg[:100]}`",
                parse_mode="Markdown"
            )


@router.message(Command("reject", ignore_mention=True))
async def cmd_reject(message: Message):
    """Команда: /reject <review_id> [причина]"""
    args = message.text.split(maxsplit=2)
    if len(args) < 2:
        await message.answer(
            "ℹ️ *Использование:* `/reject <id_отзыва> [причина]`\n\n"
            "Например:\n"
            "`/reject 550e8400-e29b-41d4-a716-446655440000`\n"
            "`/reject 550e8400-e29b-41d4-a716-446655440000 спам`",
            parse_mode="Markdown"
        )
        return
    
    review_id = args[1].strip()
    notes = args[2] if len(args) > 2 else None
    
    try:
        # Пытаемся отклонить отзыв через API
        result = await http_client.reject_review(
            tg_id=message.from_user.id,
            review_id=review_id,
            notes=notes or f"Отклонено модератором @{message.from_user.username or message.from_user.id}"
        )
        
        await message.answer(
            f"❌ *Отзыв отклонён!*\n\n"
            f"ID: `{review_id}`\n"
            f"Рейтинг: {result.get('rating', 0)}⭐\n"
            f"Статус: {result.get('moderation_status', 'rejected')}\n"
            f"Причина: {notes or 'не указана'}",
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.exception(f"❌ Ошибка отклонения отзыва {review_id}")
        error_msg = str(e)
        
        if "403" in error_msg:
            await message.answer(
                "❌ *Доступ запрещён!*\n"
                "Эта команда доступна только модераторам и администраторам.",
                parse_mode="Markdown"
            )
        elif "404" in error_msg:
            await message.answer(
                f"❌ *Отзыв не найден!*\n"
                f"ID `{review_id}` не существует или уже обработан.",
                parse_mode="Markdown"
            )
        elif "400" in error_msg and "уже отклонен" in error_msg:
            await message.answer(
                f"ℹ️ *Отзыв уже отклонён!*\n"
                f"ID: `{review_id}`",
                parse_mode="Markdown"
            )
        else:
            await message.answer(
                f"❌ *Ошибка при отклонении отзыва:*\n`{error_msg[:100]}`",
                parse_mode="Markdown"
            )


@router.message(Command("modstats", ignore_mention=True))
async def cmd_modstats(message: Message):
    """Статистика модерации"""
    try:
        # Получаем очередь
        reviews = await http_client.get_moderation_queue(
            tg_id=message.from_user.id,
            limit=50  # Для статистики берем больше
        )
        
        if not reviews:
            await message.answer(
                "📊 *Статистика модерации:*\n\n"
                "✅ Очередь пуста! Все отзывы обработаны.",
                parse_mode="Markdown"
            )
            return
        
        # Анализируем статусы
        pending = 0
        flagged = 0
        
        for review in reviews:
            status = review.get("moderation_status", "")
            if status == "pending":
                pending += 1
            elif status == "flagged_by_llm":
                flagged += 1
        
        await message.answer(
            f"📊 *Статистика модерации:*\n\n"
            f"📋 Всего в очереди: *{len(reviews)}*\n"
            f"⏳ Ожидают проверки: *{pending}*\n"
            f"🚩 Флаги от LLM: *{flagged}*\n\n"
            f"🕐 Среднее время в очереди: ~{len(reviews) * 5} мин\n"
            f"📈 Загруженность: {min(100, len(reviews) * 10)}%",
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.exception("❌ Ошибка /modstats")
        error_msg = str(e)
        if "403" in error_msg:
            await message.answer(
                "❌ *Доступ запрещён!*\n"
                "Эта команда доступна только модераторам и администраторам.",
                parse_mode="Markdown"
            )
        else:
            await message.answer(
                "❌ *Не удалось загрузить статистику.*",
                parse_mode="Markdown"
            )