# bot/keyboards/inline.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_location_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора города (1 шаг)"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏙️ Москва", callback_data="loc:moscow")],
        [InlineKeyboardButton(text="🏛️ Санкт-Петербург", callback_data="loc:saint-petersburg")],
        [InlineKeyboardButton(text="🕌 Казань", callback_data="loc:kazan")],
        [InlineKeyboardButton(text="🏭 Екатеринбург", callback_data="loc:ekaterinburg")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
    ])

def get_place_keyboard(place_id: int) -> InlineKeyboardMarkup:
    """Кнопки под карточкой места"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✍️ Оставить отзыв", callback_data=f"review:{place_id}"),
            InlineKeyboardButton(text="🔗 Подробнее", url="https://example.com")
        ]
    ])

def get_rating_keyboard() -> InlineKeyboardMarkup:
    """Оценка 1–5"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⭐", callback_data="rate:1"),
            InlineKeyboardButton(text="⭐⭐", callback_data="rate:2"),
            InlineKeyboardButton(text="⭐⭐⭐", callback_data="rate:3"),
            InlineKeyboardButton(text="⭐⭐⭐⭐", callback_data="rate:4"),
            InlineKeyboardButton(text="⭐⭐⭐⭐⭐", callback_data="rate:5"),
        ],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
    ])