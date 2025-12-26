# GidRecBot/bot/handlers/llm_router.py (УПРОЩЕННЫЙ)
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import StateFilter, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import default_state
from ..utils.http_client import http_client
from ..keyboards.inline import get_back_keyboard
import logging
from typing import Dict, Any

router = Router()
logger = logging.getLogger(__name__)


@router.message(Command("ask", ignore_mention=True))
async def cmd_ask(message: Message):
    """Команда /ask для быстрого поиска"""
    search_text = (
        "🔍 *Быстрый поиск*\n\n"
        "Опишите, что вы ищете — например:\n"
        "• _«Уютное кафе с Wi-Fi для работы»_\n"
        "• _«Романтический ресторан с панорамным видом»_\n"
        "• _«Интересная выставка современного искусства»_\n\n"
        "Просто напишите ваш запрос в ответ на это сообщение! 🗺️"
    )
    
    await message.answer(search_text, parse_mode="Markdown", reply_markup=get_back_keyboard())

@router.message(
    F.text,
    StateFilter(default_state)
)
async def handle_natural_query(message: Message):
    """Обрабатывает ЛЮБОЙ текст → отправляет в LLM"""
    text = message.text.strip()
    
    # Пропускаем служебные команды
    if text.startswith("/"):
        return
    
    # Показываем "думает..."
    temp_msg = await message.answer("🧠 *Анализирую запрос...*", parse_mode="Markdown")
    
    try:
        # Используем тестового пользователя
        user_id = "11111111-1111-1111-1111-111111111111"
        
        # Отправляем запрос в бэкенд
        response = await http_client.recommend(user_id, text)
        
        if response and response.get("message"):
            # LLM ответил
            await temp_msg.edit_text(
                f"🤖 *Рекомендация:*\n\n{response['message']}",
                parse_mode="Markdown"
            )
        else:
            # Fallback: получаем базовые рекомендации
            places_response = await http_client.get_places(limit=3)
            
            if places_response and places_response.get("places"):
                await temp_msg.edit_text(
                    "📍 *Вот несколько популярных мест:*",
                    parse_mode="Markdown"
                )
                
                for place in places_response["places"]:
                    rating = place.get("rating", 0.0)
                    review_count = place.get("review_count", 0)
                    
                    await message.answer(
                        f"🏷️ *{place['name']}*\n"
                        f"📝 {place.get('description', '')[:100]}...\n"
                        f"⭐ Рейтинг: {rating}/5 ({review_count} отзывов)\n"
                        f"📍 {place.get('address', 'Адрес не указан')}",
                        parse_mode="Markdown"
                    )
            else:
                await temp_msg.edit_text(
                    "❌ Не удалось найти подходящие места. Попробуйте другой запрос.",
                    parse_mode="Markdown"
                )
            
    except Exception as e:
        logger.exception("❌ Ошибка обработки запроса")
        await temp_msg.edit_text(
            "❌ Не удалось обработать запрос. Попробуйте позже.",
            parse_mode="Markdown"
        )

@router.callback_query(F.data.startswith("place:"))
async def show_place_details(callback: CallbackQuery):
    try:
        place_id = callback.data.split(":")[1]
        
        # Получаем информацию о месте
        place = await http_client.get_place(place_id)
        
        if place:
            rating = place.get("rating", 0.0)
            review_count = place.get("review_count", 0)
            
            text = (
                f"📍 *{place['name']}*\n\n"
                f"{place.get('description', '')}\n\n"
                f"⭐ Рейтинг: {rating}/5 ({review_count} отзывов)\n"
                f"📌 Адрес: {place.get('address', 'Не указан')}\n"
                f"🏷️ Категория: {place.get('category', 'other')}"
            )
            
            await callback.message.edit_text(
                text,
                parse_mode="Markdown"
            )
        else:
            await callback.message.edit_text("❌ Место не найдено.")
            
    except Exception as e:
        logger.exception("❌ Ошибка получения места")
        await callback.message.edit_text("❌ Ошибка получения информации.")
    
    await callback.answer()