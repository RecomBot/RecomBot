# GidRecBot/bot/notifications.py (НОВЫЙ ФАЙЛ)
from aiogram import Bot
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

class NotificationService:
    """Сервис для отправки уведомлений пользователям"""
    
    def __init__(self, bot: Bot):
        self.bot = bot
    
    async def send_moderation_result(
        self,
        telegram_id: int,
        review_id: str,
        place_name: str,
        status: str,
        reason: str = None,
        summary: str = None
    ):
        """Отправка результата модерации пользователю"""
        try:
            if status == "approved":
                message_text = (
                    f"✅ *Ваш отзыв опубликован!*\n\n"
                    f"📍 Место: *{place_name}*\n"
                    f"📝 ID отзыва: `{review_id}`\n\n"
                )
                
                if summary:
                    message_text += f"📋 *Краткое содержание:*\n{summary}\n\n"
                
                message_text += (
                    f"🎉 *Спасибо за ваш вклад!*\n"
                    f"Ваш отзыв поможет другим пользователям."
                )
            
            elif status == "rejected" or status == "flagged_by_llm":
                message_text = (
                    f"❌ *Ваш отзыв отклонен*\n\n"
                    f"📍 Место: *{place_name}*\n"
                    f"📝 ID отзыва: `{review_id}`\n\n"
                )
                
                if reason:
                    message_text += f"*Причина:* {reason}\n\n"
                
                message_text += (
                    f"⚠️ *Что можно сделать:*\n"
                    f"• Переформулируйте отзыв\n"
                    f"• Уберите оскорбительные выражения\n"
                    f"• Сосредоточьтесь на фактах\n\n"
                    f"Попробуйте оставить отзыв еще раз."
                )
            
            else:
                message_text = (
                    f"ℹ️ *Статус вашего отзыва изменен*\n\n"
                    f"📍 Место: *{place_name}*\n"
                    f"📝 ID отзыва: `{review_id}`\n\n"
                    f"*Новый статус:* {status}\n"
                )
            
            await self.bot.send_message(
                chat_id=telegram_id,
                text=message_text,
                parse_mode="Markdown"
            )
            
            logger.info(f"Уведомление отправлено пользователю {telegram_id} о отзыве {review_id}")
            
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления пользователю {telegram_id}: {e}")

# Глобальный экземпляр
notification_service = None

def init_notification_service(bot: Bot):
    """Инициализация сервиса уведомлений"""
    global notification_service
    notification_service = NotificationService(bot)
    return notification_service