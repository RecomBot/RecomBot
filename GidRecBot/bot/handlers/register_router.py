# bot/handlers/register_router.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from ..keyboards.inline import get_location_keyboard
from ..utils.http_client import http_client
import logging

router = Router()
logger = logging.getLogger(__name__)

class RegisterStates(StatesGroup):
    location = State()

MAIN_INLINE_KEYBOARD = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="🎯 Получить рекомендацию", callback_data="ask")],
        [
            InlineKeyboardButton(text="❓ Справка", callback_data="help"),
            InlineKeyboardButton(text="👤 Мой профиль", callback_data="me")
        ]
    ]
)

BACK_KEYBOARD = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
    ]
)

@router.message(Command("start", ignore_mention=True))
async def cmd_start(message: Message, state: FSMContext):
    await state.set_state(RegisterStates.location)
    await message.answer(
        "👋 Привет! Я — ваш персональный гид по местам отдыха.\n\n"
        "📍 Чтобы я знал, где искать — укажите, пожалуйста, ваш город:",
        reply_markup=get_location_keyboard()
    )

@router.callback_query(RegisterStates.location, F.data.startswith("loc:"))
async def process_location(callback: CallbackQuery, state: FSMContext):
    location_map = {
        "moscow": "Moscow",
        "saint-petersburg": "Saint Petersburg",
        "kazan": "Kazan",
        "ekaterinburg": "Yekaterinburg"
    }
    code = callback.data.split(":")[1]
    location = location_map.get(code, "Moscow")
    
    try:
        user = await http_client.register_user(
            tg_id=callback.from_user.id,
            location=location
        )
        logger.info(f"✅ Пользователь {callback.from_user.id} зарегистрирован в {location}")
        await state.clear()
        
        await callback.message.edit_text(
            f"✅ Отлично! Теперь я знаю, что вы в *{location}*.\n\n"
            "Напишите, что вам хочется — например:\n"
            "• _«Хочу сходить на концерт»_\n"
            "• _«Нужно уютное кафе»_\n"
            "• _«Что посмотреть в центре?»_\n\n"
            "Или воспользуйтесь кнопками ниже:",
            parse_mode="Markdown",
            reply_markup=MAIN_INLINE_KEYBOARD
            reply_markup=COMMON_KEYBOARD
        )
    except Exception as e:
        logger.exception("❌ Ошибка регистрации")
        await callback.message.edit_text(
            "❌ Не удалось сохранить профиль. Попробуйте позже.",
            parse_mode="Markdown"
        )
    await callback.answer()

@router.callback_query(F.data == "help")
async def handle_help_button(callback: CallbackQuery):
    await callback.message.edit_text(
        "📘 *Как мной пользоваться?*\n\n"
        "• Просто напишите, что вам хочется:\n"
        "  — _«Хочу сходить на выставку»_\n"
        "  — _«Нужно недорого поесть»_\n"
        "  — _«Что посмотреть в Питере?»_\n\n"
        "• Или используйте кнопки:\n"
        "  🎯 — получить рекомендацию\n"
        "  👤 — посмотреть профиль\n\n"
        "Я подберу лучшие варианты специально для вас! 😊",
        parse_mode="Markdown",
        reply_markup=BACK_KEYBOARD
    )
    await callback.answer()

@router.callback_query(F.data == "me")
async def handle_profile_button(callback: CallbackQuery):
    try:
        user = await http_client.get_user_by_tg_id(callback.from_user.id)
        if not user or not isinstance(user, dict):
            raise ValueError("Invalid user data")
        
        location = user.get("location", "Moscow")
        await callback.message.edit_text(
            f"👤 *Ваш профиль*\n\n"
            f"🆔 ID: `{user['id']}`\n"
            f"📍 Город: *{location}*\n"
            f"📝 Отзывов: *0*\n\n"
            "Чтобы изменить город — напишите `/start`.",
            parse_mode="Markdown",
            reply_markup=BACK_KEYBOARD
        )
    except Exception as e:
        logger.exception("❌ Ошибка профиля")
        await callback.message.edit_text(
            "❌ Не удалось загрузить профиль. Попробуйте позже.",
            parse_mode="Markdown",
            reply_markup=BACK_KEYBOARD
        )
    await callback.answer()

@router.callback_query(F.data == "ask")
async def handle_recommend_button(callback: CallbackQuery):
    await callback.message.edit_text(
        "🎯 *Напишите, что вам хочется — например:*\n"
        "• _«Хочу сходить на концерт»_\n"
        "• _«Нужно уютное кафе»_\n"
        "• _«Что посмотреть в центре?»_",
        parse_mode="Markdown",
        reply_markup=BACK_KEYBOARD
    )
    await callback.answer()

@router.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery):
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