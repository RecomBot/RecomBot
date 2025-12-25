# bot/handlers/register_router.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton
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

# 🎯 Постоянная клавиатура (внизу экрана)
COMMON_KEYBOARD = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="❓ Помощь"), KeyboardButton(text="⏹ Отмена")]
    ],
    resize_keyboard=True,
    one_time_keyboard=False
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
        user = await http_client.register_or_get_user(
            tg_id=callback.from_user.id,
            location=location
        )
        logger.info(f"✅ Пользователь {callback.from_user.id} зарегистрирован в {location}")
        await state.clear()
        
        # ✅ Используем message.answer() + reply_markup=COMMON_KEYBOARD
        await callback.message.answer(
            f"✅ Отлично! Теперь я знаю, что вы в *{location}*.\n\n"
            "Напишите, что вам хочется — например:\n"
            "• _«Хочу сходить на концерт»_\n"
            "• _«Нужно уютное кафе»_\n"
            "• _«Что посмотреть в центре?»_",
            parse_mode="Markdown",
            reply_markup=COMMON_KEYBOARD  # ← ТОЛЬКО ОДИН reply_markup
        )
        await callback.answer()
    except Exception as e:
        logger.exception("❌ Ошибка регистрации")
        await callback.message.answer(
            "❌ Не удалось сохранить профиль. Попробуйте позже.",
            parse_mode="Markdown",
            reply_markup=COMMON_KEYBOARD
        )
        await callback.answer()

# --- Кнопка [❓ Помощь] ---
@router.message(F.text == "❓ Помощь")
async def handle_help_reply(message: Message):
    await message.answer(
        "📘 *Как мной пользоваться?*\n\n"
        "• Просто напишите, что вам хочется:\n"
        "  — _«Хочу сходить на выставку»_\n"
        "  — _«Нужно недорого поесть»_\n"
        "  — _«Что посмотреть в Питере?»_\n\n"
        "• Или используйте команды:\n"
        "  `/start` — изменить город\n"
        "  `/me` — посмотреть профиль\n\n"
        "Я подберу лучшие варианты специально для вас! 😊",
        parse_mode="Markdown",
        reply_markup=COMMON_KEYBOARD
    )

# --- Кнопка [⏹ Отмена] ---
@router.message(F.text == "⏹ Отмена")
async def handle_cancel_reply(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state:
        await state.clear()
        await message.answer("⏹ Действие отменено.", reply_markup=COMMON_KEYBOARD)
    else:
        await message.answer("⏹ Нечего отменять.", reply_markup=COMMON_KEYBOARD)

# --- /me (профиль) ---
@router.message(Command("me", ignore_mention=True))
async def handle_profile_command(message: Message):
    try:
        user = await http_client.get_user_by_tg_id(message.from_user.id)
        location = user.get("preferences", {}).get("city", "Moscow")
        await message.answer(
            f"👤 *Ваш профиль*\n\n"
            f"🆔 ID: `{user['id']}`\n"
            f"📍 Город: *{location}*\n"
            f"📝 Отзывов: *0*\n\n"
            "Чтобы изменить город — напишите `/start`.",
            parse_mode="Markdown",
            reply_markup=COMMON_KEYBOARD
        )
    except Exception as e:
        logger.exception("❌ Ошибка профиля")
        await message.answer(
            "❌ Не удалось загрузить профиль.",
            parse_mode="Markdown",
            reply_markup=COMMON_KEYBOARD
        )