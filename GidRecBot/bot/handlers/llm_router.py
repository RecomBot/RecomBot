# bot/handlers/llm_router.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import default_state
from ..utils.http_client import http_client
from ..keyboards.inline import get_place_keyboard
import logging

router = Router()
logger = logging.getLogger(__name__)

# --- Обработка ЛЮБОГО текста (natural language) ---
# ✅ Работает ТОЛЬКО если НЕ в FSM (например, не в процессе отзыва)
@router.message(
    F.text,
    StateFilter(default_state)  # ← КЛЮЧЕВОЙ ФИЛЬТР
)
async def handle_natural_query(message: Message):
    """Обрабатывает ЛЮБОЙ текст → отправляет в LLM"""
    text = message.text.strip()
    
    # Пропускаем служебные команды и кнопки (уже обрабатываются в register_router.py)
    if text.startswith("/") or text in [
        "🎯 Получить рекомендацию",
        "❓ Справка",
        "👤 Мой профиль"
    ]:
        return
    
    # Показываем "думает..."
    temp_msg = await message.answer("🧠 *Анализирую запрос...*", parse_mode="Markdown")
    
    try:
        # Получаем профиль
        user = await http_client.get_user_by_tg_id(message.from_user.id)
        
        # Отправляем в LLM
        response = await http_client.recommend(
            user_id=user["id"],
            query=text  # ← ПЕРЕДАЁМ ПОЛЬЗОВАТЕЛЬСКУЮ ФРАЗУ
        )
        
        # Редактируем "думает..." на результат
        await temp_msg.edit_text(
            f"✅ *Вот что подойдёт вам в {user.get('location', 'Moscow')}:*",
            parse_mode="Markdown"
            reply_markup=COMMON_KEYBOARD
        )
        
        # Показываем места
        for place in response.get("places", [])[:3]:
            rating = place.get("rating_avg", 0.0)
            count = place.get("rating_count", 0)
            full_stars = int(rating)
            half_star = "½" if rating - full_stars >= 0.5 else ""
            stars_text = f"{'⭐' * full_stars}{half_star} {rating:.1f} ({count})"
            
            await message.answer(
                f"📍 *{place['name']}*\n"
                f"{place['description']}\n"
                f"⭐ {stars_text}\n"
                f"📌 {place['address']}",
                reply_markup=get_place_keyboard(place["id"]),
                parse_mode="Markdown",
                disable_web_page_preview=True
            )
            
    except Exception as e:
        logger.exception("❌ Ошибка обработки запроса")
        await temp_msg.edit_text(
            "❌ Не удалось обработать запрос. Попробуйте переформулировать.",
            parse_mode="Markdown"
        )

# --- Кнопка «Подробнее» (place:123) — из review_router.py, но здесь для полноты ---
@router.callback_query(F.data.startswith("place:"))
async def show_place_details(callback: CallbackQuery):
    place_id = int(callback.data.split(":")[1])
    
    # 🎯 MOCK-данные (временно)
    MOCK_PLACES = {
        1: {"name": "Кофейня у Патриарших", "description": "Уютное место с домашней выпечкой и ароматным кофе.", "rating_avg": 4.7, "rating_count": 23, "address": "Тверская, 12"},
        2: {"name": "Музей современного искусства", "description": "Интерактивные выставки и лекции от художников.", "rating_avg": 4.5, "rating_count": 41, "address": "Петровка, 25"},
        3: {"name": "Парк Горького", "description": "Зелёная зона с прокатом велосипедов и летней верандой.", "rating_avg": 4.8, "rating_count": 156, "address": "Крымский Вал, 9"}
    }
    
    place = MOCK_PLACES.get(place_id)
    if not place:
        await callback.message.edit_text("❌ Место не найдено.")
        await callback.answer()
        return
    
    full_stars = int(place["rating_avg"])
    half_star = "½" if place["rating_avg"] - full_stars >= 0.5 else ""
    stars_text = f"{'⭐' * full_stars}{half_star} {place['rating_avg']:.1f} ({place['rating_count']})"
    
    text = (
        f"📍 *{place['name']}*\n\n"
        f"{place['description']}\n\n"
        f"⭐ {stars_text}\n"
        f"📌 {place['address']}"
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=get_place_keyboard(place_id),
        parse_mode="Markdown",
        disable_web_page_preview=True
    )
    await callback.answer()