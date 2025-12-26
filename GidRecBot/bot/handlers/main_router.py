# bot/handlers/main_router.py
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command

router = Router()

# --- /help ---
@router.message(Command("help", ignore_mention=True))
async def cmd_help(message: Message):
    await message.answer(
        "📘 *Справка по командам:*\n\n"
        "• `/start` — начать регистрацию (выбор города)\n"
        "• `/ask` — получить рекомендацию от ИИ\n"
        "• `/review` — оставить отзыв (после просмотра места)\n"
        "• `/me` — посмотреть профиль\n"
        "• `/cancel` — отмена действия\n\n"
        "Для начала работы выполните `/start`.",
        parse_mode="Markdown"
    )

@router.message(Command("cancel", ignore_mention=True))
@router.message(F.text == "❌ Отмена")
async def cmd_cancel(message: Message):
    await message.answer(
        "⏹ Действие отменено.\n"
        "Вы можете выбрать другую команду.",
        reply_markup=None
    )