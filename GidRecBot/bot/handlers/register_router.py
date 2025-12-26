# bot/handlers/register_router.py (ИСПРАВЛЕННЫЙ - убраны лишние ссылки на COMMON_KEYBOARD)
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from typing import Dict, Any
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from ..keyboards.inline import get_main_keyboard, get_back_keyboard
from ..utils.http_client import http_client
from ..utils.user_manager import switch_user_role, get_user_info
import logging

router = Router()
logger = logging.getLogger(__name__)

class RegisterStates(StatesGroup):
    location = State()

class SearchStates(StatesGroup):
    """Состояния для поиска мест"""
    waiting_for_query = State()
    selecting_category = State()

@router.message(Command("start", ignore_mention=True))
async def cmd_start(message: Message, state: FSMContext):
    """Обработка команды /start"""
    try:
        user = message.from_user
        user_name = user.first_name or "друг"
        
        # Экранируем имя пользователя для Markdown
        user_name = user_name.replace("*", "\\*").replace("_", "\\_").replace("`", "\\`")
        
        # Важно: получаем или создаем пользователя в системе
        logger.info(f"🔄 Получаем/создаем пользователя {user.id} при /start")
        user_info = await get_user_info(user.id)
        
        if user_info:
            logger.info(f"✅ Пользователь {user.id} готов: {user_info.get('username', 'N/A')}")
            
            # Формируем персонализированное приветствие
            if user_info.get('first_name'):
                display_name = user_info['first_name']
            else:
                display_name = user_name
            
            welcome_text = (
                f"👋 Привет, {display_name}! Я — ваш персональный гид по местам отдыха.\n\n"
                f"✅ *Вы успешно подключены к системе!*\n\n"
                f"*Что я могу для вас сделать:*\n"
                f"• 🔍 Найти места по вашим предпочтениям\n"
                f"• ⭐ Показать популярные места\n"
                f"• ✍️ Принять ваши отзывы о посещенных местах\n"
                f"• 🎯 Дать персонализированные рекомендации\n\n"
                f"*Начните с простого запроса или выберите действие ниже:* 👇"
            )
            
            # Добавляем информацию о статусе
            if user_info.get('action') == 'created':
                welcome_text += "\n\n🎉 *Новый аккаунт создан!*"
            elif user_info.get('action') == 'updated':
                welcome_text += "\n\n✅ *Профиль обновлен!*"
                
        else:
            # Fallback если не удалось получить информацию
            welcome_text = (
                f"👋 Привет, {user_name}! Я — ваш персональный гид по местам отдыха.\n\n"
                f"*Выберите действие ниже:* 👇"
            )
        
        await message.answer(
            welcome_text,
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )
        
    except Exception as e:
        logger.error(f"Ошибка в cmd_start: {e}")
        # Fallback сообщение
        await message.answer(
            "👋 Привет! Я — ваш персональный гид по местам отдыха.\n\n"
            "Выберите действие:",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )

@router.message(Command("me", ignore_mention=True))
async def cmd_me(message: Message, backend_user: Dict[str, Any] = None):
    """Команда /me - показывает информацию о пользователе"""
    try:
        if not backend_user:
            # Если middleware не сработал, получаем информацию
            logger.warning(f"Middleware не передал backend_user для {message.from_user.id}")
            backend_user = await get_user_info(message.from_user.id)
        
        if backend_user:
            # Форматируем текст профиля
            text = format_profile_text(message.from_user.id, backend_user)
        else:
            text = "❌ Не удалось получить информацию о профиле"
            
    except Exception as e:
        logger.error(f"Ошибка получения профиля: {e}", exc_info=True)
        text = "❌ Ошибка при получении профиля"
    
    await message.answer(text, parse_mode="Markdown")

@router.callback_query(F.data == "me")
async def handle_profile(callback: CallbackQuery, backend_user: Dict[str, Any] = None):
    """Обработка кнопки профиля"""
    try:
        if not backend_user:
            # Если middleware не сработал, получаем информацию
            logger.warning(f"Middleware не передал backend_user в callback для {callback.from_user.id}")
            backend_user = await get_user_info(callback.from_user.id)
        
        if backend_user:
            # Форматируем текст профиля
            profile_text = format_profile_text(callback.from_user.id, backend_user)
            
        else:
            user = callback.from_user
            profile_text = (
                f"👤 *Ваш профиль*\n\n"
                f"🆔 Telegram ID: `{user.id}`\n"
                f"👤 Имя: {user.first_name or 'Не указано'}\n"
                f"👤 Фамилия: {user.last_name or 'Не указана'}\n"
                f"👤 Username: @{user.username or 'Не указан'}\n\n"
                f"⚠️ *Не удалось получить полную информацию из системы.*"
            )
            
    except Exception as e:
        logger.error(f"Ошибка получения профиля в callback: {e}", exc_info=True)
        profile_text = "❌ Ошибка при получении профиля"
    
    await callback.message.edit_text(
        profile_text, 
        parse_mode="Markdown", 
        reply_markup=get_back_keyboard()
    )
    await callback.answer()

def format_profile_text(tg_id: int, user_info: Dict[str, Any]) -> str:
    """Форматирует текст профиля"""
    # Проверяем что это словарь
    if not isinstance(user_info, dict):
        return "❌ Некорректные данные профиля"
    
    # Экранируем данные для Markdown
    username = user_info.get('username', '')
    if username:
        username = username.replace("*", "\\*").replace("_", "\\_").replace("`", "\\`")
    else:
        username = 'N/A'
    
    first_name = user_info.get('first_name', '')
    if first_name:
        first_name = first_name.replace("*", "\\*").replace("_", "\\_").replace("`", "\\`")
    else:
        first_name = 'N/A'
    
    last_name = user_info.get('last_name', '')
    if last_name:
        last_name = last_name.replace("*", "\\*").replace("_", "\\_").replace("`", "\\`")
    
    # Получаем backend_id - может быть в разных ключах
    backend_id = user_info.get('id') or user_info.get('backend_user_id', 'N/A')
    
    # Получаем роль
    role = user_info.get('role', 'user').upper()
    
    # Получаем статус активности
    is_active = user_info.get('is_active', True)
    
    # Форматируем дату
    created_at = user_info.get('created_at', 'N/A')
    if created_at and created_at != 'N/A':
        try:
            # Парсим ISO формат: "2025-12-26T15:11:48.894475+00:00"
            if 'T' in created_at:
                date_part = created_at.split('T')[0]
                created_at = date_part
        except:
            pass
    
    # Форматируем текст
    text = (
        f"👤 *Ваш профиль*\n\n"
        f"🆔 Telegram ID: `{tg_id}`\n"
        f"👤 Backend ID: `{backend_id}`\n"
        f"👑 Роль: *{role}*\n"
        f"📝 Имя: {first_name} {last_name}\n"
        f"👤 Username: @{username}\n"
        f"✅ Активен: {'Да' if is_active else 'Нет'}\n"
        f"📅 Зарегистрирован: {created_at}\n\n"
    )
    
    # Добавляем информацию о правах
    permissions = user_info.get('permissions', {})
    if permissions and isinstance(permissions, dict):
        text += "*Ваши права:*\n"
        for perm, value in permissions.items():
            if value:
                perm_text = perm.replace('_', ' ').replace('can ', '').title()
                text += f"• {perm_text}\n"
    
    return text

@router.message(Command("places", ignore_mention=True))
async def cmd_places(message: Message):
    """Показывает доступные места"""
    try:
        # Получаем места из бэкенда
        response = await http_client.get_places(limit=5)
        
        if response and response.get("places"):
            places = response["places"]
            text = "📍 *Доступные места:*\n\n"
            
            for i, place in enumerate(places, 1):
                rating = place.get("rating", 0.0)
                review_count = place.get("review_count", 0)
                
                # Экранируем данные для Markdown
                place_name = place.get('name', '').replace("*", "\\*").replace("_", "\\_").replace("`", "\\`")
                city = place.get('city', 'N/A').replace("*", "\\*").replace("_", "\\_").replace("`", "\\`")
                address = place.get('address', 'N/A').replace("*", "\\*").replace("_", "\\_").replace("`", "\\`")
                category = place.get('category', 'other').replace("*", "\\*").replace("_", "\\_").replace("`", "\\`")
                description = place.get('description', '').replace("*", "\\*").replace("_", "\\_").replace("`", "\\`")
                
                text += (
                    f"{i}. *{place_name}*\n"
                    f"   📍 {city} | {address[:30]}...\n"
                    f"   🏷️ {category} | ⭐ {rating} ({review_count} отзывов)\n"
                    f"   📝 {description[:50]}...\n\n"
                )
            
            text += "Используйте /ask <запрос> для поиска конкретных мест"
            
        else:
            text = "ℹ️ Пока нет доступных мест. Попробуйте позже."
            
    except Exception as e:
        logger.error(f"Ошибка получения мест: {e}")
        text = "❌ Ошибка при получении списка мест"
    
    await message.answer(text, parse_mode="Markdown")

@router.message(Command("help", ignore_mention=True))
async def cmd_help(message: Message):
    """Команда /help"""
    help_text = (
        "📘 *Справка по боту*\n\n"
        "🔍 *Как искать места*\n"
        "1. Нажмите «🔍 Подобрать место»\n"
        "2. Опишите, что ищете (например: «хочу в уютное кафе с Wi-Fi»)\n"
        "3. Я найду лучшие варианты из базы\n\n"
        "📍 *Популярные места*\n"
        "Нажмите «📍 Популярные места» чтобы увидеть топ мест по рейтингу\n\n"
        "⭐ *Отзывы*\n"
        "После посещения места вы можете оставить отзыв\n\n"
        "👤 *Профиль*\n"
        "Просмотр информации о вашем аккаунте\n\n"
        "*Команды*\n"
        "/start — Перезапустить бота\n"
        "/help — Эта справка\n"
        "/ask — Быстрый поиск (альтернатива кнопке)\n\n"
        "Просто напишите, что ищете — я помогу найти лучшее место! 😊"
    )
    
    await message.answer(help_text, parse_mode="Markdown", reply_markup=get_back_keyboard())

# Остальные обработчики из оригинального файла...
@router.callback_query(F.data == "help")
async def handle_help(callback: CallbackQuery):
    """Обработка кнопки помощи"""
    await cmd_help(callback.message)
    await callback.answer()

@router.callback_query(F.data == "ask")
async def handle_recommend_button(callback: CallbackQuery):
    ask_text = (
        "🎯 *Напишите, что вам хочется — например*\n"
        "• _«Хочу сходить на концерт»_\n"
        "• _«Нужно уютное кафе»_\n"
        "• _«Что посмотреть в центре?»_"
    )
    
    await callback.message.edit_text(
        ask_text,
        parse_mode="Markdown",
        reply_markup=get_back_keyboard()
    )
    await callback.answer()

@router.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery):
    back_text = (
        "✅ Вы вернулись в главное меню.\n\n"
        "Напишите, что вам хочется — например:\n"
        "• _«Хочу сходить на концерт»_\n"
        "• _«Нужно уютное кафе»_\n"
        "• _«Что посмотреть в центре?»_\n\n"
        "Или воспользуйтесь кнопками ниже:"
    )
    
    await callback.message.edit_text(
        back_text,
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )
    await callback.answer()

@router.callback_query(F.data == "find_place")
async def handle_find_place(callback: CallbackQuery, state: FSMContext):
    """Начало поиска места"""
    search_text = (
        "🔍 *Поиск мест*\n\n"
        "Опишите, что вы ищете — например:\n"
        "• _«Уютное кафе с Wi-Fi для работы»_\n"
        "• _«Романтический ресторан с панорамным видом»_\n"
        "• _«Интересная выставка современного искусства»_\n"
        "• _«Тихий парк для прогулки с собакой»_\n\n"
        "Я найду лучшие варианты из нашей базы данных! 🗺️"
    )
    
    await callback.message.edit_text(
        search_text,
        parse_mode="Markdown",
        reply_markup=get_back_keyboard()
    )
    
    # Устанавливаем состояние ожидания запроса
    await state.set_state(SearchStates.waiting_for_query)
    await callback.answer()