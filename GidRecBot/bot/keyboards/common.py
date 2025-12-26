# bot/keyboards/common.py
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

# 🎯 Постоянная клавиатура (всегда внизу)
COMMON_KEYBOARD = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="❓ Помощь"),
            KeyboardButton(text="⏹ Отмена")
        ]
    ],
    resize_keyboard=True,
    one_time_keyboard=False,  # ← Ключево: клавиатура НЕ исчезает после нажатия
    selective=False
)