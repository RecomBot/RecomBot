# bot/handlers/review_router.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from ..states.review import ReviewStates
from ..keyboards.inline import get_rating_keyboard, get_place_keyboard
import logging

router = Router()
logger = logging.getLogger(__name__)

MOCK_PLACES = {
    1: {
        "name": "Кофейня у Патриарших",
        "description": "Уютное место с домашней выпечкой и ароматным кофе.",
        "rating_avg": 4.7,
        "rating_count": 23,
        "address": "Тверская, 12",
        "category": "cafe"
    },
    2: {
        "name": "Музей современного искусства",
        "description": "Интерактивные выставки и лекции от художников.",
        "rating_avg": 4.5,
        "rating_count": 41,
        "address": "Петровка, 25",
        "category": "museum"
    },
    3: {
        "name": "Парк Горького",
        "description": "Зелёная зона с прокатом велосипедов и летней верандой.",
        "rating_avg": 4.8,
        "rating_count": 156,
        "address": "Крымский Вал, 9",
        "category": "park"
    }
}

@router.callback_query(F.data.startswith("review:"))
async def start_review(callback: CallbackQuery, state: FSMContext):
    place_id = int(callback.data.split(":")[1])
    await state.update_data(place_id=place_id)
    await state.set_state(ReviewStates.rating)
    await callback.message.edit_text(
        "⭐ *Оцените место от 1 до 5:*",
        reply_markup=get_rating_keyboard(),
        parse_mode="Markdown"
        reply_markup=COMMON_KEYBOARD
    )
    await callback.answer()

@router.callback_query(ReviewStates.rating, F.data.startswith("rate:"))
async def process_rating(callback: CallbackQuery, state: FSMContext):
    rating = int(callback.data.split(":")[1])
    await state.update_data(rating=rating)
    await state.set_state(ReviewStates.text)
    await callback.message.edit_text(
        "✍️ *Напишите отзыв (от 10 до 300 символов):*",
        parse_mode="Markdown"
    )
    await callback.answer()

@router.message(ReviewStates.text)
async def process_text(message: Message, state: FSMContext):
    text = message.text.strip()
    if len(text) < 10:
        await message.answer("❌ Слишком коротко! Напишите хотя бы 10 символов.")
        return
    if len(text) > 300:
        await message.answer("❌ Слишком длинно! Максимум 300 символов.")
        return
    
    data = await state.get_data()
    place_id = data["place_id"]
    rating = data["rating"]
    
    try:
        logger.info(f"📩 Mock-отзыв: place={place_id}, rating={rating}, text='{text[:20]}...'")
        await message.answer("✅ *Отзыв отправлен на модерацию!*", parse_mode="Markdown")
        
        # ✅ Показываем место + кнопка «Назад»
        place = MOCK_PLACES.get(place_id)
        if not place:
            await message.answer("❌ Место не найдено.")
        else:
            full_stars = int(place["rating_avg"])
            half_star = "½" if place["rating_avg"] - full_stars >= 0.5 else ""
            stars_text = f"{'⭐' * full_stars}{half_star} {place['rating_avg']:.1f} ({place['rating_count']})"
            
            await message.answer(
                f"📍 *{place['name']}*\n\n{place['description']}\n\n⭐ {stars_text}\n📌 {place['address']}",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")],
                    [InlineKeyboardButton(text="📝 Оставить отзыв", callback_data=f"review:{place_id}")]
                ]),
                parse_mode="Markdown"
            )
    except Exception as e:
        logger.exception("❌ Ошибка в /review")
        await message.answer("❌ Ошибка отправки отзыва.", parse_mode="Markdown")
    await state.clear()

@router.callback_query(F.data == "cancel")
async def cancel_review(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("⏹ Отзыв отменён.")
    await callback.answer()

@router.callback_query(F.data.startswith("place:"))
async def show_place_details(callback: CallbackQuery):
    place_id = int(callback.data.split(":")[1])
    place = MOCK_PLACES.get(place_id)
    if not place:
        await callback.message.edit_text("❌ Место не найдено.")
        await callback.answer()
        return
    
    full_stars = int(place["rating_avg"])
    half_star = "½" if place["rating_avg"] - full_stars >= 0.5 else ""
    stars_text = f"{'⭐' * full_stars}{half_star} {place['rating_avg']:.1f} ({place['rating_count']})"
    
    await callback.message.edit_text(
        f"📍 *{place['name']}*\n\n{place['description']}\n\n⭐ {stars_text}\n📌 {place['address']}",
        reply_markup=get_place_keyboard(place_id),
        parse_mode="Markdown"
    )
    await callback.answer()

# 🎯 Обработчик «Назад» (чтобы работал из отзыва)
@router.callback_query(F.data == "back_to_main")
async def back_to_main_from_review(callback: CallbackQuery):
    await callback.message.edit_text(
        "✅ Вы вернулись в главное меню.\n\n"
        "Напишите, что вам хочется — например:\n"
        "• _«Хочу сходить на концерт»_\n"
        "• _«Нужно уютное кафе»_\n"
        "• _«Что посмотреть в центре?»_\n\n"
        "Или воспользуйтесь кнопками ниже:",
        parse_mode="Markdown",
        reply_markup=MAIN_INLINE_KEYBOARD
    )
    await callback.answer()