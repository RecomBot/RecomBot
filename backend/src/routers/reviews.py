# backend/src/routers/reviews.py
from fastapi import APIRouter, Depends, HTTPException, status, Body, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from uuid import UUID
from ..dependencies import get_db_session, get_llm
from ..models import User, Place, Review, ModerationStatus, UserRole
from ..schemas.review import ReviewCreate, ReviewResponse, ReviewWithRelationsResponse
from ..services.recommendation import RecommendationService
from ..services.cache import CacheService
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/reviews", tags=["Reviews"])

@router.post("/", response_model=ReviewResponse, status_code=status.HTTP_201_CREATED)
async def create_review(
    review_data: ReviewCreate,
    telegram_id: int = Body(..., embed=True, gt=0),
    db: AsyncSession = Depends(get_db_session),
    llm = Depends(get_llm),
    cache: CacheService = Depends(get_db_session)  # TODO: исправить зависимость
):
    """Создать отзыв"""
    # 1. Находим пользователя
    user_result = await db.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = user_result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден"
        )
    
    # 2. Находим место
    place_result = await db.execute(
        select(Place).where(Place.id == review_data.place_id, Place.is_active == True)
    )
    place = place_result.scalar_one_or_none()
    
    if not place:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Место не найдено"
        )
    
    # 3. Проверяем, не оставлял ли пользователь уже отзыв на это место
    existing_review_result = await db.execute(
        select(Review).where(
            Review.user_id == user.id,
            Review.place_id == review_data.place_id
        )
    )
    existing_review = existing_review_result.scalar_one_or_none()
    
    if existing_review:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Вы уже оставляли отзыв на это место"
        )
    
    # 4. Проверяем контент через LLM
    llm_check = await llm.check_review_content(review_data.text)
    summary = await llm.summarize_review(review_data.text, review_data.rating)
    
    # Определяем статус модерации
    if llm_check.get("is_appropriate", True):
        moderation_status = ModerationStatus.APPROVED
    else:
        moderation_status = ModerationStatus.FLAGGED_BY_LLM
    
    # 5. Создаем отзыв
    from uuid import uuid4
    new_review = Review(
        id=uuid4(),
        user_id=user.id,
        place_id=review_data.place_id,
        rating=review_data.rating,
        text=review_data.text,
        summary=summary,
        moderation_status=moderation_status,
        llm_check=llm_check
    )
    
    try:
        db.add(new_review)
        await db.flush()  # Получаем ID без коммита
        
        # 6. Обновляем рейтинг места (если отзыв одобрен)
        if moderation_status == ModerationStatus.APPROVED:
            from ..services.recommendation import RecommendationService
            rec_service = RecommendationService(cache)
            await rec_service.update_place_rating(db, review_data.place_id)
        
        await db.commit()
        await db.refresh(new_review)
        
        # 7. Очищаем кэш рекомендаций для этого пользователя
        await cache.clear_pattern(f"recs:user:{user.id}:*")
        
        logger.info(f"Review created: user={user.id}, place={review_data.place_id}, rating={review_data.rating}")
        return ReviewResponse.model_validate(new_review)
        
    except Exception as e:
        await db.rollback()
        logger.error(f"Error creating review: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при создании отзыва"
        )

@router.get("/place/{place_id}", response_model=List[ReviewWithRelationsResponse])
async def get_reviews_by_place(
    place_id: UUID,
    show_pending: bool = Query(False),
    db: AsyncSession = Depends(get_db_session)
):
    """Получить отзывы по месту"""
    query = select(Review).where(Review.place_id == place_id)
    
    if not show_pending:
        query = query.where(Review.moderation_status == ModerationStatus.APPROVED)
    
    query = query.order_by(Review.created_at.desc())
    
    result = await db.execute(query)
    reviews = result.scalars().all()
    
    # Загружаем связанные данные
    response_reviews = []
    for review in reviews:
        # Нужно загрузить user и place
        user_result = await db.execute(select(User).where(User.id == review.user_id))
        place_result = await db.execute(select(Place).where(Place.id == review.place_id))
        
        review_dict = ReviewWithRelationsResponse.model_validate(review)
        review_dict.user = user_result.scalar_one()
        review_dict.place = place_result.scalar_one()
        
        if review.moderated_by:
            mod_result = await db.execute(select(User).where(User.id == review.moderated_by))
            review_dict.moderator = mod_result.scalar_one()
        
        response_reviews.append(review_dict)
    
    return response_reviews

@router.get("/user/{user_id}", response_model=List[ReviewResponse])
async def get_reviews_by_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db_session)
):
    """Получить отзывы пользователя"""
    result = await db.execute(
        select(Review)
        .where(Review.user_id == user_id)
        .order_by(Review.created_at.desc())
    )
    reviews = result.scalars().all()
    return [ReviewResponse.model_validate(r) for r in reviews]