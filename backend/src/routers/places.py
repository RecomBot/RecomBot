# backend/src/routers/places.py
"""
Роутер для работы с местами
"""

from uuid import UUID
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

# Универсальные импорты
try:
    from ..database import get_db, Place, Review, User
    from ..schemas.place import PlaceCreate, PlaceResponse, PlaceStats
    from ..dependencies import get_current_user, require_moderator
    from ..utils.rating_updater import update_place_rating
except ImportError:
    from database import get_db, Place, Review, User
    from schemas.place import PlaceCreate, PlaceResponse, PlaceStats
    from dependencies import get_current_user, require_moderator
    from utils.rating_updater import update_place_rating

router = APIRouter()


@router.get("/", response_model=dict)
async def get_places(
    category: Optional[str] = None,
    city: Optional[str] = None,
    min_rating: Optional[float] = Query(None, ge=0.0, le=5.0),
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """Получение списка мест"""
    try:
        query = select(Place).where(Place.is_active == True)
        
        if category:
            query = query.where(Place.category == category)
        if city:
            query = query.where(Place.city == city)
        if min_rating is not None:
            query = query.where(Place.rating >= min_rating)
        
        query = query.offset(offset).limit(limit)
        result = await db.execute(query)
        places = result.scalars().all()
        
        places_response = []
        for p in places:
            # Получаем количество отзывов для каждого места
            count_result = await db.execute(
                select(func.count(Review.id))
                .where(
                    Review.place_id == p.id,
                    Review.moderation_status == "approved"
                )
            )
            review_count = count_result.scalar()
            
            places_response.append(PlaceResponse(
                id=p.id,
                name=p.name,
                description=p.description,
                category=p.category,
                address=p.address,
                city=p.city,
                price_level=p.price_level,
                tags=p.tags,
                rating=p.rating,
                review_count=review_count,
                is_active=p.is_active
            ))
        
        return {
            "places": places_response,
            "total": len(places)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{place_id}", response_model=PlaceResponse)
async def get_place(
    place_id: UUID, 
    db: AsyncSession = Depends(get_db)
):
    """Получение конкретного места"""
    try:
        result = await db.execute(
            select(Place).where(Place.id == place_id, Place.is_active == True)
        )
        place = result.scalar_one_or_none()
        
        if not place:
            raise HTTPException(status_code=404, detail="Место не найдено")
        
        # Получаем количество отзывов
        count_result = await db.execute(
            select(func.count(Review.id))
            .where(
                Review.place_id == place_id,
                Review.moderation_status == "approved"
            )
        )
        review_count = count_result.scalar()
        
        response = PlaceResponse.from_orm(place)
        response_dict = response.dict()
        response_dict["review_count"] = review_count
        
        return response_dict
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{place_id}/stats", response_model=PlaceStats)
async def get_place_stats(
    place_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Получение статистики по месту"""
    try:
        # Проверяем существует ли место
        place_result = await db.execute(
            select(Place).where(Place.id == place_id, Place.is_active == True)
        )
        place = place_result.scalar_one_or_none()
        
        if not place:
            raise HTTPException(status_code=404, detail="Место не найдено")
        
        # Получаем распределение рейтингов
        rating_distribution = await db.execute(
            select(Review.rating, func.count(Review.id))
            .where(
                Review.place_id == place_id,
                Review.moderation_status == "approved"
            )
            .group_by(Review.rating)
            .order_by(Review.rating)
        )
        
        distribution = {str(rating): count for rating, count in rating_distribution}
        
        # Получаем общее количество отзывов
        count_result = await db.execute(
            select(func.count(Review.id))
            .where(
                Review.place_id == place_id,
                Review.moderation_status == "approved"
            )
        )
        total_reviews = count_result.scalar()
        
        # Получаем последние отзывы
        recent_reviews_result = await db.execute(
            select(Review)
            .where(
                Review.place_id == place_id,
                Review.moderation_status == "approved"
            )
            .order_by(Review.created_at.desc())
            .limit(5)
        )
        recent_reviews = recent_reviews_result.scalars().all()
        
        return PlaceStats(
            place_id=place_id,
            name=place.name,
            current_rating=place.rating,
            total_reviews=total_reviews,
            rating_distribution=distribution,
            recent_reviews=[
                {
                    "id": r.id,
                    "rating": r.rating,
                    "summary": r.summary,
                    "created_at": r.created_at.isoformat()
                }
                for r in recent_reviews
            ]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/", response_model=PlaceResponse, status_code=201)
async def create_place(
    place_data: PlaceCreate,
    current_user: User = Depends(require_moderator),
    db: AsyncSession = Depends(get_db)
):
    """Создание нового места (только для модераторов и администраторов)"""
    try:
        new_place = Place(
            name=place_data.name,
            description=place_data.description,
            category=place_data.category,
            address=place_data.address,
            city=place_data.city,
            price_level=place_data.price_level,
            tags=place_data.tags,
            is_active=True,
            created_by=current_user.id
        )
        
        db.add(new_place)
        await db.flush()
        await db.refresh(new_place)
        
        return PlaceResponse.from_orm(new_place)
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))