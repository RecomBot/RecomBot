# bot/handlers/llm_router.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import default_state
from ..utils.http_client import http_client
from ..keyboards.inline import get_place_keyboard
import logging

router = Router()
logger = logging.getLogger(__name__)


async def show_places_page(message: Message, state: FSMContext, new_search: bool = False):
    """Показать страницу мест (3 за раз)"""
    data = await state.get_data()
    places = data.get("places", [])
    offset = data.get("offset", 0)
    query = data.get("query", "")
    location = data.get("location", "Moscow")
    
    page_places = places[offset:offset + 3]
    if not page_places:
        await message.answer("🔚 *Больше нет рекомендаций.*", parse_mode="Markdown")
        if new_search:
            await state.clear()
        return
    
    # Показываем места
    for idx, place in enumerate(page_places, 1):
        place_id = place.get("id", "")
        rating = place.get("rating", 0.0)
        count = place.get("rating_count", 0)
        price_level = place.get("price_level", 2)
        
        # Форматируем рейтинг
        stars = "⭐" * int(rating) + ("½" if rating % 1 >= 0.5 else "")
        stars_text = f"{stars} {rating:.1f} ({count})"
        
        # Форматируем уровень цен
        price_display = "💲" * price_level
        
        # Формируем сообщение
        place_text = (
            f"📍 *{place['name']}*\n\n"
            f"{place.get('description', '')[:100]}...\n\n"
            f"⭐ {stars_text}\n"
            f"🏷️ {place.get('category', 'без категории')}\n"
            f"💰 {price_display}\n"
            f"📌 {place.get('address', 'Адрес не указан')[:50]}"
        )
        
        await message.answer(
            place_text,
            reply_markup=get_place_keyboard(place_id),
            parse_mode="Markdown"
        )
    
    # Пагинация
    buttons = []
    if offset > 0:
        buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data="page:prev"))
    if offset + 3 < len(places):
        buttons.append(InlineKeyboardButton(text="➡️ Ещё", callback_data="page:next"))
    
    if buttons:
        await message.answer(
            f"📍 *Рекомендации для {location}*\n"
            f"🔍 *Запрос:* «{query}»\n"
            f"📋 *Найдено мест:* {len(places)}\n"
            f"📄 *Страница:* {offset//3 + 1}/{(len(places) + 2)//3}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[buttons]),
            parse_mode="Markdown"
        )
    
    if new_search:
        await message.answer(
            "💡 *Что дальше?*\n"
            "• Нажмите на кнопку '✍️ Оставить отзыв' под понравившимся местом\n"
            "• Напишите новый запрос для поиска\n"
            "• Используйте кнопки пагинации для просмотра других мест",
            parse_mode="Markdown"
        )


# 🤖 Основной хендлер: любой текст → LLM + пагинация
@router.message(
    F.text,
    StateFilter(default_state)  # ← Только если НЕ в FSM (не в отзыве)
)
async def handle_natural_query(message: Message, state: FSMContext):
    """Обработка естественного языка запроса"""
    text = message.text.strip()
    
    # Игнорируем команды и кнопки
    if text.startswith("/") or text in ["🎯 Получить рекомендацию", "❓ Помощь", "⏹ Отмена"]:
        return
    
    temp_msg = await message.answer("🧠 *Анализирую ваш запрос...*", parse_mode="Markdown")
    
    try:
        # 1. Получаем или регистрируем пользователя
        try:
            user = await http_client.get_user_by_tg_id(message.from_user.id)
        except:
            # Пользователь не найден, предлагаем зарегистрироваться
            await temp_msg.delete()
            await message.answer(
                "👋 *Добро пожаловать!*\n\n"
                "Похоже, вы здесь впервые. Пожалуйста, выполните команду `/start` "
                "для регистрации и выбора города.",
                parse_mode="Markdown"
            )
            return
        
        location = user.get("preferences", {}).get("city", "Moscow")
        username = message.from_user.username or message.from_user.first_name or "Пользователь"
        
        # 2. Определяем тип запроса и получаем рекомендации
        if any(word in text.lower() for word in ["хочу", "нужно", "ищу", "посоветуй", "рекомендуй", "где"]):
            # Natural language → LLM рекомендации
            response = await http_client.recommend(
                tg_id=message.from_user.id,
                query=text,
                limit=10
            )
            recommendation_text = response.get("text", "")
            places = response.get("places", [])
        else:
            # Простой поиск
            response = await http_client.search_places(
                tg_id=message.from_user.id,
                query=text,
                limit=10
            )
            recommendation_text = response.get("text", f"Результаты поиска по запросу «{text}»")
            places = response.get("places", [])
        
        await temp_msg.delete()
        
        if not places:
            await message.answer(
                f"❌ *По вашему запросу ничего не найдено.*\n\n"
                f"Попробуйте:\n"
                f"• Уточнить запрос (например, «кофе в центре»)\n"
                f"• Изменить город (сейчас: {location})\n"
                f"• Использовать другие ключевые слова",
                parse_mode="Markdown"
            )
            return
        
        # 3. Показываем LLM рекомендацию (если есть)
        if recommendation_text and len(recommendation_text) > 20:
            await message.answer(
                f"💬 *Рекомендация для {username}:*\n\n{recommendation_text}",
                parse_mode="Markdown"
            )
        
        # 4. Сохраняем в состояние для пагинации
        await state.update_data(
            places=places,
            query=text,
            offset=0,
            location=location
        )
        
        # 5. Показываем первую страницу
        await show_places_page(message, state, new_search=True)
        
    except Exception as e:
        await temp_msg.delete()
        logger.exception(f"❌ Ошибка обработки запроса: {e}")
        
        error_msg = str(e)
        if "API error" in error_msg:
            await message.answer(
                "❌ *Сервис рекомендаций временно недоступен.*\n\n"
                "Попробуйте позже или используйте простой поиск.",
                parse_mode="Markdown"
            )
        else:
            await message.answer(
                f"❌ *Не удалось обработать запрос:*\n`{error_msg[:100]}`\n\n"
                "Попробуйте переформулировать запрос или обратитесь в поддержку.",
                parse_mode="Markdown"
            )


# 📖 Пагинация: Назад
@router.callback_query(F.data == "page:prev")
async def page_prev(callback: CallbackQuery, state: FSMContext):
    """Предыдущая страница"""
    data = await state.get_data()
    data["offset"] = max(0, data["offset"] - 3)
    await state.update_data(offset=data["offset"])
    
    await callback.message.delete()
    await show_places_page(callback.message, state)
    await callback.answer("⬅️ Предыдущая страница")


# 📖 Пагинация: Ещё
@router.callback_query(F.data == "page:next")
async def page_next(callback: CallbackQuery, state: FSMContext):
    """Следующая страница"""
    data = await state.get_data()
    data["offset"] += 3
    await state.update_data(offset=data["offset"])
    
    await callback.message.delete()
    await show_places_page(callback.message, state)
    await callback.answer("➡️ Следующая страница")


# ℹ️ Кнопка «Подробнее» уже обрабатывается в review_router.py