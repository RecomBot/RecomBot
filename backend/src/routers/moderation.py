# backend/src/routers/moderation.py
from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from uuid import UUID
from ..dependencies import get_db_session
from ..models import User, Review, ModerationStatus, UserRole
from ..schemas.review import ReviewResponse, ReviewUpdate
from ..services.recommendation import RecommendationService
from ..services.cache import CacheService
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/moderation", tags=["Moderation"])

async def verify_moderator(
    telegram_id: int,
    db: AsyncSession
) -> User:
    """Проверить, что пользователь - модератор"""
    result = await db.execute(
        select(User).where(
            User.telegram_id == telegram_id,
            User.role.in_([UserRole.MODERATOR, UserRole.ADMIN])
        )
    )
    moderator = result.scalar_one_or_none()
    
    if not moderator:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только модераторы и администраторы могут выполнять это действие"
        )
    
    return moderator

@router.get("/queue", response_model=List[ReviewResponse])
async def get_moderation_queue(
    telegram_id: int = Body(..., embed=True, gt=0),
    limit: int = Body(20, embed=True, ge=1, le=100),
    db: AsyncSession = Depends(get_db_session)
):
    """Получить очередь отзывов на модерацию"""
    await verify_moderator(telegram_id, db)
    
    result = await db.execute(
        select(Review)
        .where(Review.moderation_status.in_([ModerationStatus.PENDING, ModerationStatus.FLAGGED_BY_LLM]))
        .order_by(Review.created_at.asc())
        .limit(limit)
    )
    
    reviews = result.scalars().all()
    return [ReviewResponse.model_validate(r) for r in reviews]

@router.post("/reviews/{review_id}/approve", response_model=ReviewResponse)
async def approve_review(
    review_id: UUID,
    telegram_id: int = Body(..., embed=True, gt=0),
    notes: Optional[str] = Body(None, embed=True),
    db: AsyncSession = Depends(get_db_session),
    cache: CacheService = Depends(get_db_session)  # TODO: исправить
):
    """Одобрить отзыв"""
    moderator = await verify_moderator(telegram_id, db)
    
    # Находим отзыв
    result = await db.execute(
        select(Review).where(Review.id == review_id)
    )
    review = result.scalar_one_or_none()
    
    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Отзыв не найден"
        )
    
    if review.moderation_status == ModerationStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Отзыв уже одобрен"
        )
    
    try:
        old_status = review.moderation_status
        review.moderation_status = ModerationStatus.APPROVED
        review.moderated_by = moderator.id
        if notes:
            review.moderation_notes = notes
        
        await db.flush()
        
        # Обновляем рейтинг места
        if old_status != ModerationStatus.APPROVED:
            rec_service = RecommendationService(cache)
            await rec_service.update_place_rating(db, review.place_id)
            
            # Очищаем кэш рекомендаций для этого места
            await cache.clear_pattern(f"recs:*:place:{review.place_id}:*")
        
        await db.commit()
        await db.refresh(review)
        
        logger.info(f"Review {review_id} approved by moderator {moderator.id}")
        return ReviewResponse.model_validate(review)
        
    except Exception as e:
        await db.rollback()
        logger.error(f"Error approving review: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при одобрении отзыва"
        )

@router.post("/reviews/{review_id}/reject", response_model=ReviewResponse)
async def reject_review(
    review_id: UUID,
    telegram_id: int = Body(..., embed=True, gt=0),
    notes: Optional[str] = Body(None, embed=True),
    db: AsyncSession = Depends(get_db_session),
    cache: CacheService = Depends(get_db_session)  # TODO: исправить
):
    """Отклонить отзыв"""
    moderator = await verify_moderator(telegram_id, db)
    
    result = await db.execute(
        select(Review).where(Review.id == review_id)
    )
    review = result.scalar_one_or_none()
    
    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Отзыв не найден"
        )
    
    if review.moderation_status == ModerationStatus.REJECTED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Отзыв уже отклонен"
        )
    
    try:
        old_status = review.moderation_status
        review.moderation_status = ModerationStatus.REJECTED
        review.moderated_by = moderator.id
        if notes:
            review.moderation_notes = notes
        
        await db.flush()
        
        # Если отзыв был одобрен, обновляем рейтинг места
        if old_status == ModerationStatus.APPROVED:
            rec_service = RecommendationService(cache)
            await rec_service.update_place_rating(db, review.place_id)
            
            # Очищаем кэш
            await cache.clear_pattern(f"recs:*:place:{review.place_id}:*")
        
        await db.commit()
        await db.refresh(review)
        
        logger.info(f"Review {review_id} rejected by moderator {moderator.id}")
        return ReviewResponse.model_validate(review)
        
    except Exception as e:
        await db.rollback()
        logger.error(f"Error rejecting review: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при отклонении отзыва"
        )