# backend/src/routers/recommendations.py
from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from ..dependencies import get_db_session, get_llm
from ..models import User, Place
from ..schemas.recommendation import RecommendationRequest, RecommendationResponse
from ..services.recommendation import RecommendationService
from ..services.cache import CacheService
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/recommendations", tags=["Recommendations"])

@router.post("/chat", response_model=RecommendationResponse)
async def get_chat_recommendations(
    request: RecommendationRequest,
    telegram_id: int = Body(..., embed=True, gt=0),
    db: AsyncSession = Depends(get_db_session),
    llm = Depends(get_llm),
    cache: CacheService = Depends(get_db_session)  # TODO: исправить
):
    """Получить рекомендации через LLM-чат"""
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
    
    # 2. Получаем рекомендации через сервис
    rec_service = RecommendationService(cache)
    places = await rec_service.get_recommendations_for_user(
        db=db,
        user_id=user.id,
        query=request.query,
        limit=request.limit
    )
    
    # 3. Генерируем текстовые рекомендации через LLM
    user_prefs = {
        "city": user.preferences.get('city', 'Moscow') if user.preferences else 'Moscow',
        "query": request.query
    }
    
    places_data = [
        {
            "name": p.name,
            "description": p.description or "",
            "category": p.category,
            "rating": p.rating,
            "price_level": p.price_level
        }
        for p in places
    ]
    
    recommendations_text = await llm.generate_recommendations(user_prefs, places_data)
    
    # 4. Формируем ответ
    return RecommendationResponse(
        text=recommendations_text,
        places=places,
        user_id=str(user.id),
        city=user_prefs['city'],
        query=request.query
    )

@router.post("/search", response_model=RecommendationResponse)
async def search_places(
    query: str = Body(..., embed=True, min_length=2, max_length=200),
    telegram_id: int = Body(..., embed=True, gt=0),
    limit: int = Body(5, embed=True, ge=1, le=20),
    db: AsyncSession = Depends(get_db_session),
    cache: CacheService = Depends(get_db_session)  # TODO: исправить
):
    """Поиск мест по запросу"""
    # Аналогично chat, но без LLM текста
    user_result = await db.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = user_result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден"
        )
    
    rec_service = RecommendationService(cache)
    places = await rec_service.get_recommendations_for_user(
        db=db,
        user_id=user.id,
        query=query,
        limit=limit
    )
    
    city = user.preferences.get('city', 'Moscow') if user.preferences else 'Moscow'
    
    return RecommendationResponse(
        text=f"Найдено {len(places)} мест в {city} по запросу «{query}»",
        places=places,
        user_id=str(user.id),
        city=city,
        query=query
    )