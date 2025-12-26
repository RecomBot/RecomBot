# backend/src/utils/rating_updater.py
"""
Утилиты для обновления рейтингов мест
"""

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func

from database import Review, Place

logger = logging.getLogger(__name__)


async def update_place_rating(db: AsyncSession, place_id: UUID) -> dict:
    """Обновляет средний рейтинг места на основе всех одобренных отзывов"""
    try:
        # Получаем все одобренные отзывы для места
        result = await db.execute(
            select(Review.rating)
            .where(
                Review.place_id == place_id,
                Review.moderation_status == "approved"
            )
        )
        ratings = result.scalars().all()
        
        # Также получаем количество отзывов для информации
        count_result = await db.execute(
            select(func.count(Review.id))
            .where(
                Review.place_id == place_id,
                Review.moderation_status == "approved"
            )
        )
        review_count = count_result.scalar()
        
        if not ratings:
            # Если отзывов нет - рейтинг 0.0
            avg_rating = 0.0
        else:
            # Рассчитываем средний рейтинг с округлением до 1 знака после запятой
            avg_rating = round(sum(ratings) / len(ratings), 1)
        
        # Обновляем рейтинг места
        await db.execute(
            update(Place)
            .where(Place.id == place_id)
            .values(rating=avg_rating)
        )
        
        logger.info(f"Обновлен рейтинг места {place_id}: {avg_rating} (на основе {review_count} отзывов)")
        return {
            "place_id": place_id,
            "rating": avg_rating,
            "review_count": review_count
        }
        
    except Exception as e:
        logger.error(f"Ошибка обновления рейтинга места {place_id}: {e}")
        raise


async def update_all_place_ratings(db: AsyncSession):
    """Обновляет рейтинги всех мест"""
    try:
        # Получаем все места
        result = await db.execute(select(Place.id))
        place_ids = result.scalars().all()
        
        updated_count = 0
        for place_id in place_ids:
            await update_place_rating(db, place_id)
            updated_count += 1
        
        await db.commit()
        logger.info(f"Обновлены рейтинги для {updated_count} мест")
        
    except Exception as e:
        logger.error(f"Ошибка обновления рейтингов: {e}")