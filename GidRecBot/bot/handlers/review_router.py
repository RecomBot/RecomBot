# bot/handlers/review_router.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from ..states.review import ReviewStates
from ..keyboards.inline import get_rating_keyboard, get_place_keyboard
from ..utils.http_client import http_client
import logging

router = Router()
logger = logging.getLogger(__name__)

@router.callback_query(F.data.startswith("review:"))
async def start_review(callback: CallbackQuery, state: FSMContext):
    place_id = callback.data.split(":")[1]
    await state.update_data(place_id=place_id)
    await state.set_state(ReviewStates.rating)
    await callback.message.answer(
        "⭐ *Оцените место от 1 до 5:*",
        reply_markup=get_rating_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()

@router.callback_query(ReviewStates.rating, F.data.startswith("rate:"))
async def process_rating(callback: CallbackQuery, state: FSMContext):
    rating = int(callback.data.split(":")[1])
    await state.update_data(rating=rating)
    await state.set_state(ReviewStates.text)
    await callback.message.answer(
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
    tg_id = message.from_user.id

    try:
        logger.info(f"📩 Отзыв: place={place_id}, rating={rating}, text='{text[:20]}...'")
        await http_client.create_review(
            tg_id=tg_id,
            place_id=place_id,
            rating=rating,
            text=text
        )
        await message.answer(
            "✅ *Отзыв отправлен на модерацию!*",
            parse_mode="Markdown"
        )
        # Показываем карточку места
        await message.answer(
            f"📍 *Место:* ID `{place_id}`\n"
            f"⭐ Оценка: {rating}\n"
            f"📝 Текст: _{text[:50]}..._",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
            ]),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.exception("❌ Ошибка отправки отзыва")
        await message.answer("❌ Ошибка отправки отзыва.", parse_mode="Markdown")
    await state.clear()

@router.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery):
    await callback.message.answer(
        "✅ Вы вернулись в главное меню.\n\n"
        "Напишите, что вам хочется — например:\n"
        "• _«Хочу сходить на концерт»_\n"
        "• _«Нужно уютное кафе»_\n"
        "• _«Что посмотреть в центре?»_",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎯 Получить рекомендацию", callback_data="ask")],
            [
                InlineKeyboardButton(text="❓ Помощь", callback_data="help"),
                InlineKeyboardButton(text="👤 Мой профиль", callback_data="me")
            ]
        ]),
        parse_mode="Markdown"
    )
    await callback.answer()