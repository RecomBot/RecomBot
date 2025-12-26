# GidRecBot/bot/handlers/user_reviews_router.py (НОВЫЙ ФАЙЛ)
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from ..utils.http_client import http_client
from ..keyboards.inline import get_back_keyboard, get_main_keyboard
from typing import List, Dict, Any
import logging
from datetime import datetime

router = Router()
logger = logging.getLogger(__name__)

def format_review_status(status: str) -> str:
    """Форматирование статуса отзыва"""
    status_map = {
        "approved": "✅ Одобрен",
        "pending": "🟡 На модерации", 
        "rejected": "❌ Отклонен",
        "flagged_by_llm": "🟡 На модерации (ИИ)"
    }
    return status_map.get(status, status)

def format_date(date_str: str) -> str:
    """Форматирование даты"""
    try:
        if not date_str:
            return "дата не указана"
        
        # Парсим дату
        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        
        # Определяем относительное время
        now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
        diff = now - dt
        
        if diff.days == 0:
            return "сегодня"
        elif diff.days == 1:
            return "вчера"
        elif diff.days < 7:
            return f"{diff.days} дней назад"
        elif diff.days < 30:
            weeks = diff.days // 7
            return f"{weeks} недель назад"
        else:
            return dt.strftime("%d.%m.%Y")
            
    except Exception:
        return date_str[:10] if date_str else ""

def get_review_keyboard(review: Dict[str, Any]) -> InlineKeyboardMarkup:
    """Клавиатура для управления отзывом"""
    buttons = []
    
    # Кнопки действий в зависимости от статуса
    if review.get("can_delete"):
        buttons.append([InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"delete_review:{review['id']}")])
    
    if review.get("can_edit"):
        buttons.append([InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"edit_review:{review['id']}")])
    
    buttons.append([InlineKeyboardButton(text="📍 Перейти к месту", callback_data=f"goto_place:{review['place_id']}")])
    buttons.append([InlineKeyboardButton(text="🔙 Назад к списку", callback_data="my_reviews")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

@router.message(Command("myreviews", ignore_mention=True))
@router.callback_query(F.data == "my_reviews")
async def show_user_reviews(event: Message | CallbackQuery):
    """Показывает отзывы пользователя"""
    try:
        if isinstance(event, CallbackQuery):
            message = event.message
            telegram_id = event.from_user.id
            await event.answer()
        else:
            message = event
            telegram_id = event.from_user.id
        
        loading_text = "📝 *Загружаю ваши отзывы...*"
        if isinstance(event, CallbackQuery):
            await message.edit_text(loading_text, parse_mode="Markdown")
        else:
            await message.answer(loading_text, parse_mode="Markdown")
        
        # Получаем отзывы пользователя из API
        response = await http_client.get_user_reviews(telegram_id, limit=20)
        
        if not response or "error" in response:
            error_text = "❌ *Не удалось загрузить ваши отзывы.*\n\nПопробуйте позже."
            if isinstance(event, CallbackQuery):
                await message.edit_text(error_text, parse_mode="Markdown", reply_markup=get_back_keyboard())
            else:
                await message.answer(error_text, parse_mode="Markdown", reply_markup=get_back_keyboard())
            return
        
        reviews = response.get("reviews", [])
        total = response.get("total", 0)
        
        if not reviews:
            # Нет отзывов
            no_reviews_text = (
                "📭 *У вас пока нет отзывов*\n\n"
                "Вы еще не оставляли отзывы на места.\n\n"
                "*Как оставить отзыв:*\n"
                "1. Найдите место через поиск\n"
                "2. Нажмите «✍️ Оставить отзыв»\n"
                "3. Оцените место от 1 до 5\n"
                "4. Напишите ваше мнение\n\n"
                "Ваши отзывы помогают другим пользователям!"
            )
            
            if isinstance(event, CallbackQuery):
                await message.edit_text(no_reviews_text, parse_mode="Markdown", reply_markup=get_back_keyboard())
            else:
                await message.answer(no_reviews_text, parse_mode="Markdown", reply_markup=get_back_keyboard())
            return
        
        # Формируем заголовок
        header_text = f"📝 *Ваши отзывы*\n\nВсего отзывов: *{total}*\n\n"
        
        if isinstance(event, CallbackQuery):
            await message.edit_text(header_text, parse_mode="Markdown")
        else:
            await message.answer(header_text, parse_mode="Markdown")
        
        # Показываем отзывы
        for i, review in enumerate(reviews[:10], 1):  # Ограничиваем показ 10 отзывами
            place_name = review.get("place_name", "Неизвестное место")
            rating = review.get("rating", 0)
            status = format_review_status(review.get("moderation_status", "pending"))
            date = format_date(review.get("created_at", ""))
            summary = review.get("summary", "")
            
            # Форматируем текст отзыва
            review_text = review.get("text", "")
            if len(review_text) > 100:
                review_text = review_text[:100] + "..."
            
            # Создаем сообщение об отзыве
            review_message = (
                f"*{i}. {place_name}*\n"
                f"⭐ Оценка: *{rating}/5*\n"
                f"📝 Статус: {status}\n"
                f"🕐 Дата: {date}\n"
            )
            
            if summary:
                review_message += f"📋 Кратко: {summary[:80]}...\n"
            
            review_message += f"💬 Отзыв: {review_text}"
            
            # Создаем кнопки для этого отзыва
            keyboard = get_review_keyboard(review)
            
            await message.answer(
                review_message,
                parse_mode="Markdown",
                reply_markup=keyboard
            )
        
        # Если отзывов больше, чем показали
        if total > len(reviews):
            more_text = f"\n📊 *И еще {total - len(reviews)} отзывов...*\nИспользуйте пагинацию для просмотра всех отзывов."
            
            # TODO: Добавить пагинацию
            pagination_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 В главное меню", callback_data="back_to_main")]
            ])
            
            await message.answer(more_text, parse_mode="Markdown", reply_markup=pagination_keyboard)
        else:
            # Кнопка возврата
            footer_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 В главное меню", callback_data="back_to_main")]
            ])
            
            await message.answer(
                "✅ *Все ваши отзывы загружены.*\nВыберите отзыв для управления.",
                parse_mode="Markdown",
                reply_markup=footer_keyboard
            )
            
    except Exception as e:
        logger.error(f"Ошибка показа отзывов пользователя: {e}")
        error_text = "❌ *Произошла ошибка при загрузке отзывов.*\n\nПопробуйте позже."
        
        if isinstance(event, CallbackQuery):
            await message.edit_text(error_text, parse_mode="Markdown", reply_markup=get_back_keyboard())
        else:
            await message.answer(error_text, parse_mode="Markdown", reply_markup=get_back_keyboard())

@router.callback_query(F.data.startswith("delete_review:"))
async def delete_review_prompt(callback: CallbackQuery):
    """Запрос подтверждения удаления отзыва"""
    try:
        review_id = callback.data.split(":")[1]
        
        # Получаем информацию об отзыве для подтверждения
        telegram_id = callback.from_user.id
        
        # TODO: Можно получить детали отзыва для показа в подтверждении
        # Пока используем общий текст
        
        await callback.message.edit_text(
            "🗑️ *Удаление отзыва*\n\n"
            "Вы уверены, что хотите удалить этот отзыв?\n\n"
            "⚠️ *Внимание:*\n"
            "• Отзыв будет удален безвозвратно\n"
            "• Рейтинг места будет пересчитан\n"
            "• Это действие нельзя отменить\n\n"
            "Подтвердите удаление:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_delete:{review_id}")],
                [InlineKeyboardButton(text="❌ Нет, отменить", callback_data="cancel_delete")]
            ])
        )
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка запроса удаления отзыва: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)

@router.callback_query(F.data.startswith("confirm_delete:"))
async def confirm_delete_review(callback: CallbackQuery):
    """Подтверждение удаления отзыва"""
    try:
        review_id = callback.data.split(":")[1]
        telegram_id = callback.from_user.id
        
        # Отправляем запрос на удаление
        response = await http_client.delete_review(review_id, telegram_id)
        
        if response and response.get("success"):
            await callback.message.edit_text(
                "✅ *Отзыв удален!*\n\n"
                "Отзыв успешно удален.\n"
                "Рейтинг места будет пересчитан.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📝 Мои отзывы", callback_data="my_reviews")],
                    [InlineKeyboardButton(text="🔙 В главное меню", callback_data="back_to_main")]
                ])
            )
        else:
            error_msg = response.get("detail", "Неизвестная ошибка") if response else "Ошибка сервера"
            await callback.message.edit_text(
                f"❌ *Не удалось удалить отзыв*\n\n"
                f"Ошибка: {error_msg}",
                parse_mode="Markdown",
                reply_markup=get_back_keyboard()
            )
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка удаления отзыва: {e}")
        await callback.message.edit_text(
            "❌ *Ошибка удаления отзыва*\n\n"
            "Попробуйте позже.",
            parse_mode="Markdown",
            reply_markup=get_back_keyboard()
        )
        await callback.answer()

@router.callback_query(F.data == "cancel_delete")
async def cancel_delete_review(callback: CallbackQuery):
    """Отмена удаления отзыва"""
    await callback.message.edit_text(
        "⏹ *Удаление отменено.*\n\n"
        "Отзыв не был удален.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📝 Мои отзывы", callback_data="my_reviews")],
            [InlineKeyboardButton(text="🔙 В главное меню", callback_data="back_to_main")]
        ])
    )
    await callback.answer()

@router.callback_query(F.data.startswith("goto_place:"))
async def goto_place(callback: CallbackQuery):
    """Переход к месту"""
    try:
        place_id = callback.data.split(":")[1]
        
        # Получаем информацию о месте
        place_info = await http_client.get_place(place_id)
        
        if not place_info:
            await callback.answer("❌ Место не найдено", show_alert=True)
            return
        
        rating = place_info.get("rating", 0.0)
        review_count = place_info.get("review_count", 0)
        address = place_info.get("address", "Адрес не указан")
        category = place_info.get("category", "other")
        description = place_info.get("description", "Описание отсутствует")
        
        # Безопасный срез описания
        if len(description) > 200:
            description = description[:200] + "..."
        
        # Эмодзи для категорий
        category_emoji = {
            "cafe": "☕",
            "restaurant": "🍽️",
            "park": "🌳",
            "museum": "🏛️",
            "cinema": "🎬",
            "theatre": "🎭",
            "art": "🎨"
        }.get(category, "📍")
        
        place_text = (
            f"📍 *{category_emoji} {place_info['name']}*\n\n"
            f"📝 {description}\n\n"
            f"⭐ Рейтинг: *{rating:.1f}/5* ({review_count} отзывов)\n"
            f"📍 Адрес: {address[:50]}{'...' if len(address) > 50 else ''}\n"
            f"🏷️ Категория: {category}"
        )
        
        from ..keyboards.inline import get_place_keyboard
        keyboard = get_place_keyboard(place_id)
        
        await callback.message.edit_text(
            place_text,
            parse_mode="Markdown",
            reply_markup=keyboard
        )
        
    except Exception as e:
        logger.error(f"Ошибка перехода к месту: {e}")
        await callback.answer("❌ Ошибка загрузки места", show_alert=True)
    
    await callback.answer()

def get_reviews_pagination_keyboard(
    current_page: int, 
    total_pages: int,
    telegram_id: int
) -> InlineKeyboardMarkup:
    """Клавиатура пагинации для отзывов"""
    buttons = []
    
    if total_pages > 1:
        row = []
        if current_page > 0:
            row.append(InlineKeyboardButton(
                text="◀️ Назад", 
                callback_data=f"reviews_page:{current_page-1}:{telegram_id}"
            ))
        
        row.append(InlineKeyboardButton(
            text=f"{current_page+1}/{total_pages}", 
            callback_data="current_page"
        ))
        
        if current_page < total_pages - 1:
            row.append(InlineKeyboardButton(
                text="Вперед ▶️", 
                callback_data=f"reviews_page:{current_page+1}:{telegram_id}"
            ))
        
        buttons.append(row)
    
    buttons.append([InlineKeyboardButton(text="🔙 В главное меню", callback_data="back_to_main")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)