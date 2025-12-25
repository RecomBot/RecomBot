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


async def show_places_page(message: Message, state: FSMContext):
    """Показывает страницу мест (3 за раз)"""
    data = await state.get_data()
    places = data.get("places", [])
    offset = data.get("offset", 0)
    query = data.get("query", "")
    location = data.get("location", "Moscow")

    page_places = places[offset:offset + 3]
    if not page_places:
        await message.answer("🔚 Больше нет рекомендаций.")
        await state.clear()
        return

    for place in page_places:
        rating = place.get("rating", 0.0)
        count = place.get("rating_count", 0)
        stars = "⭐" * int(rating) + ("½" if rating % 1 >= 0.5 else "")
        stars_text = f"{stars} {rating:.1f} ({count})"

        await message.answer(
            f"📍 *{place['name']}*\n"
            f"{place.get('description', '')}\n"
            f"⭐ {stars_text}\n"
            f"📌 {place.get('address', 'Адрес не указан')}",
            reply_markup=get_place_keyboard(place["id"]),
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
            f"📍 Рекомендации для *{location}* по запросу:\n_«{query}»_",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[buttons]),
            parse_mode="Markdown"
        )


# 🤖 Основной хендлер: любой текст → LLM + пагинация
@router.message(
    F.text,
    StateFilter(default_state)  # ← Только если НЕ в FSM (не в отзыве)
)
async def handle_natural_query(message: Message, state: FSMContext):
    text = message.text.strip()
    if text.startswith("/") or text in ["🎯 Получить рекомендацию", "❓ Помощь", "⏹ Отмена"]:
        return

    temp_msg = await message.answer("🧠 *Анализирую запрос...*", parse_mode="Markdown")

    try:
        # Получаем пользователя (регистрируем, если нужно)
        user = await http_client.get_user_by_tg_id(message.from_user.id)
        location = user.get("preferences", {}).get("city", "Moscow")

        # Выполняем поиск или LLM-рекомендацию
        if "хочу" in text.lower() or "нужно" in text.lower() or "ищу" in text.lower():
            # Natural language → LLM
            response = await http_client.recommend(
                tg_id=message.from_user.id,
                query=text
            )
        else:
            # Простой поиск → /search
            response = await http_client.search_places(
                tg_id=message.from_user.id,
                query=text
            )

        # Сохраняем в состояние
        await state.update_data(
            places=response.get("places", []),
            query=text,
            offset=0,
            location=location
        )

        await temp_msg.delete()
        await message.answer(
            f"✅ *Вот что подойдёт вам в {location}:*",
            parse_mode="Markdown"
        )
        await show_places_page(message, state)

    except Exception as e:
        logger.exception("❌ Ошибка обработки запроса")
        await temp_msg.edit_text(
            "❌ Не удалось обработать запрос. Попробуйте переформулировать.",
            parse_mode="Markdown"
        )


# 📖 Пагинация: Назад
@router.callback_query(F.data == "page:prev")
async def page_prev(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    data["offset"] = max(0, data["offset"] - 3)
    await state.update_data(offset=data["offset"])
    await callback.message.delete()
    await show_places_page(callback.message, state)
    await callback.answer()


# 📖 Пагинация: Ещё
@router.callback_query(F.data == "page:next")
async def page_next(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    data["offset"] += 3
    await state.update_data(offset=data["offset"])
    await callback.message.delete()
    await show_places_page(callback.message, state)
    await callback.answer()


# ℹ️ Кнопка «Подробнее» (place:123)
@router.callback_query(F.data.startswith("place:"))
async def show_place_details(callback: CallbackQuery):
    place_id = callback.data.split(":")[1]

    # Запросим детали из бэкенда (если нужно) или покажем из кэша
    # Пока используем mock (в продакшене — GET /api/v1/places/{id})
    MOCK_PLACES = {
        "1": {
            "name": "Кофейня у Патриарших",
            "description": "Уютное место с домашней выпечкой и ароматным кофе.",
            "rating": 4.7,
            "rating_count": 23,
            "address": "Тверская, 12"
        },
        "2": {
            "name": "Музей современного искусства",
            "description": "Интерактивные выставки и лекции от художников.",
            "rating": 4.5,
            "rating_count": 41,
            "address": "Петровка, 25"
        },
        "3": {
            "name": "Парк Горького",
            "description": "Зелёная зона с прокатом велосипедов и летней верандой.",
            "rating": 4.8,
            "rating_count": 156,
            "address": "Крымский Вал, 9"
        }
    }
    place = MOCK_PLACES.get(place_id)
    if not place:
        await callback.message.edit_text("❌ Место не найдено.")
        await callback.answer()
        return

    rating = place["rating"]
    stars = "⭐" * int(rating) + ("½" if rating % 1 >= 0.5 else "")
    stars_text = f"{stars} {rating:.1f} ({place['rating_count']})"

    await callback.message.edit_text(
        f"📍 *{place['name']}*\n\n"
        f"{place['description']}\n\n"
        f"⭐ {stars_text}\n"
        f"📌 {place['address']}",
        reply_markup=get_place_keyboard(place_id),
        parse_mode="Markdown"
    )
    await callback.answer()