# GidRecBot/bot/handlers/search_router.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import default_state
from typing import Dict, Any, List
from ..keyboards.inline import get_main_keyboard, get_place_keyboard, get_back_keyboard
from ..utils.http_client import http_client
from ..states.review import ReviewStates
import logging
import re

router = Router()
logger = logging.getLogger(__name__)

# Состояния импортируем из register_router
from ..handlers.register_router import SearchStates

# Константы для пагинации
PLACES_PER_PAGE = 3

def get_pagination_keyboard(page: int, total_pages: int, query: str = "", category: str = "") -> InlineKeyboardMarkup:
    """Клавиатура пагинации"""
    buttons = []
    
    if total_pages > 1:
        row = []
        if page > 0:
            row.append(InlineKeyboardButton(text="◀️ Назад", callback_data=f"page:{page-1}:{query}:{category}"))
        
        row.append(InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="current_page"))
        
        if page < total_pages - 1:
            row.append(InlineKeyboardButton(text="Вперед ▶️", callback_data=f"page:{page+1}:{query}:{category}"))
        
        buttons.append(row)
    
    buttons.append([InlineKeyboardButton(text="🔍 Новый поиск", callback_data="find_place")])
    buttons.append([InlineKeyboardButton(text="🔙 В главное меню", callback_data="back_to_main")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def filter_places_by_query(places: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
    """Фильтрация мест по поисковому запросу"""
    if not query or not places:
        return places
    
    query_lower = query.lower()
    filtered_places = []
    
    # Ключевые слова для категорий
    category_keywords = {
        "cafe": ["кафе", "кофейня", "кофе", "чай", "десерт", "завтрак", "ланч", "выпечка", "булочная"],
        "restaurant": ["ресторан", "ужин", "обед", "ужинать", "обедать", "кухня", "блюдо", "меню", "закусочная"],
        "park": ["парк", "прогулка", "природа", "сквер", "сад", "отдых", "зелень", "аллея", "фонтан"],
        "museum": ["музей", "выставка", "галерея", "искусство", "экспозиция", "коллекция", "история"],
        "cinema": ["кино", "фильм", "сеанс", "кинозал", "премьера", "кинотеатр", "просмотр"],
        "theatre": ["театр", "спектакль", "постановка", "представление", "балет", "опера", "драма"],
        "bar": ["бар", "паб", "напитки", "коктейль", "пиво", "вино", "алкоголь"],
        "mall": ["торговый", "центр", "магазин", "шопинг", "бутик", "универмаг", "молл"]
    }
    
    for place in places:
        if not isinstance(place, dict):
            continue
            
        place_name = place.get("name", "")
        place_desc = place.get("description", "")
        place_category = place.get("category", "")
        
        if not place_name:
            continue
            
        place_name_lower = place_name.lower()
        place_desc_lower = place_desc.lower()
        
        # Проверяем категорию
        category_match = False
        if place_category in category_keywords:
            keywords = category_keywords[place_category]
            if any(keyword in query_lower for keyword in keywords):
                category_match = True
        
        # Проверяем название и описание
        query_words = query_lower.split()
        name_match = any(word in place_name_lower for word in query_words)
        desc_match = any(word in place_desc_lower for word in query_words[:3])
        
        if category_match or name_match or desc_match:
            filtered_places.append(place)
    
    return filtered_places

@router.message(StateFilter(SearchStates.waiting_for_query))
async def process_search_query(message: Message, state: FSMContext):
    """Обработка поискового запроса пользователя"""
    user_query = message.text.strip()
    
    if not user_query or len(user_query) < 3:
        await message.answer("❌ Запрос слишком короткий. Опишите подробнее, что ищете.")
        return
    
    # Сохраняем запрос в состоянии
    await state.update_data(user_query=user_query, page=0)
    
    # Показываем "ищу..."
    search_msg = await message.answer("🔍 *Ищу подходящие места...*", parse_mode="Markdown")
    
    try:
        # 1. Сначала ищем в базе данных по категориям
        places_response = await http_client.get_places(limit=50)
        
        logger.info(f"Ответ от API для поиска '{user_query}': {places_response}")
        
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Проверяем ответ
        if not places_response:
            await search_msg.edit_text(
                "❌ *Не удалось подключиться к серверу.*\n\n"
                "Попробуйте позже или обратитесь в поддержку.",
                parse_mode="Markdown",
                reply_markup=get_back_keyboard()
            )
            await state.clear()
            return
        
        # Проверяем если это ошибка от API
        if isinstance(places_response, dict) and places_response.get("error"):
            error_msg = places_response.get("message", "Неизвестная ошибка")
            await search_msg.edit_text(
                f"❌ *Ошибка сервера:* {error_msg}\n\n"
                "Попробуйте позже.",
                parse_mode="Markdown",
                reply_markup=get_back_keyboard()
            )
            await state.clear()
            return
        
        # Проверяем наличие ключа "places"
        if "places" not in places_response:
            logger.warning(f"Ответ API не содержит ключ 'places': {places_response}")
            await search_msg.edit_text(
                "❌ *Некорректный ответ от сервера.*\n\n"
                "Попробуйте позже.",
                parse_mode="Markdown",
                reply_markup=get_back_keyboard()
            )
            await state.clear()
            return
        
        places = places_response.get("places", [])
        
        if not isinstance(places, list):
            logger.error(f"Поле 'places' не является списком: {type(places)}")
            await search_msg.edit_text(
                "❌ *Ошибка формата данных.*\n\n"
                "Попробуйте позже.",
                parse_mode="Markdown",
                reply_markup=get_back_keyboard()
            )
            await state.clear()
            return
        
        logger.info(f"Получено {len(places)} мест из базы данных")
        
        # Фильтруем места по запросу (простой анализ)
        filtered_places = filter_places_by_query(places, user_query)
        
        logger.info(f"После фильтрации осталось {len(filtered_places)} мест")
        
        # Сохраняем отфильтрованные места в состоянии
        await state.update_data(filtered_places=filtered_places)
        
        if filtered_places:
            # Показываем первую страницу
            await show_places_page(message, filtered_places, 0, user_query, search_msg)
        else:
            # Мест не найдено - предлагаем ИИ поиск
            await search_msg.edit_text(
                f"🤔 *По вашему запросу в базе данных не найдено мест.*\n\n"
                f"*Запрос:* «{user_query}»\n\n"
                f"Всего мест в базе: {len(places)}\n\n"
                "Хотите, чтобы я поискал с помощью ИИ?",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(text="🤖 Да, поищите ИИ", callback_data=f"ai_search:{user_query}"),
                        InlineKeyboardButton(text="🔍 Новый поиск", callback_data="find_place")
                    ],
                    [InlineKeyboardButton(text="🔙 В главное меню", callback_data="back_to_main")]
                ])
            )
    
    except Exception as e:
        logger.error(f"Ошибка поиска: {e}", exc_info=True)
        await search_msg.edit_text(
            "❌ *Произошла ошибка при поиске.*\n\n"
            "Попробуйте ещё раз или обратитесь в поддержку.",
            parse_mode="Markdown",
            reply_markup=get_back_keyboard()
        )
    
    # Не сбрасываем состояние, чтобы можно было использовать пагинацию
    # await state.clear()

async def show_places_page(
    message: Message, 
    places: List[Dict[str, Any]], 
    page: int, 
    query: str = "",
    search_msg: Message = None,
    is_ai_search: bool = False  # Новый параметр
):
    """Показывает страницу с местами"""
    if not places:
        if search_msg:
            await search_msg.edit_text(
                "❌ *Не найдено мест для отображения.*",
                parse_mode="Markdown",
                reply_markup=get_back_keyboard()
            )
        return
    
    total_places = len(places)
    total_pages = (total_places + PLACES_PER_PAGE - 1) // PLACES_PER_PAGE
    
    if page >= total_pages:
        page = 0
    
    start_idx = page * PLACES_PER_PAGE
    end_idx = min(start_idx + PLACES_PER_PAGE, total_places)
    page_places = places[start_idx:end_idx]
    
    # Разные заголовки для обычного и ИИ-поиска
    if is_ai_search:
        header = f"🤖 *Интеллектуальный поиск:*\n\n*Запрос:* «{query}»\n\n"
    else:
        header = f"✅ *Нашёл {total_places} мест:*\n\n*Запрос:* «{query}»\n\n"
    
    header += f"*Страница {page+1} из {total_pages}:*"
    
    if search_msg:
        await search_msg.edit_text(
            header,
            parse_mode="Markdown",
            reply_markup=get_pagination_keyboard(page, total_pages, query, "ai" if is_ai_search else "")
        )
    else:
        await message.edit_text(
            header,
            parse_mode="Markdown",
            reply_markup=get_pagination_keyboard(page, total_pages, query, "ai" if is_ai_search else "")
        )
    
    # Показываем места на текущей странице
    for i, place in enumerate(page_places, 1):
        if not isinstance(place, dict):
            continue
            
        rating = place.get("rating", 0.0)
        review_count = place.get("review_count", 0)
        address = place.get("address", "Адрес не указан")
        category = place.get("category", "other")
        
        # Для ИИ-поиска добавляем информацию о совпадении ключевых слов
        keyword_matches = place.get("keyword_matches", 0)
        ai_badge = ""
        if is_ai_search and keyword_matches > 0:
            ai_badge = f" 🔍 {keyword_matches} совпад."
        
        # Эмодзи для категорий
        category_emoji = {
            "cafe": "☕",
            "restaurant": "🍽️",
            "park": "🌳",
            "museum": "🏛️",
            "cinema": "🎬",
            "theatre": "🎭",
            "art": "🎨",
            "bar": "🍸",
            "mall": "🛍️"
        }.get(category, "📍")
        
        place_text = (
            f"*{start_idx + i}. {category_emoji} {place.get('name', 'Без названия')}{ai_badge}*\n"
            f"📝 {place.get('description', 'Описание отсутствует')[:80]}...\n"
            f"⭐ Рейтинг: *{rating:.1f}/5* ({review_count} отзывов)\n"
            f"📍 Адрес: {address}\n"
            f"🏷️ Категория: {category}"
        )
        
        place_id = place.get("id")
        if place_id:
            await message.answer(
                place_text,
                parse_mode="Markdown",
                reply_markup=get_place_keyboard(str(place_id))
            )

@router.callback_query(F.data.startswith("page:"))
async def handle_pagination(callback: CallbackQuery, state: FSMContext):
    """Обработка пагинации"""
    try:
        # Извлекаем данные из callback
        parts = callback.data.split(":")
        if len(parts) < 2:
            await callback.answer("❌ Ошибка пагинации")
            return
        
        page = int(parts[1])
        query = parts[2] if len(parts) > 2 else ""
        
        # Получаем данные из состояния
        state_data = await state.get_data()
        filtered_places = state_data.get("filtered_places", [])
        
        if not filtered_places:
            # Если нет мест в состоянии, получаем заново
            places_response = await http_client.get_places(limit=50)
            
            if places_response and isinstance(places_response, dict) and "places" in places_response:
                places = places_response["places"]
                if isinstance(places, list):
                    filtered_places = filter_places_by_query(places, query)
                    await state.update_data(filtered_places=filtered_places)
        
        if filtered_places:
            await show_places_page(callback.message, filtered_places, page, query)
        else:
            await callback.message.edit_text(
                "❌ *Не удалось загрузить места.*\n\n"
                "Попробуйте выполнить поиск заново.",
                parse_mode="Markdown",
                reply_markup=get_back_keyboard()
            )
    
    except Exception as e:
        logger.error(f"Ошибка пагинации: {e}", exc_info=True)
        await callback.answer("❌ Ошибка переключения страницы")
    
    await callback.answer()

@router.callback_query(F.data.startswith("ai_search:"))
async def handle_ai_search(callback: CallbackQuery, state: FSMContext):
    """Обработка запроса на интеллектуальный поиск"""
    user_query = callback.data.split(":", 1)[1]
    
    await callback.message.edit_text(
        f"🧠 *Анализирую ваш запрос...*\n\n"
        f"*Ваш запрос:* «{user_query}»\n\n"
        "Использую ИИ для понимания, что вы ищете, и ищу подходящие места в базе данных...",
        parse_mode="Markdown"
    )
    
    try:
        # Используем интеллектуальный поиск
        response = await http_client.intelligent_search(
            query=user_query,
            telegram_id=callback.from_user.id,
            limit=15  # Больше мест для ИИ-поиска
        )
        
        if response and response.get("success"):
            places = response.get("places", [])
            analysis = response.get("analysis", {})
            total_found = response.get("total_found", 0)
            
            if places:
                # Сохраняем места в состоянии для пагинации
                await state.update_data(
                    filtered_places=places,
                    user_query=user_query,
                    page=0,
                    is_ai_search=True  # Флаг что это ИИ-поиск
                )
                
                # Формируем анализ от LLM
                reasoning = analysis.get("reasoning", "Анализ не предоставлен")
                category = analysis.get("category", "не определена")
                keywords = analysis.get("keywords", [])
                
                analysis_text = (
                    f"🤖 *Анализ ИИ:*\n\n"
                    f"*Запрос:* «{user_query}»\n\n"
                    f"📊 *Результаты анализа:*\n"
                    f"• Категория: {category if category else 'не определена'}\n"
                    f"• Ключевые слова: {', '.join(keywords[:5]) if keywords else 'не определены'}\n"
                    f"• Найдено мест: {total_found}\n\n"
                    f"💡 *Обоснование:*\n{reasoning}\n\n"
                    f"📍 *Результаты поиска:*"
                )
                
                await callback.message.edit_text(
                    analysis_text,
                    parse_mode="Markdown",
                    reply_markup=get_pagination_keyboard(0, 1, user_query, "ai")  # Первая страница
                )
                
                # Показываем первую страницу мест
                await show_places_page(
                    callback.message,
                    places,
                    0,
                    user_query,
                    search_msg=None,
                    is_ai_search=True
                )
                
            else:
                await callback.message.edit_text(
                    f"🤖 *Интеллектуальный поиск*\n\n"
                    f"*Запрос:* «{user_query}»\n\n"
                    f"К сожалению, не нашёл подходящих мест по вашему запросу.\n\n"
                    f"Попробуйте:\n"
                    f"• Уточнить запрос\n"
                    f"• Использовать другие слова\n"
                    f"• Посмотреть популярные места",
                    parse_mode="Markdown",
                    reply_markup=get_back_keyboard()
                )
        else:
            await callback.message.edit_text(
                "❌ *ИИ не смог проанализировать запрос.*\n\n"
                "Попробуйте уточнить запрос или воспользуйтесь обычным поиском.",
                parse_mode="Markdown",
                reply_markup=get_back_keyboard()
            )
    
    except Exception as e:
        logger.error(f"Ошибка ИИ-поиска: {e}", exc_info=True)
        await callback.message.edit_text(
            "❌ *Ошибка интеллектуального поиска.*\n\n"
            "Попробуйте позже или используйте обычный поиск.",
            parse_mode="Markdown",
            reply_markup=get_back_keyboard()
        )
    
    await callback.answer()
    
@router.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery):
    """Возврат в главное меню"""
    await callback.message.edit_text(
        "✅ *Главное меню*\n\n"
        "Выберите действие:",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )
    await callback.answer()

@router.callback_query(F.data == "back_to_search")
async def back_to_search(callback: CallbackQuery, state: FSMContext):
    """Возврат к поиску"""
    from ..handlers.register_router import handle_find_place
    await handle_find_place(callback, state)