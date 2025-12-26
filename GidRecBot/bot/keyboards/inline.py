# GidRecBot/bot/keyboards/inline.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import Optional, List

def get_main_keyboard() -> InlineKeyboardMarkup:
    """Основная клавиатура для главного меню"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔍 Подобрать место", callback_data="find_place"),
            InlineKeyboardButton(text="📍 Популярные места", callback_data="popular_places")
        ],
        [
            InlineKeyboardButton(text="⭐ Мои отзывы", callback_data="my_reviews"),
            InlineKeyboardButton(text="👤 Мой профиль", callback_data="me")
        ],
        [
            InlineKeyboardButton(text="❓ Помощь", callback_data="help"),
            InlineKeyboardButton(text="🆘 Поддержка", callback_data="support")
        ]
    ])

def get_categories_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора категорий"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="☕ Кафе", callback_data="category:cafe"),
            InlineKeyboardButton(text="🍽️ Рестораны", callback_data="category:restaurant")
        ],
        [
            InlineKeyboardButton(text="🎭 Мероприятия", callback_data="category:event"),
            InlineKeyboardButton(text="🏛️ Музеи", callback_data="category:museum")
        ],
        [
            InlineKeyboardButton(text="🌳 Парки", callback_data="category:park"),
            InlineKeyboardButton(text="🎬 Кино", callback_data="category:cinema")
        ],
        [
            InlineKeyboardButton(text="🎭 Театры", callback_data="category:theatre"),
            InlineKeyboardButton(text="🎨 Искусство", callback_data="category:art")
        ],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
    ])

def get_place_keyboard(place_id: str, show_reviews: bool = True) -> InlineKeyboardMarkup:
    """Кнопки под карточкой места"""
    buttons = []
    
    if show_reviews:
        buttons.append([
            InlineKeyboardButton(text="✍️ Оставить отзыв", callback_data=f"review:{place_id}"),
            InlineKeyboardButton(text="⭐ Посмотреть отзывы", callback_data=f"view_reviews:{place_id}")
        ])
    
    buttons.append([InlineKeyboardButton(text="🔙 К поиску", callback_data="back_to_search"),
                    InlineKeyboardButton(text="🔙 В главное меню", callback_data="back_to_main")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_rating_keyboard() -> InlineKeyboardMarkup:
    """Оценка 1–5"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⭐ 1", callback_data="rate:1"),
            InlineKeyboardButton(text="⭐⭐ 2", callback_data="rate:2"),
            InlineKeyboardButton(text="⭐⭐⭐ 3", callback_data="rate:3"),
            InlineKeyboardButton(text="⭐⭐⭐⭐ 4", callback_data="rate:4"),
            InlineKeyboardButton(text="⭐⭐⭐⭐⭐ 5", callback_data="rate:5"),
        ],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
    ])

def get_back_keyboard() -> InlineKeyboardMarkup:
    """Простая кнопка "Назад" """
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
    ])

def get_pagination_keyboard(page: int, total_pages: int, query: str = "", category: str = "") -> InlineKeyboardMarkup:
    """Клавиатура пагинации для мест"""
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