# bot/handlers/review_router.py (ИСПРАВЛЕННЫЙ)
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from ..states.review import ReviewStates
from ..keyboards.inline import get_rating_keyboard, get_place_keyboard, get_back_keyboard
from ..utils.http_client import http_client
import logging
from typing import Dict, Any
from uuid import UUID

router = Router()
logger = logging.getLogger(__name__)

MOCK_PLACES = {
    1: {
        "name": "Кофейня у Патриарших",
        "description": "Уютное место с домашней выпечкой и ароматным кофе.",
        "rating_avg": 4.7,
        "rating_count": 23,
        "address": "Тверская, 12",
        "category": "cafe"
    },
    2: {
        "name": "Музей современного искусства",
        "description": "Интерактивные выставки и лекции от художников.",
        "rating_avg": 4.5,
        "rating_count": 41,
        "address": "Петровка, 25",
        "category": "museum"
    },
    3: {
        "name": "Парк Горького",
        "description": "Зелёная зона с прокатом велосипедов и летней верандой.",
        "rating_avg": 4.8,
        "rating_count": 156,
        "address": "Крымский Вал, 9",
        "category": "park"
    }
}

@router.callback_query(F.data.startswith("review:"))
async def start_review(callback: CallbackQuery, state: FSMContext):
    """Начало создания отзыва"""
    try:
        # Получаем UUID места (не int!)
        place_uuid = callback.data.split(":", 1)[1]
        
        # Проверяем что это валидный UUID
        try:
            UUID(place_uuid)
        except ValueError:
            await callback.answer("❌ Неверный ID места", show_alert=True)
            return
        
        # Получаем информацию о месте
        place_info = await http_client.get_place(place_uuid)
        
        if not place_info:
            await callback.answer("❌ Место не найдено", show_alert=True)
            return
        
        # Формируем описание (безопасный срез)
        description = place_info.get("description", "")
        if len(description) > 100:
            description = description[:100] + "..."
        
        # Сохраняем данные в состоянии
        await state.update_data(
            place_id=place_uuid,
            place_name=place_info.get("name", "Неизвестное место"),
            place_description=description
        )
        
        await state.set_state(ReviewStates.rating)
        
        await callback.message.edit_text(
            f"⭐ *Оцените место*\n\n"
            f"📍 Место: *{place_info['name']}*\n"
            f"📝 {description}\n\n"
            f"*Выберите оценку от 1 до 5:*",
            reply_markup=get_rating_keyboard(),
            parse_mode="Markdown"
        )
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка начала отзыва: {e}", exc_info=True)  # ← добавим полную информацию об ошибке
        await callback.answer("❌ Ошибка начала отзыва", show_alert=True)

@router.callback_query(ReviewStates.rating, F.data.startswith("rate:"))
async def process_rating(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора рейтинга"""
    try:
        rating = int(callback.data.split(":")[1])
        
        if rating < 1 or rating > 5:
            await callback.answer("❌ Оценка должна быть от 1 до 5", show_alert=True)
            return
        
        await state.update_data(rating=rating)
        await state.set_state(ReviewStates.text)
        
        data = await state.get_data()
        place_name = data.get("place_name", "место")
        
        await callback.message.edit_text(
            f"✍️ *Напишите отзыв*\n\n"
            f"📍 Место: *{place_name}*\n"
            f"⭐ Ваша оценка: *{rating}/5*\n\n"
            f"*Теперь напишите ваш отзыв:*\n"
            f"(минимум 10 символов, максимум 1000)\n\n"
            f"*Что можно написать:*\n"
            f"• Что понравилось\n"
            f"• Что можно улучшить\n"
            f"• Общее впечатление\n"
            f"• Рекомендации другим",
            parse_mode="Markdown"
        )
        await callback.answer()
        
    except ValueError:
        await callback.answer("❌ Неверная оценка", show_alert=True)
    except Exception as e:
        logger.error(f"Ошибка обработки оценки: {e}", exc_info=True)
        await callback.answer("❌ Ошибка обработки", show_alert=True)

@router.message(ReviewStates.text)
async def process_text(message: Message, state: FSMContext):
    """Обработка текста отзыва"""
    text = message.text.strip()
    
    if len(text) < 10:
        await message.answer("❌ Слишком коротко! Напишите хотя бы 10 символов.")
        return
    if len(text) > 1000:
        await message.answer("❌ Слишком длинно! Максимум 1000 символов.")
        return
    
    try:
        data = await state.get_data()
        place_id = data["place_id"]
        rating = data["rating"]
        place_name = data["place_name"]
        telegram_id = message.from_user.id

        # Отправляем отзыв в backend
        response = await http_client.create_review(
            place_id=place_id,
            rating=rating,
            text=text,
            telegram_id=telegram_id
        )
        
        if response:
            # Логируем полный ответ для отладки
            logger.info(f"Ответ от backend при создании отзыва: {response}")
            # Проверяем если это ошибка
            if response.get("error"):
                error_detail = response.get("detail", "Неизвестная ошибка")
                error_message = response.get("message", error_detail)
                
                logger.warning(f"Ошибка от API при создании отзыва: {error_detail}")

                error_detail_lower = error_detail.lower()
                
                # Проверяем специфичные ошибки
                if any(phrase in error_detail_lower for phrase in [
                    "уже есть активный отзыв", 
                    "already have an active review",
                    "active review exists"
                ]):
                    # У пользователя уже есть активный отзыв
                    await message.answer(
                        f"❌ *Не удалось отправить отзыв*\n\n"
                        f"📍 Место: *{place_name}*\n\n"
                        f"*Причина:* У вас уже есть активный отзыв на это место.\n\n"
                        f"⚠️ *Что можно сделать:*\n"
                        f"• Если ваш предыдущий отзыв был отклонен, вы можете написать новый\n"
                        f"• Если отзыв одобрен, вы можете удалить его через профиль\n"
                        f"• Или написать отзыв на другое место\n\n"
                        f"Используйте команду /me для просмотра ваших отзывов.",
                        parse_mode="Markdown",
                        # reply_markup=get_back_keyboard()
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="⭐ Мои отзывы", callback_data="my_reviews")],
                            [InlineKeyboardButton(text="✍️ Другое место", callback_data="find_place")],
                            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
                        ])
                    )
                elif any(phrase in error_detail_lower for phrase in [
                    "отклонен",
                    "rejected",
                    "не подходит",
                    "inappropriate"
                ]):
                    # Предыдущий отзыв был отклонен
                    await message.answer(
                        f"❌ *Не удалось отправить отзыв*\n\n"
                        f"📍 Место: *{place_name}*\n\n"
                        f"*Причина:* {error_detail}\n\n"
                        f"⚠️ *Что можно сделать:*\n"
                        f"• Переформулируйте отзыв\n"
                        f"• Уберите оскорбительные выражения\n"
                        f"• Сосредоточьтесь на фактах\n\n"
                        f"Попробуйте оставить отзыв еще раз.",
                        parse_mode="Markdown",
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="✍️ Попробовать снова", callback_data=f"review:{place_id}")],
                            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
                        ])
                    )
                else:
                    # Общая ошибка
                    await message.answer(
                        f"❌ *Не удалось отправить отзыв*\n\n"
                        f"📍 Место: *{place_name}*\n\n"
                        f"*Ошибка:* {error_message}\n\n"
                        f"Попробуйте позже или обратитесь в поддержку.",
                        parse_mode="Markdown",
                        reply_markup=get_back_keyboard()
                    )
                return
            
            # Логируем полный ответ для отладки
            logger.info(f"Успешный ответ от backend: {response}")

            # Проверяем статус модерации из ответа
            moderation_status = response.get("moderation_status", "pending")
            review_id = response.get("id")
            summary = response.get("summary", "")
            moderation_reason = response.get("moderation_reason", "")
            llm_check = response.get("llm_check", {})
            
            logger.info(f"Статус модерации: {moderation_status}, причина: {moderation_reason}")
            
            if moderation_status == "approved":
                # Отзыв одобрен автоматически
                await message.answer(
                    f"✅ *Отзыв опубликован!*\n\n"
                    f"📍 Место: *{place_name}*\n"
                    f"⭐ Оценка: *{rating}/5*\n\n"
                    f"📝 *Краткое содержание:*\n{summary}\n\n"
                    f"🎉 *Спасибо за ваш отзыв!*\n"
                    f"Он поможет другим пользователям сделать правильный выбор.",
                    parse_mode="Markdown",
                    reply_markup=get_back_keyboard()
                )
            elif moderation_status == "rejected":
                # Отзыв отклонен LLM
                reason = moderation_reason or "Нарушение правил сообщества"
                await message.answer(
                    f"❌ *Отзыв отклонен* (автоматическая проверка)\n\n"
                    f"📍 Место: *{place_name}*\n"
                    f"⭐ Оценка: *{rating}/5*\n\n"
                    f"*Причина:* {reason}\n\n"
                    f"⚠️ *Что можно сделать:*\n"
                    f"• Переформулируйте отзыв\n"
                    f"• Уберите оскорбительные выражения\n"
                    f"• Сосредоточьтесь на фактах\n\n"
                    f"Попробуйте оставить отзыв еще раз.",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="✍️ Оставить новый отзыв", callback_data=f"review:{place_id}")],
                        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
                    ])
                )
            elif moderation_status == "flagged_by_llm":
                # Отзыв отправлен на ручную модерацию
                reason = llm_check.get("reason", "Требуется проверка модератора")
                found_issues = llm_check.get("found_issues", [])
                
                issues_text = ""
                if found_issues:
                    issues_text = "*Обнаруженные проблемы:*\n" + "\n".join([f"• {issue}" for issue in found_issues]) + "\n\n"
                
                await message.answer(
                    f"🟡 *Отзыв отправлен на модерацию*\n\n"
                    f"📍 Место: *{place_name}*\n"
                    f"⭐ Оценка: *{rating}/5*\n\n"
                    f"📝 *Краткое содержание:*\n{summary}\n\n"
                    f"{issues_text}"
                    f"⏳ *Статус:* Ожидает проверки модератором\n"
                    f"Мы уведомим вас о результате.\n\n"
                    f"ID отзыва: `{review_id}`",
                    parse_mode="Markdown",
                    reply_markup=get_back_keyboard()
                )
            else:
                # Неизвестный статус
                await message.answer(
                    f"✅ *Отзыв отправлен!*\n\n"
                    f"📍 Место: *{place_name}*\n"
                    f"⭐ Оценка: *{rating}/5*\n\n"
                    f"📝 *Краткое содержание:*\n{summary}\n\n"
                    f"⏳ *Статус:* {moderation_status}\n"
                    f"Мы уведомим вас о результате.",
                    parse_mode="Markdown",
                    reply_markup=get_back_keyboard()
                )
        else:
            await message.answer(
                "❌ *Не удалось отправить отзыв.*\n\n"
                "API не вернул ответ. Попробуйте позже.",
                parse_mode="Markdown",
                reply_markup=get_back_keyboard()
            )
        
    except Exception as e:
        logger.error(f"Ошибка отправки отзыва: {e}", exc_info=True)
        await message.answer(
            f"❌ *Ошибка отправки отзыва.*\n\n"
            f"Ошибка: {str(e)[:100]}\n\n"
            f"Попробуйте позже.",
            parse_mode="Markdown",
            reply_markup=get_back_keyboard()
        )
    
    await state.clear()

@router.callback_query(F.data == "cancel")
async def cancel_review(callback: CallbackQuery, state: FSMContext):
    """Отмена отзыва"""
    await state.clear()
    await callback.message.edit_text(
        "⏹ *Создание отзыва отменено.*\n\n"
        "Вы можете оставить отзыв в другой раз.",
        parse_mode="Markdown",
        reply_markup=get_back_keyboard()
    )
    await callback.answer()

# @router.callback_query(F.data.startswith("place:"))
# async def show_place_details(callback: CallbackQuery):
#     place_id = int(callback.data.split(":")[1])
#     place = MOCK_PLACES.get(place_id)
#     if not place:
#         await callback.message.edit_text("❌ Место не найдено.")
#         await callback.answer()
#         return
    
#     full_stars = int(place["rating_avg"])
#     half_star = "½" if place["rating_avg"] - full_stars >= 0.5 else ""
#     stars_text = f"{'⭐' * full_stars}{half_star} {place['rating_avg']:.1f} ({place['rating_count']})"
    
#     await callback.message.edit_text(
#         f"📍 *{place['name']}*\n\n{place['description']}\n\n⭐ {stars_text}\n📌 {place['address']}",
#         reply_markup=get_place_keyboard(place_id),
#         parse_mode="Markdown"
#     )
#     await callback.answer()

@router.callback_query(F.data.startswith("view_reviews:"))
async def view_reviews(callback: CallbackQuery):
    """Просмотр отзывов места"""
    try:
        place_uuid = callback.data.split(":", 1)[1]
        
        # Получаем место
        place_info = await http_client.get_place(place_uuid)
        
        if not place_info:
            await callback.answer("❌ Место не найдено", show_alert=True)
            return
        
        rating = place_info.get("rating", 0.0)
        review_count = place_info.get("review_count", 0)
        
        reviews_text = (
            f"📝 *Отзывы о месте*\n\n"
            f"📍 *{place_info['name']}*\n\n"
            f"⭐ Общий рейтинг: *{rating:.1f}/5*\n"
            f"📊 Количество отзывов: *{review_count}*\n\n"
        )
        
        if review_count > 0:
            reviews_text += "*Последние отзывы:*\n"
            
            # Пробуем получить отзывы через API (если есть метод)
            try:
                reviews_response = await http_client.get_place_reviews(place_uuid, limit=3)
                if reviews_response and isinstance(reviews_response, list):
                    for review in reviews_response[:3]:
                        if isinstance(review, dict):
                            user_rating = review.get("rating", 0)
                            review_text = review.get("text", "")[:60]
                            reviews_text += f"⭐ {user_rating}/5: {review_text}...\n"
                else:
                    reviews_text += "• Отзывы загружаются...\n"
            except:
                reviews_text += "• Отзывы загружаются...\n"
        else:
            reviews_text += "📭 *Пока нет отзывов.*\nБудьте первым!"
        
        await callback.message.edit_text(
            reviews_text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✍️ Оставить отзыв", callback_data=f"review:{place_uuid}")],
                [InlineKeyboardButton(text="🔙 Назад", callback_data=f"place_back:{place_uuid}")]
            ])
        )
        
    except Exception as e:
        logger.error(f"Ошибка просмотра отзывов: {e}", exc_info=True)
        await callback.answer("❌ Ошибка загрузки отзывов", show_alert=True)
    
    await callback.answer()

@router.callback_query(F.data.startswith("place_back:"))
async def back_to_place(callback: CallbackQuery):
    """Возврат к карточке места"""
    try:
        place_uuid = callback.data.split(":", 1)[1]
        
        # Получаем информацию о месте
        place_info = await http_client.get_place(place_uuid)
        
        if not place_info:
            await callback.answer("❌ Место не найдено", show_alert=True)
            return
        
        rating = place_info.get("rating", 0.0)
        review_count = place_info.get("review_count", 0)
        address = place_info.get("address", "Адрес не указан")
        category = place_info.get("category", "other")
        
        # Эмодзи для категорий
        category_emoji = {
            "cafe": "☕",
            "restaurant": "🍽️",
            "park": "🌳",
            "museum": "🏛️",
            "cinema": "🎬",
            "theatre": "🎭",
            "art": "🎨"
        }.get(category, "📍")
        
        place_text = (
            f"📍 *{category_emoji} {place_info['name']}*\n\n"
            f"📝 {place_info.get('description', 'Описание отсутствует')}\n\n"
            f"⭐ Рейтинг: *{rating}/5* ({review_count} отзывов)\n"
            f"📍 Адрес: {address}\n"
            f"🏷️ Категория: {category}"
        )
        
        await callback.message.edit_text(
            place_text,
            parse_mode="Markdown",
            reply_markup=get_place_keyboard(place_uuid)
        )
        
    except Exception as e:
        logger.error(f"Ошибка возврата к месту: {e}")
        await callback.answer("❌ Ошибка загрузки места", show_alert=True)
    
    await callback.answer()

# # 🎯 Обработчик «Назад» (чтобы работал из отзыва)
# @router.callback_query(F.data == "back_to_main")
# async def back_to_main_from_review(callback: CallbackQuery):
#     await callback.message.edit_text(
#         "✅ Вы вернулись в главное меню.\n\n"
#         "Напишите, что вам хочется — например:\n"
#         "• _«Хочу сходить на концерт»_\n"
#         "• _«Нужно уютное кафе»_\n"
#         "• _«Что посмотреть в центре?»_\n\n"
#         "Или воспользуйтесь кнопками ниже:",
#         parse_mode="Markdown",
#         reply_markup=MAIN_INLINE_KEYBOARD
#     )
#     await callback.answer()