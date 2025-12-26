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
    """Команда /start - начало регистрации"""
    await state.set_state(RegisterStates.location)
    
    username = message.from_user.username or message.from_user.first_name or "друг"
    
    await message.answer(
        f"👋 *Привет, {username}!*\n\n"
        "Я — ваш персональный гид по местам отдыха и развлечениям.\n\n"
        "📍 Чтобы подбирать лучшие места именно для вас, укажите, пожалуйста, ваш город:",
        reply_markup=get_location_keyboard(),
        parse_mode="Markdown"
    )


@router.callback_query(RegisterStates.location, F.data.startswith("loc:"))
async def process_location(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора города"""
    location_map = {
        "moscow": "Moscow",
        "saint-petersburg": "Saint Petersburg",
        "kazan": "Kazan",
        "ekaterinburg": "Yekaterinburg"
    }
    
    code = callback.data.split(":")[1]
    location = location_map.get(code, "Moscow")
    username = callback.from_user.username or callback.from_user.first_name or f"user_{callback.from_user.id}"
    
    try:
        # Регистрируем пользователя через API
        user = await http_client.register_user(
            tg_id=callback.from_user.id,
            location=location,
            username=username
        )
        
        logger.info(f"✅ Пользователь {callback.from_user.id} зарегистрирован в {location}")
        await state.clear()
        
        await callback.message.edit_text(
            f"✅ *Отлично, {username}!*\n\n"
            f"Теперь я знаю, что вы в *{location}*.\n\n"
            "📝 *Как пользоваться ботом:*\n"
            "• Просто напишите, что вам хочется\n"
            "• Например: _«Хочу сходить на концерт»_\n"
            "• Или: _«Нужно уютное кафе»_\n"
            "• Или: _«Что посмотреть в центре?»_\n\n"
            "Я подберу лучшие варианты специально для вас! 😊\n\n"
            "Или воспользуйтесь кнопками ниже:",
            parse_mode="Markdown",
            reply_markup=MAIN_INLINE_KEYBOARD
        )
        
    except Exception as e:
        logger.exception(f"❌ Ошибка регистрации пользователя: {e}")
        
        await callback.message.edit_text(
            "❌ *Не удалось сохранить профиль.*\n\n"
            "Пожалуйста, попробуйте позже или обратитесь в поддержку.\n\n"
            f"Ошибка: `{str(e)[:100]}`",
            parse_mode="Markdown"
        )
    
    await callback.answer()


@router.callback_query(F.data == "help")
async def handle_help_button(callback: CallbackQuery):
    """Кнопка помощи"""
    await callback.message.edit_text(
        "📘 *Как мной пользоваться?*\n\n"
        "🔍 *Поиск и рекомендации:*\n"
        "• Просто напишите, что вам хочется\n"
        "• Например: _«Хочу сходить на выставку»_\n"
        "• Или: _«Нужно недорого поесть»_\n"
        "• Или: _«Что посмотреть в центре?»_\n\n"
        "⭐ *Отзывы:*\n"
        "• Нажмите «✍️ Оставить отзыв» под понравившимся местом\n"
        "• Оцените место от 1 до 5 звезд\n"
        "• Напишите отзыв (от 10 до 500 символов)\n"
        "• Отзыв пройдет модерацию и будет опубликован\n\n"
        "👤 *Профиль:*\n"
        "• Просмотр вашей информации\n"
        "• История ваших отзывов\n"
        "• Смена города через `/start`\n\n"
        "🎯 *Кнопки:*\n"
        "• 🎯 — получить рекомендацию\n"
        "• 👤 — посмотреть профиль\n\n"
        "Я подберу лучшие варианты специально для вас! 😊",
        parse_mode="Markdown",
        reply_markup=BACK_KEYBOARD
    )
    await callback.answer()


@router.callback_query(F.data == "me")
async def handle_profile_button(callback: CallbackQuery):
    """Кнопка профиля"""
    try:
        # Получаем информацию о пользователе
        user = await http_client.get_user_by_tg_id(callback.from_user.id)
        
        if not user:
            raise ValueError("Пользователь не найден")
        
        location = user.get("preferences", {}).get("city", "Moscow")
        username = user.get("username", f"user_{callback.from_user.id}")
        role = user.get("role", "user")
        
        # Получаем отзывы пользователя (нужен отдельный endpoint)
        # Пока используем заглушку
        reviews_count = "N/A"
        
        role_emoji = {
            "user": "👤",
            "moderator": "🛡️",
            "admin": "👑"
        }.get(role, "👤")
        
        await callback.message.edit_text(
            f"{role_emoji} *Ваш профиль*\n\n"
            f"👤 *Имя:* {username}\n"
            f"🆔 *ID:* `{user.get('id', 'N/A')}`\n"
            f"📍 *Город:* *{location}*\n"
            f"🎭 *Роль:* {role}\n"
            f"📝 *Отзывов:* *{reviews_count}*\n"
            f"✅ *Статус:* {'Активен' if user.get('is_active', True) else 'Неактивен'}\n"
            f"📅 *Регистрация:* {user.get('created_at', 'N/A')[:10]}\n\n"
            "💡 *Что можно сделать:*\n"
            "• Чтобы изменить город — напишите `/start`\n"
            "• Посмотреть ваши отзывы — напишите `/myreviews`\n"
            "• Для модераторов: `/modqueue` — очередь на модерацию",
            parse_mode="Markdown",
            reply_markup=BACK_KEYBOARD
        )
        
    except Exception as e:
        logger.exception(f"❌ Ошибка загрузки профиля: {e}")
        
        await callback.message.edit_text(
            "❌ *Не удалось загрузить профиль.*\n\n"
            "Возможно, вы не зарегистрированы. Выполните команду `/start` для регистрации.",
            parse_mode="Markdown",
            reply_markup=BACK_KEYBOARD
        )
    
    await callback.answer()


@router.callback_query(F.data == "ask")
async def handle_recommend_button(callback: CallbackQuery):
    """Кнопка получения рекомендации"""
    await callback.message.edit_text(
        "🎯 *Напишите, что вам хочется — например:*\n\n"
        "• _«Хочу сходить на концерт»_\n"
        "• _«Нужно уютное кафе»_\n"
        "• _«Что посмотреть в центре?»_\n"
        "• _«Ищу место для романтического ужина»_\n"
        "• _«Куда сходить с детьми?»_\n\n"
        "Я подберу лучшие варианты специально для вас! ✨",
        parse_mode="Markdown",
        reply_markup=BACK_KEYBOARD
    )
    await callback.answer()


@router.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery):
    """Возврат в главное меню"""
    await callback.message.edit_text(
        "✅ *Вы вернулись в главное меню.*\n\n"
        "📝 *Как пользоваться:*\n"
        "• Просто напишите, что вам хочется\n"
        "• Например: _«Хочу сходить на концерт»_\n"
        "• Или: _«Нужно уютное кафе»_\n"
        "• Или: _«Что посмотреть в центре?»_\n\n"
        "Я подберу лучшие варианты специально для вас! 😊\n\n"
        "Или воспользуйтесь кнопками ниже:",
        parse_mode="Markdown",
        reply_markup=MAIN_INLINE_KEYBOARD
    )
    await callback.answer()