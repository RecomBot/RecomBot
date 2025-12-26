# backend/src/routers/moderation.py
"""
Роутер для модерации контента
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

# Универсальные импорты
try:
    from ..database import get_db, Review, User
    from ..schemas.review import ReviewModeration
    from ..dependencies import get_current_user, require_moderator
    from ..utils.rating_updater import update_place_rating
except ImportError:
    from database import get_db, Review, User
    from schemas.review import ReviewModeration
    from dependencies import get_current_user, require_moderator
    from utils.rating_updater import update_place_rating

router = APIRouter()


@router.get("/pending-reviews")
async def get_pending_reviews(
    current_user: User = Depends(require_moderator),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """Отзывы на модерацию"""
    try:
        result = await db.execute(
            select(Review)
            .where(Review.moderation_status.in_(["pending", "flagged_by_llm"]))
            .order_by(Review.created_at.asc())
            .limit(limit)
        )
        
        reviews = result.scalars().all()
        reviews_with_details = []
        
        for review in reviews:
            reviews_with_details.append({
                "id": review.id,
                "user_id": review.user_id,
                "place_id": review.place_id,
                "rating": review.rating,
                "text": review.text,
                "summary": review.summary,
                "llm_check": review.llm_check,
                "moderation_status": review.moderation_status,
                "created_at": review.created_at.isoformat()
            })
        
        return {"reviews": reviews_with_details, "total": len(reviews_with_details)}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reviews/{review_id}/approve")
async def approve_review(
    review_id: UUID,
    current_user: User = Depends(require_moderator),
    db: AsyncSession = Depends(get_db)
):
    """Одобрение отзыва"""
    try:
        result = await db.execute(
            select(Review).where(Review.id == review_id)
        )
        review = result.scalar_one_or_none()
        
        if not review:
            raise HTTPException(status_code=404, detail="Отзыв не найдено")
        
        # Получаем текущий статус отзыва
        old_status = review.moderation_status
        
        review.moderation_status = "approved"
        review.moderated_by = current_user.id
        review.moderated_at = func.now()
        
        # Обновляем рейтинг места
        await update_place_rating(db, review.place_id)

        await db.commit()
        return {
            "success": True, 
            "message": "Отзыв одобрен", 
            "moderator_id": str(current_user.id),
            "old_status": old_status
        }
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reviews/{review_id}/reject")
async def reject_review(
    review_id: UUID,
    moderation_data: ReviewModeration,
    current_user: User = Depends(require_moderator),
    db: AsyncSession = Depends(get_db)
):
    """Отклонение отзыва"""
    try:
        result = await db.execute(
            select(Review).where(Review.id == review_id)
        )
        review = result.scalar_one_or_none()
        
        if not review:
            raise HTTPException(status_code=404, detail="Отзыв не найден")
        
        # Получаем текущий статус отзыва
        old_status = review.moderation_status

        review.moderation_status = "rejected"
        review.moderated_by = current_user.id
        review.moderated_at = func.now()
        review.moderation_notes = moderation_data.notes
        
        # ОБНОВЛЯЕМ РЕЙТИНГ МЕСТА ЕСЛИ ОТЗЫВ БЫЛ ОДОБРЕН РАНЬШЕ
        if old_status == "approved":
            await update_place_rating(db, review.place_id)

        await db.commit()
        return {
            "success": True, 
            "message": "Отзыв отклонен",
            "old_status": old_status,
            "place_rating_updated": old_status == "approved",
            "moderator_id": str(current_user.id)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))