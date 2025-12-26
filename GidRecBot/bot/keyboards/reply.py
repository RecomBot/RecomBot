from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    """Кнопка «Отмена» для отмены FSM"""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True,
        one_time_keyboard=True
    )