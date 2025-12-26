# backend/src/routers/recommendations.py
"""
Роутер для рекомендаций
"""

from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

# Универсальные импорты
try:
    from ..database import get_db, Place, User
    from ..schemas.recommendation import RecommendationRequest, RecommendationResponse
    from ..dependencies import get_current_user
    from ..services.llm_service import LLMService
except ImportError:
    from database import get_db, Place, User
    from schemas.recommendation import RecommendationRequest, RecommendationResponse
    from dependencies import get_current_user
    from services.llm_service import LLMService

router = APIRouter()


@router.get("/", response_model=RecommendationResponse)
async def get_recommendations(
    category: Optional[str] = None,
    city: Optional[str] = None,
    limit: int = 10,
    db: AsyncSession = Depends(get_db)
):
    """Базовые рекомендации по категориям"""
    try:
        query = select(Place).where(Place.is_active == True)
        
        if category:
            query = query.where(Place.category == category)
        if city:
            query = query.where(Place.city == city)
        
        query = query.order_by(func.random()).limit(limit)
        result = await db.execute(query)
        places = result.scalars().all()
        
        return RecommendationResponse(
            recommendations=[
                {
                    "id": p.id,
                    "name": p.name,
                    "category": p.category,
                    "city": p.city,
                    "description": p.description,
                    "price_level": p.price_level
                }
                for p in places
            ],
            source="database"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/personal", response_model=RecommendationResponse)
async def get_personal_recommendations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Персонализированные рекомендации через LLM"""
    try:
        llm_service = LLMService()
        recommendations = await llm_service.generate_recommendations(current_user.id, db)
        
        if recommendations:
            return RecommendationResponse(
                recommendations=recommendations,
                source="ollama"
            )
        else:
            # Fallback: простые рекомендации по категориям
            categories = current_user.preferences.get("categories", ["cafe", "restaurant"]) if current_user.preferences else ["cafe"]
            
            places_result = await db.execute(
                select(Place)
                .where(Place.category.in_(categories), Place.is_active == True)
                .limit(5)
            )
            places = places_result.scalars().all()
            
            return RecommendationResponse(
                recommendations=[
                    {"id": p.id, "name": p.name, "category": p.category, "description": p.description}
                    for p in places
                ],
                source="database_fallback"
            )
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat", response_model=RecommendationResponse)
async def get_chat_recommendations(
    request: RecommendationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Рекомендации через чат-интерфейс"""
    try:
        # Обновляем предпочтения если переданы
        if request.categories or request.city or request.budget:
            if not current_user.preferences:
                current_user.preferences = {}
            
            if request.categories:
                current_user.preferences["categories"] = request.categories
            if request.city:
                current_user.preferences["city"] = request.city
            if request.budget:
                current_user.preferences["budget"] = request.budget
            
            await db.commit()
        
        # Генерируем рекомендации через LLM
        llm_service = LLMService()
        recommendations = await llm_service.generate_recommendations(current_user.id, db)
        
        if recommendations:
            return RecommendationResponse(
                recommendations=recommendations,
                source="llm_recommendations"
            )
        else:
            return RecommendationResponse(
                recommendations=["Пока не могу сгенерировать персонализированные рекомендации. Попробуйте позже или уточните ваши предпочтения."],
                source="fallback_message"
            )
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))