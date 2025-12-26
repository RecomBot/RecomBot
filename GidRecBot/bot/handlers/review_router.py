# bot/handlers/review_router.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from ..states.review import ReviewStates
from ..keyboards.inline import get_rating_keyboard, get_place_keyboard
from ..utils.http_client import http_client
import logging

router = Router()
logger = logging.getLogger(__name__)

# Состояния для оставления отзыва
class ReviewForm(StatesGroup):
    place_id = State()
    rating = State()
    text = State()


@router.callback_query(F.data.startswith("review:"))
async def start_review(callback: CallbackQuery, state: FSMContext):
    """Начать процесс оставления отзыва"""
    place_id = callback.data.split(":")[1]
    
    # Проверяем, существует ли место
    try:
        place = await http_client.get_place(place_id)
        if not place:
            await callback.answer("❌ Место не найдено!")
            return
    except Exception as e:
        logger.error(f"Error getting place {place_id}: {e}")
        await callback.answer("❌ Ошибка при получении информации о месте")
        return
    
    # Сохраняем place_id в состоянии
    await state.update_data(place_id=place_id, place_name=place.get("name", "Место"))
    await state.set_state(ReviewForm.rating)
    
    await callback.message.edit_text(
        f"⭐ *Оцените «{place['name']}» от 1 до 5:*",
        reply_markup=get_rating_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(ReviewForm.rating, F.data.startswith("rate:"))
async def process_rating(callback: CallbackQuery, state: FSMContext):
    """Обработка оценки"""
    rating = int(callback.data.split(":")[1])
    await state.update_data(rating=rating)
    await state.set_state(ReviewForm.text)
    
    await callback.message.edit_text(
        "✍️ *Напишите отзыв (от 10 до 500 символов):*\n\n"
        "Опишите ваши впечатления, что понравилось или не понравилось, "
        "дайте советы другим посетителям.",
        parse_mode="Markdown"
    )
    await callback.answer()


@router.message(ReviewForm.text)
async def process_text(message: Message, state: FSMContext):
    """Обработка текста отзыва"""
    text = message.text.strip()
    
    # Валидация текста
    if len(text) < 10:
        await message.answer("❌ *Слишком коротко!*\nНапишите хотя бы 10 символов.", parse_mode="Markdown")
        return
    if len(text) > 500:
        await message.answer("❌ *Слишком длинно!*\nМаксимум 500 символов.", parse_mode="Markdown")
        return
    
    # Получаем данные из состояния
    data = await state.get_data()
    place_id = data.get("place_id")
    place_name = data.get("place_name", "Место")
    rating = data.get("rating")
    
    if not place_id or not rating:
        await message.answer("❌ Ошибка: данные отзыва не найдены. Начните заново.")
        await state.clear()
        return
    
    # Показываем индикатор загрузки
    temp_msg = await message.answer("📨 *Отправляю отзыв...*", parse_mode="Markdown")
    
    try:
        # Отправляем отзыв через API
        review = await http_client.create_review(
            tg_id=message.from_user.id,
            place_id=place_id,
            rating=rating,
            text=text
        )
        
        await temp_msg.delete()
        
        # Определяем статус модерации
        status = review.get("moderation_status", "pending")
        status_texts = {
            "approved": "✅ *Ваш отзыв опубликован!*",
            "pending": "⏳ *Ваш отзыв отправлен на модерацию.*\nОбычно это занимает несколько часов.",
            "flagged_by_llm": "⚠️ *Ваш отзыв проверяется системой.*\nМодератор рассмотрит его в ближайшее время."
        }
        
        status_msg = status_texts.get(status, "⏳ *Отзыв отправлен!*")
        
        await message.answer(
            f"{status_msg}\n\n"
            f"📍 *Место:* {place_name}\n"
            f"⭐ *Оценка:* {rating}/5\n"
            f"📝 *Отзыв:* {text[:100]}...\n\n"
            f"ID отзыва: `{review.get('id', '')}`",
            parse_mode="Markdown"
        )
        
        # Показываем информацию о месте снова
        try:
            place = await http_client.get_place(place_id)
            if place:
                rating_display = f"{place['rating']:.1f}⭐ ({place['rating_count']})"
                
                await message.answer(
                    f"📍 *{place['name']}*\n\n"
                    f"{place.get('description', '')}\n\n"
                    f"⭐ {rating_display}\n"
                    f"🏷️ {place.get('category', 'без категории')}\n"
                    f"📌 {place.get('address', 'Адрес не указан')}\n"
                    f"💰 Уровень цен: {'💲' * place.get('price_level', 2)}",
                    reply_markup=get_place_keyboard(place_id),
                    parse_mode="Markdown"
                )
        except Exception as e:
            logger.error(f"Error showing place after review: {e}")
        
    except Exception as e:
        await temp_msg.delete()
        logger.exception(f"❌ Ошибка создания отзыва: {e}")
        
        error_msg = str(e)
        if "уже оставляли отзыв" in error_msg:
            await message.answer(
                "❌ *Вы уже оставляли отзыв на это место!*\n\n"
                "Каждый пользователь может оставить только один отзыв на место.",
                parse_mode="Markdown"
            )
        elif "Пользователь не найден" in error_msg:
            await message.answer(
                "❌ *Вы не зарегистрированы!*\n\n"
                "Пожалуйста, сначала выполните команду `/start` для регистрации.",
                parse_mode="Markdown"
            )
        elif "Место не найдено" in error_msg:
            await message.answer(
                "❌ *Место не найдено!*\n\n"
                "Возможно, оно было удалено или деактивировано.",
                parse_mode="Markdown"
            )
        else:
            await message.answer(
                f"❌ *Ошибка при отправке отзыва:*\n`{error_msg[:100]}`\n\n"
                "Попробуйте позже или свяжитесь с поддержкой.",
                parse_mode="Markdown"
            )
    
    finally:
        await state.clear()


@router.callback_query(F.data == "cancel")
async def cancel_review(callback: CallbackQuery, state: FSMContext):
    """Отмена оставления отзыва"""
    await state.clear()
    await callback.message.edit_text("⏹ *Отзыв отменён.*", parse_mode="Markdown")
    await callback.answer()


@router.callback_query(F.data.startswith("place:"))
async def show_place_details(callback: CallbackQuery):
    """Показать детали места"""
    place_id = callback.data.split(":")[1]
    
    try:
        place = await http_client.get_place(place_id)
        if not place:
            await callback.message.edit_text("❌ *Место не найдено.*", parse_mode="Markdown")
            await callback.answer()
            return
        
        # Форматируем рейтинг
        rating = place.get("rating", 0)
        rating_count = place.get("rating_count", 0)
        rating_display = f"{rating:.1f}⭐ ({rating_count})"
        
        # Форматируем уровень цен
        price_level = place.get("price_level", 2)
        price_display = "💲" * price_level
        
        # Получаем отзывы для этого места
        reviews = await http_client.get_reviews_by_place(place_id, show_pending=False)
        
        await callback.message.edit_text(
            f"📍 *{place['name']}*\n\n"
            f"{place.get('description', '')}\n\n"
            f"⭐ *Рейтинг:* {rating_display}\n"
            f"🏷️ *Категория:* {place.get('category', 'без категории')}\n"
            f"📍 *Город:* {place.get('city', 'Не указан')}\n"
            f"📌 *Адрес:* {place.get('address', 'Адрес не указан')}\n"
            f"💰 *Уровень цен:* {price_display}\n\n"
            f"📝 *Отзывов:* {len(reviews)}\n"
            f"🔗 *Источник:* {place.get('source', 'пользователь')}\n"
            f"📅 *Добавлено:* {place.get('created_at', '')[:10]}",
            reply_markup=get_place_keyboard(place_id),
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.exception(f"Error showing place details: {e}")
        await callback.message.edit_text(
            "❌ *Не удалось загрузить информацию о месте.*\n"
            "Попробуйте позже.",
            parse_mode="Markdown"
        )
    
    await callback.answer()