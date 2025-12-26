# backend/src/services/recommendation.py
from typing import List, Dict, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
import logging
from ..models import Place, User, Review
from shared.models.enums import PlaceCategory
from .cache import CacheService

logger = logging.getLogger(__name__)

class RecommendationService:
    """Сервис рекомендаций"""
    
    def __init__(self, cache_service: CacheService):
        self.cache = cache_service
    
    async def get_recommendations_for_user(
        self,
        db: AsyncSession,
        user_id: UUID,
        query: Optional[str] = None,
        limit: int = 10
    ) -> List[Place]:
        """Получить рекомендации для пользователя"""
        # 1. Получить пользователя и его предпочтения
        user_result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = user_result.scalar_one_or_none()
        
        if not user:
            return []
        
        city = user.preferences.get('city', 'Moscow') if user.preferences else 'Moscow'
        
        # 2. Попробовать получить из кэша
        cache_key = f"recs:user:{user_id}:city:{city}:query:{query or 'general'}"
        cached = await self.cache.get(cache_key)
        if cached:
            # В реальности нужно десериализовать места
            pass
        
        # 3. Базовые рекомендации по городу и рейтингу
        query_builder = select(Place).where(
            Place.city == city,
            Place.is_active == True
        )
        
        # 4. Если есть текст запроса, пытаемся понять категорию
        if query:
            category = self._detect_category_from_query(query)
            if category:
                query_builder = query_builder.where(Place.category == category)
            else:
                # Поиск по названию или описанию
                query_builder = query_builder.where(
                    or_(
                        Place.name.ilike(f"%{query}%"),
                        Place.description.ilike(f"%{query}%")
                    )
                )
        
        # 5. Сортировка по рейтингу
        query_builder = query_builder.order_by(
            Place.rating.desc(),
            Place.rating_count.desc()
        ).limit(limit)
        
        result = await db.execute(query_builder)
        places = result.scalars().all()
        
        # 6. Сохранить в кэш
        places_data = [self._place_to_dict(p) for p in places]
        await self.cache.set(cache_key, places_data, ttl=300)
        
        return places
    
    def _detect_category_from_query(self, query: str) -> Optional[PlaceCategory]:
        """Определить категорию из текстового запроса"""
        query_lower = query.lower()
        
        category_map = {
            PlaceCategory.CAFE: ['кафе', 'кофе', 'кофейня', 'завтрак', 'брunch', 'кофеен'],
            PlaceCategory.RESTAURANT: ['ресторан', 'ужин', 'обед', 'ужинать', 'обедать'],
            PlaceCategory.PARK: ['парк', 'прогулка', 'прогуляться', 'сквер', 'сад'],
            PlaceCategory.MUSEUM: ['музей', 'выставка', 'экспозиция', 'галерея'],
            PlaceCategory.THEATER: ['театр', 'спектакль', 'постановка'],
            PlaceCategory.CONCERT: ['концерт', 'музыка', 'живая музыка', 'группа'],
            PlaceCategory.CINEMA: ['кино', 'фильм', 'кинотеатр', 'сеанс'],
            PlaceCategory.ART: ['искусство', 'арт', 'творчество', 'картины'],
            PlaceCategory.EXCURSION: ['экскурсия', 'тур', 'гид', 'обзорная'],
            PlaceCategory.QUEST: ['квест', 'приключение', 'escape room'],
            PlaceCategory.BAR: ['бар', 'паб', 'коктейль', 'напитки', 'пиво'],
        }
        
        for category, keywords in category_map.items():
            if any(keyword in query_lower for keyword in keywords):
                return category
        
        return None
    
    def _place_to_dict(self, place: Place) -> Dict:
        """Конвертировать место в словарь"""
        return {
            "id": str(place.id),
            "name": place.name,
            "description": place.description,
            "category": place.category,
            "city": place.city,
            "address": place.address,
            "rating": place.rating,
            "rating_count": place.rating_count,
            "price_level": place.price_level,
        }
    
    async def update_place_rating(self, db: AsyncSession, place_id: UUID) -> bool:
        """Обновить рейтинг места после отзыва"""
        try:
            # Получить средний рейтинг и количество одобренных отзывов
            from sqlalchemy import func
            
            result = await db.execute(
                select(
                    func.avg(Review.rating).label("avg_rating"),
                    func.count(Review.id).label("count")
                ).where(
                    Review.place_id == place_id,
                    Review.moderation_status == "approved"
                )
            )
            stats = result.first()
            
            if stats and stats.avg_rating is not None:
                await db.execute(
                    select(Place)
                    .where(Place.id == place_id)
                    .update({
                        "rating": float(stats.avg_rating),
                        "rating_count": stats.count
                    })
                )
                return True
            return False
        except Exception as e:
            logger.error(f"Error updating place rating: {e}")
            return False