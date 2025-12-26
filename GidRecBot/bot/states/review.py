# bot/states/review.py
from aiogram.fsm.state import State, StatesGroup

class ReviewStates(StatesGroup):
    """FSM для оставления отзыва"""
    place_id = State()   # Шаг 1: выбор места (если вызван не из карточки)
    rating = State()     # Шаг 2: оценка (1–5)
    text = State()       # Шаг 3: текст отзыва