# backend/src/routers/reviews.py
"""
Роутер для работы с отзывами
"""

from uuid import UUID
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

# Универсальные импорты
try:
    from ..database import get_db, Place, Review, User
    from ..schemas.review import ReviewCreate, ReviewResponse
    from ..dependencies import get_current_user, require_moderator
    from ..services.llm_service import LLMService
    from ..utils.rating_updater import update_place_rating
except ImportError:
    from database import get_db, Place, Review, User
    from schemas.review import ReviewCreate, ReviewResponse
    from dependencies import get_current_user, require_moderator
    from services.llm_service import LLMService
    from utils.rating_updater import update_place_rating

router = APIRouter()


async def has_active_review(db: AsyncSession, user_id: UUID, place_id: UUID) -> bool:
    """Проверяет, есть ли у пользователя активный отзыв на место"""
    result = await db.execute(
        select(Review).where(
            Review.user_id == user_id,
            Review.place_id == place_id,
            Review.moderation_status.in_(["approved", "pending"])
        )
    )
    return result.scalar_one_or_none() is not None


async def get_latest_user_review(db: AsyncSession, user_id: UUID, place_id: UUID) -> Optional[Review]:
    """Получает последний отзыв пользователя на место"""
    result = await db.execute(
        select(Review).where(
            Review.user_id == user_id,
            Review.place_id == place_id
        ).order_by(Review.created_at.desc()).limit(1)
    )
    return result.scalar_one_or_none()


@router.post("/", response_model=ReviewResponse, status_code=201)
async def create_review(
    review_data: ReviewCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Создание отзыва с LLM проверкой"""
    try:
        # Проверяем место
        place_result = await db.execute(
            select(Place).where(Place.id == review_data.place_id, Place.is_active == True)
        )
        place = place_result.scalar_one_or_none()
        
        if not place:
            raise HTTPException(status_code=404, detail="Место не найдено")
        
        # Проверяем, есть ли активный отзыв
        if await has_active_review(db, current_user.id, review_data.place_id):
            latest_review = await get_latest_user_review(db, current_user.id, review_data.place_id)
            
            if latest_review and latest_review.moderation_status == "rejected":
                raise HTTPException(
                    status_code=400, 
                    detail=f"Ваш предыдущий отзыв был отклонен. Причина: {latest_review.moderation_notes or 'нарушение правил'}"
                )
            else:
                raise HTTPException(
                    status_code=400, 
                    detail="У вас уже есть активный отзыв на это место"
                )
        
        # LLM проверка
        llm_service = LLMService()
        llm_check = await llm_service.check_review_content(review_data.text)
        summary = await llm_service.summarize_review(review_data.text, review_data.rating)
        
        # Определяем статус модерации на основе LLM проверки
        if llm_check.get("is_appropriate", True):
            moderation_status = "approved"
            should_update_rating = True
        else:
            moderation_status = "flagged_by_llm"
            should_update_rating = False
        
        # Определяем sentiment_score
        sentiment_score = llm_check.get("confidence", 0.5)
        if not llm_check.get("is_appropriate", True):
            sentiment_score = 0.0

        new_review = Review(
            user_id=current_user.id,
            place_id=review_data.place_id,
            rating=review_data.rating,
            text=review_data.text,
            llm_check=llm_check,
            summary=summary,
            sentiment_score=sentiment_score,
            moderation_status=moderation_status
        )
        
        db.add(new_review)
        await db.flush()
        await db.refresh(new_review)

        if should_update_rating:
            await update_place_rating(db, review_data.place_id)

        return ReviewResponse(
            id=new_review.id,
            user_id=new_review.user_id,
            place_id=new_review.place_id,
            rating=new_review.rating,
            text=new_review.text,
            summary=new_review.summary,
            moderation_status=new_review.moderation_status,
            created_at=new_review.created_at.isoformat(),
            helpful_count=new_review.helpful_count
        )
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=List[ReviewResponse])
async def get_reviews(
    place_id: Optional[UUID] = Query(None),
    only_approved: bool = Query(True),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """Получение отзывов"""
    try:
        query = select(Review)
        
        if place_id:
            query = query.where(Review.place_id == place_id)
        if only_approved:
            query = query.where(Review.moderation_status == "approved")
        
        query = query.order_by(Review.created_at.desc()).limit(limit)
        result = await db.execute(query)
        reviews = result.scalars().all()
        
        return [
            ReviewResponse(
                id=r.id,
                user_id=r.user_id,
                place_id=r.place_id,
                rating=r.rating,
                text=r.text,
                summary=r.summary,
                moderation_status=r.moderation_status,
                created_at=r.created_at.isoformat(),
                helpful_count=r.helpful_count
            )
            for r in reviews
        ]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/user/{user_id}/place/{place_id}")
async def get_user_review_for_place(
    user_id: UUID,
    place_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Получение всех отзывов пользователя на конкретное место"""
    try:
        result = await db.execute(
            select(Review)
            .where(
                Review.user_id == user_id,
                Review.place_id == place_id
            )
            .order_by(Review.created_at.desc())
        )
        
        reviews = result.scalars().all()
        
        return {
            "user_id": user_id,
            "place_id": place_id,
            "reviews": [
                {
                    "id": r.id,
                    "rating": r.rating,
                    "text": r.text[:100] + "..." if len(r.text) > 100 else r.text,
                    "moderation_status": r.moderation_status,
                    "moderation_notes": r.moderation_notes,
                    "created_at": r.created_at.isoformat(),
                    "summary": r.summary
                }
                for r in reviews
            ],
            "total": len(reviews),
            "has_active_review": any(r.moderation_status in ["approved", "pending"] for r in reviews)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{review_id}")
async def delete_review(
    review_id: UUID,
    current_user: User = Depends(require_moderator),
    db: AsyncSession = Depends(get_db)
):
    """Удаление отзыва (с обновлением рейтинга места)"""
    try:
        # Получаем отзыв
        result = await db.execute(
            select(Review).where(Review.id == review_id)
        )
        review = result.scalar_one_or_none()
        
        if not review:
            raise HTTPException(status_code=404, detail="Отзыв не найдено")
        
        # Сохраняем place_id для обновления рейтинга
        place_id = review.place_id
        
        # Удаляем отзыв
        await db.delete(review)
        await db.flush()
        
        # Обновляем рейтинг места
        await update_place_rating(db, place_id)
        
        await db.commit()
        
        return {
            "success": True,
            "message": "Отзыв удален",
            "place_id": place_id,
            "deleted_by": current_user.username,
            "user_role": current_user.role
        }
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))