# GidRecBot/bot/handlers/popular_router.py (ИСПРАВЛЕННЫЙ)
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from typing import Dict, Any, List, Tuple
from ..keyboards.inline import get_main_keyboard, get_place_keyboard, get_back_keyboard
from ..utils.http_client import http_client
import logging
import math

router = Router()
logger = logging.getLogger(__name__)

# Константы для пагинации популярных мест
PLACES_PER_PAGE = 10  # 10 мест на страницу (как кнопки)

def get_combined_keyboard(
    places: List[Dict[str, Any]], 
    page: int, 
    total_pages: int, 
    sort_by: str = "rating"
) -> InlineKeyboardMarkup:
    """
    Создает объединенную клавиатуру: кнопки мест + пагинация + сортировка
    """
    buttons = []
    
    # 1. Кнопки мест
    for i, place in enumerate(places):
        if not isinstance(place, dict):
            continue
            
        place_name = place.get("name", "Без названия")
        place_id = place.get("id")
        
        if not place_id:
            continue
        
        # Сокращаем длинные названия
        if len(place_name) > 30:
            display_name = place_name[:27] + "..."
        else:
            display_name = place_name
        
        # Добавляем номер места и эмодзи в зависимости от позиции
        if sort_by == "rating":
            # Для рейтинга - медальки
            if i == 0:
                prefix = "🥇"
            elif i == 1:
                prefix = "🥈" 
            elif i == 2:
                prefix = "🥉"
            else:
                prefix = f"{page * PLACES_PER_PAGE + i + 1}."
        else:
            # Для отзывов - номер
            prefix = f"{page * PLACES_PER_PAGE + i + 1}."
        
        # Кнопка места
        buttons.append([
            InlineKeyboardButton(
                text=f"{prefix} {display_name}",
                callback_data=f"popular_place:{place_id}"
            )
        ])
    
    # Разделитель между местами и пагинацией
    if buttons and total_pages > 1:
        buttons.append([])  # Пустая строка как разделитель
    
    # 2. Пагинация (если больше 1 страницы)
    if total_pages > 1:
        pagination_row = []
        
        # Кнопка "Назад" если не первая страница
        if page > 0:
            pagination_row.append(InlineKeyboardButton(
                text="◀️ Назад", 
                callback_data=f"popular_page:{page-1}:{sort_by}"
            ))
        
        # Текущая страница
        pagination_row.append(InlineKeyboardButton(
            text=f"{page+1}/{total_pages}", 
            callback_data="current_page"
        ))
        
        # Кнопка "Вперед" если не последняя страница
        if page < total_pages - 1:
            pagination_row.append(InlineKeyboardButton(
                text="Вперед ▶️", 
                callback_data=f"popular_page:{page+1}:{sort_by}"
            ))
        
        buttons.append(pagination_row)
    
    # 3. Кнопки сортировки
    sort_row = []
    if sort_by == "rating":
        sort_row.append(InlineKeyboardButton(
            text="⭐ Рейтинг", 
            callback_data="current_sort"
        ))
        sort_row.append(InlineKeyboardButton(
            text="💬 Отзывы", 
            callback_data="popular_sort:reviews"
        ))
    else:
        sort_row.append(InlineKeyboardButton(
            text="⭐ Рейтинг", 
            callback_data="popular_sort:rating"
        ))
        sort_row.append(InlineKeyboardButton(
            text="💬 Отзывы", 
            callback_data="current_sort"
        ))
    
    buttons.append(sort_row)
    
    # 4. Кнопки навигации
    buttons.append([
        InlineKeyboardButton(text="🔍 Поиск", callback_data="find_place"),
        InlineKeyboardButton(text="🔙 Главная", callback_data="back_to_main")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def sort_places_by_criteria(places: List[Dict[str, Any]], sort_by: str = "rating") -> List[Dict[str, Any]]:
    """Сортировка мест по разным критериям"""
    if not places:
        return []
    
    places_copy = places.copy()
    
    try:
        if sort_by == "reviews":
            # Сортировка по количеству отзывов (по убыванию), затем по рейтингу
            return sorted(
                places_copy,
                key=lambda x: (x.get("review_count", 0), x.get("rating", 0)),
                reverse=True
            )
        else:  # sort_by == "rating"
            # Сортировка по рейтингу (по убыванию), затем по количеству отзывов
            return sorted(
                places_copy,
                key=lambda x: (x.get("rating", 0), x.get("review_count", 0)),
                reverse=True
            )
    except Exception as e:
        logger.error(f"Ошибка сортировки: {e}")
        return places_copy

async def get_all_popular_places(sort_by: str = "rating") -> Tuple[List[Dict[str, Any]], int]:
    """Получает все популярные места и общее количество"""
    try:
        # Получаем достаточно много мест для пагинации
        response = await http_client.get_places(limit=100)
        
        if not response or "places" not in response:
            logger.warning("Не удалось получить места для популярных")
            return [], 0
        
        places = response.get("places", [])
        
        if not places:
            return [], 0
        
        # Фильтруем места с рейтингом > 0 или отзывами > 0
        popular_places = []
        for place in places:
            if not isinstance(place, dict):
                continue
            
            rating = place.get("rating", 0)
            review_count = place.get("review_count", 0)
            
            # Включаем в популярные если есть рейтинг или отзывы
            if rating > 0 or review_count > 0:
                popular_places.append(place)
        
        if not popular_places:
            # Если нет популярных, берем все места
            popular_places = [p for p in places if isinstance(p, dict)]
        
        # Сортируем по выбранному критерию
        sorted_places = sort_places_by_criteria(popular_places, sort_by)
        
        return sorted_places, len(sorted_places)
        
    except Exception as e:
        logger.error(f"Ошибка получения популярных мест: {e}")
        return [], 0

async def show_popular_places_page(
    callback: CallbackQuery, 
    page: int = 0, 
    sort_by: str = "rating",
    edit_message: bool = True
):
    """Показывает страницу популярных мест в виде кнопок"""
    try:
        # Получаем отсортированные места
        all_places, total_count = await get_all_popular_places(sort_by)
        
        if not all_places:
            if edit_message:
                await callback.message.edit_text(
                    "⭐ *Популярные места*\n\n"
                    "Пока нет популярных мест в базе данных.\n\n"
                    "Места становятся популярными после получения отзывов и оценок.",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🔍 Найти места", callback_data="find_place")],
                        [InlineKeyboardButton(text="🔙 В главное меню", callback_data="back_to_main")]
                    ])
                )
            else:
                await callback.message.answer(
                    "⭐ *Популярные места*\n\n"
                    "Пока нет популярных мест в базе данных.",
                    parse_mode="Markdown",
                    reply_markup=get_back_keyboard()
                )
            return
        
        # Рассчитываем пагинацию
        total_pages = math.ceil(total_count / PLACES_PER_PAGE)
        
        if page >= total_pages:
            page = 0
        
        # Получаем места для текущей страницы
        start_idx = page * PLACES_PER_PAGE
        end_idx = min(start_idx + PLACES_PER_PAGE, total_count)
        page_places = all_places[start_idx:end_idx]
        
        # Определяем заголовок сортировки
        sort_title = "⭐ Сортировка по рейтингу" if sort_by == "rating" else "💬 Сортировка по отзывам"
        sort_emoji = "⭐" if sort_by == "rating" else "💬"
        
        # Создаем сообщение
        message_text = (
            f"{sort_emoji} *Популярные места*\n\n"
            f"*{sort_title}*\n"
            f"📍 Всего: {total_count} мест\n"
            f"📄 Страница {page+1} из {total_pages}\n\n"
            f"*Выберите место из списка:*"
        )
        
        # Создаем объединенную клавиатуру
        combined_keyboard = get_combined_keyboard(page_places, page, total_pages, sort_by)
        
        if edit_message:
            # Редактируем существующее сообщение
            await callback.message.edit_text(
                message_text,
                parse_mode="Markdown",
                reply_markup=combined_keyboard
            )
        else:
            # Отправляем новое сообщение (для команды /popular)
            await callback.message.answer(
                message_text,
                parse_mode="Markdown",
                reply_markup=combined_keyboard
            )
        
    except Exception as e:
        logger.error(f"Ошибка показа популярных мест: {e}", exc_info=True)
        if edit_message:
            await callback.message.edit_text(
                "❌ *Не удалось загрузить популярные места.*\n\n"
                "Попробуйте позже.",
                parse_mode="Markdown",
                reply_markup=get_back_keyboard()
            )
        else:
            await callback.message.answer(
                "❌ *Не удалось загрузить популярные места.*",
                parse_mode="Markdown",
                reply_markup=get_back_keyboard()
            )

@router.callback_query(F.data == "popular_places")
async def handle_popular_places(callback: CallbackQuery):
    """Начальная загрузка популярных мест"""
    # Редактируем сообщение "Загружаю..."
    await callback.message.edit_text(
        "⭐ *Загружаю популярные места...*",
        parse_mode="Markdown"
    )
    
    # Показываем первую страницу, сортировка по рейтингу по умолчанию
    await show_popular_places_page(callback, page=0, sort_by="rating", edit_message=True)
    await callback.answer()

@router.callback_query(F.data.startswith("popular_page:"))
async def handle_popular_pagination(callback: CallbackQuery):
    """Обработка пагинации популярных мест"""
    try:
        # Извлекаем данные из callback
        parts = callback.data.split(":")
        if len(parts) < 3:
            await callback.answer("❌ Ошибка пагинации")
            return
        
        page = int(parts[1])
        sort_by = parts[2]
        
        # Проверяем допустимые значения sort_by
        if sort_by not in ["rating", "reviews"]:
            sort_by = "rating"
        
        # Обновляем текущее сообщение (не удаляем!)
        await show_popular_places_page(callback, page=page, sort_by=sort_by, edit_message=True)
        
    except (ValueError, IndexError) as e:
        logger.error(f"Ошибка парсинга callback данных: {e}")
        await callback.answer("❌ Ошибка переключения страницы")
    except Exception as e:
        logger.error(f"Ошибка пагинации: {e}", exc_info=True)
        await callback.answer("❌ Ошибка загрузки страницы")
    
    await callback.answer()

@router.callback_query(F.data.startswith("popular_sort:"))
async def handle_popular_sort(callback: CallbackQuery):
    """Обработка смены сортировки популярных мест"""
    try:
        sort_by = callback.data.split(":")[1]
        
        # Проверяем допустимые значения
        if sort_by not in ["rating", "reviews"]:
            sort_by = "rating"
        
        # Начинаем с первой страницы при смене сортировки
        await show_popular_places_page(callback, page=0, sort_by=sort_by, edit_message=True)
        
    except Exception as e:
        logger.error(f"Ошибка смены сортировки: {e}", exc_info=True)
        await callback.answer("❌ Ошибка смены сортировки")
    
    await callback.answer()

@router.callback_query(F.data.startswith("popular_place:"))
async def handle_popular_place_click(callback: CallbackQuery):
    """Обработка нажатия на кнопку места в списке популярных"""
    try:
        place_id = callback.data.split(":", 1)[1]
        
        # Получаем информацию о месте
        place_info = await http_client.get_place(place_id)
        
        if not place_info:
            await callback.answer("❌ Место не найдено", show_alert=True)
            return
        
        rating = place_info.get("rating", 0.0)
        review_count = place_info.get("review_count", 0)
        address = place_info.get("address", "Адрес не указан")
        category = place_info.get("category", "other")
        description = place_info.get("description", "Описание отсутствует")
        
        # Обрезаем длинное описание
        if len(description) > 500:
            description = description[:497] + "..."
        
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
        
        # Форматируем текст карточки места
        place_text = (
            f"📍 *{category_emoji} {place_info.get('name', 'Без названия')}*\n\n"
            f"📝 *Описание:*\n{description}\n\n"
            f"⭐ *Рейтинг:* {rating:.1f}/5 ({review_count} отзывов)\n"
            f"📍 *Адрес:* {address}\n"
            f"🏷️ *Категория:* {category}"
        )
        
        # Создаем клавиатуру для карточки места
        place_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✍️ Оставить отзыв", callback_data=f"review:{place_id}"),
                InlineKeyboardButton(text="⭐ Отзывы", callback_data=f"view_reviews:{place_id}")
            ],
            [
                InlineKeyboardButton(text="🔙 К списку", callback_data="popular_places"),
                InlineKeyboardButton(text="🔍 Похожие", callback_data=f"similar:{place_id}")
            ],
            [InlineKeyboardButton(text="🔙 В главное меню", callback_data="back_to_main")]
        ])
        
        # Отправляем новое сообщение с карточкой места (не редактируем список!)
        await callback.message.answer(
            place_text,
            parse_mode="Markdown",
            reply_markup=place_keyboard
        )
        
        # Отвечаем на callback (скрываем часики)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка загрузки места: {e}", exc_info=True)
        await callback.answer("❌ Ошибка загрузки места", show_alert=True)

# Команда /popular
@router.message(Command("popular", ignore_mention=True))
async def cmd_popular(message: Message):
    """Команда /popular для быстрого доступа к популярным местам"""
    # Создаем временный callback
    class TempCallback:
        def __init__(self, msg):
            self.message = msg
            self.data = "popular_places"
    
    temp_callback = TempCallback(message)
    await show_popular_places_page(temp_callback, page=0, sort_by="rating", edit_message=False)

# Обработка кнопки "Назад к списку" из карточки места
@router.callback_query(F.data == "back_to_list")
async def back_to_popular_list(callback: CallbackQuery):
    """Возврат к списку популярных мест из карточки места"""
    # Удаляем сообщение с карточкой места
    try:
        await callback.message.delete()
    except:
        pass
    
    # Показываем список популярных мест
    await handle_popular_places(callback)