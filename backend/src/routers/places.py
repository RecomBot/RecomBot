# backend/src/routers/places.py
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Optional
from uuid import UUID
from ..dependencies import get_db_session
from ..models import Place, PlaceCategory
from ..schemas.place import PlaceResponse, PlaceListResponse, PlaceCreate
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/places", tags=["Places"])

@router.get("/", response_model=List[PlaceResponse])
async def get_places(
    category: Optional[PlaceCategory] = None,
    city: Optional[str] = None,
    min_rating: Optional[float] = Query(None, ge=0, le=5),
    max_price: Optional[int] = Query(None, ge=1, le=5),
    search: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db_session)
):
    """Получить список мест с фильтрацией"""
    query = select(Place).where(Place.is_active == True)
    
    # Применяем фильтры
    if category:
        query = query.where(Place.category == category)
    if city:
        query = query.where(Place.city == city)
    if min_rating is not None:
        query = query.where(Place.rating >= min_rating)
    if max_price is not None:
        query = query.where(Place.price_level <= max_price)
    if search:
        query = query.where(
            func.lower(Place.name).contains(search.lower()) |
            func.lower(Place.description).contains(search.lower())
        )
    
    # Сортировка и пагинация
    query = query.order_by(
        Place.rating.desc(),
        Place.rating_count.desc(),
        Place.created_at.desc()
    ).offset(offset).limit(limit)
    
    result = await db.execute(query)
    places = result.scalars().all()
    
    return [PlaceResponse.model_validate(p) for p in places]

@router.get("/{place_id}", response_model=PlaceResponse)
async def get_place(
    place_id: UUID,
    db: AsyncSession = Depends(get_db_session)
):
    """Получить место по ID"""
    result = await db.execute(
        select(Place).where(Place.id == place_id, Place.is_active == True)
    )
    place = result.scalar_one_or_none()
    
    if not place:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Место не найдено"
        )
    
    return PlaceResponse.model_validate(place)

@router.post("/", response_model=PlaceResponse, status_code=status.HTTP_201_CREATED)
async def create_place(
    place_data: PlaceCreate,
    db: AsyncSession = Depends(get_db_session)
):
    """Создать новое место (для парсера/админов)"""
    # Проверяем, не существует ли уже такое место
    if place_data.external_id:
        result = await db.execute(
            select(Place).where(Place.external_id == place_data.external_id)
        )
        existing = result.scalar_one_or_none()
        if existing:
            return PlaceResponse.model_validate(existing)
    
    # Создаем новое место
    from uuid import uuid4
    new_place = Place(
        id=uuid4(),
        **place_data.model_dump(exclude_unset=True)
    )
    
    db.add(new_place)
    await db.commit()
    await db.refresh(new_place)
    
    logger.info(f"New place created: {new_place.name} in {new_place.city}")
    return PlaceResponse.model_validate(new_place)

@router.get("/categories/", response_model=List[str])
async def get_categories():
    """Получить список доступных категорий"""
    return [category.value for category in PlaceCategory]

@router.get("/cities/", response_model=List[str])
async def get_cities(db: AsyncSession = Depends(get_db_session)):
    """Получить список городов с местами"""
    result = await db.execute(
        select(Place.city)
        .where(Place.is_active == True)
        .distinct()
        .order_by(Place.city)
    )
    cities = result.scalars().all()
    return list(cities)