from aiogram import Router, F
from aiogram.types import Message

router = Router()


@router.message(F.text.startswith("/"))
async def unknown_command(message: Message):
    await message.answer(
        "❓ *Неизвестная команда.*\n\n"
        "Используйте `/help`, чтобы посмотреть доступные команды.",
        parse_mode="Markdown"
    )
