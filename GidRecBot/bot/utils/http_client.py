# GidRecBot/bot/utils/http_client.py
import httpx
import logging
from typing import Optional, Dict, Any, List
from uuid import UUID
from shared.config import config

logger = logging.getLogger(__name__)


class HTTPClient:
    """HTTP клиент для работы с API бэкенда"""
    
    def __init__(self, base_url: str = None):
        self.base_url = (base_url or config.API_BASE_URL).rstrip('/')
        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={"Content-Type": "application/json"}
        )
        logger.info(f"HTTPClient initialized with base URL: {self.base_url}")
    
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """Общий метод для выполнения запросов"""
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = await self.client.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json() if response.content else {}
        except httpx.TimeoutException:
            logger.error(f"Request timeout: {method} {url}")
            return None
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code}: {e.response.text}")
            # Пробуем получить детали ошибки
            try:
                error_detail = e.response.json().get("detail", str(e))
            except:
                error_detail = str(e)
            raise Exception(f"API error: {error_detail}")
        except Exception as e:
            logger.error(f"Request error: {e}")
            raise
    
    # ========== АУТЕНТИФИКАЦИЯ ==========
    
    async def register_user(self, tg_id: int, location: str, username: Optional[str] = None) -> Dict[str, Any]:
        """
        Регистрация/получение пользователя
        POST /api/v1/auth/
        """
        data = {
            "telegram_id": tg_id,
            "location": location,
            "username": username
        }
        
        response = await self._make_request(
            "POST",
            "/api/v1/auth/",
            json=data
        )
        
        if response:
            logger.info(f"User registered/retrieved: {tg_id} in {location}")
            return response
        raise Exception("Failed to register user")
    
    async def get_user_by_tg_id(self, tg_id: int) -> Dict[str, Any]:
        """
        Получить пользователя по Telegram ID
        GET /api/v1/auth/by_tg/{telegram_id}
        """
        response = await self._make_request(
            "GET",
            f"/api/v1/auth/by_tg/{tg_id}"
        )
        
        if response:
            return response
        raise Exception(f"User with tg_id {tg_id} not found")
    
    # ========== МЕСТА ==========
    
    async def get_places(
        self,
        category: Optional[str] = None,
        city: Optional[str] = None,
        min_rating: Optional[float] = None,
        search: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Получить список мест с фильтрацией
        GET /api/v1/places/
        """
        params = {
            "limit": limit,
            "category": category,
            "city": city,
            "min_rating": min_rating,
            "search": search
        }
        # Убираем None значения
        params = {k: v for k, v in params.items() if v is not None}
        
        response = await self._make_request(
            "GET",
            "/api/v1/places/",
            params=params
        )
        
        return response or []
    
    async def get_place(self, place_id: str) -> Optional[Dict[str, Any]]:
        """
        Получить место по ID
        GET /api/v1/places/{place_id}
        """
        try:
            response = await self._make_request(
                "GET",
                f"/api/v1/places/{place_id}"
            )
            return response
        except Exception as e:
            logger.error(f"Error getting place {place_id}: {e}")
            return None
    
    # ========== ОТЗЫВЫ ==========
    
    async def create_review(
        self,
        tg_id: int,
        place_id: str,
        rating: int,
        text: str
    ) -> Dict[str, Any]:
        """
        Создать отзыв
        POST /api/v1/reviews/
        """
        data = {
            "place_id": place_id,
            "rating": rating,
            "text": text,
            "telegram_id": tg_id
        }
        
        response = await self._make_request(
            "POST",
            "/api/v1/reviews/",
            json=data
        )
        
        if response:
            logger.info(f"Review created for place {place_id} by user {tg_id}")
            return response
        raise Exception("Failed to create review")
    
    async def get_reviews_by_place(self, place_id: str, show_pending: bool = False) -> List[Dict[str, Any]]:
        """
        Получить отзывы по месту
        GET /api/v1/reviews/place/{place_id}
        """
        params = {"show_pending": show_pending}
        
        try:
            response = await self._make_request(
                "GET",
                f"/api/v1/reviews/place/{place_id}",
                params=params
            )
            return response or []
        except Exception as e:
            logger.error(f"Error getting reviews for place {place_id}: {e}")
            return []
    
    # ========== РЕКОМЕНДАЦИИ ==========
    
    async def recommend(
        self,
        tg_id: int,
        query: str,
        limit: int = 5
    ) -> Dict[str, Any]:
        """
        Получить рекомендации через LLM-чат
        POST /api/v1/recommendations/chat
        """
        data = {
            "query": query,
            "limit": limit,
            "telegram_id": tg_id
        }
        
        response = await self._make_request(
            "POST",
            "/api/v1/recommendations/chat",
            json=data
        )
        
        if response:
            logger.info(f"Recommendations generated for user {tg_id}, query: {query}")
            return response
        raise Exception("Failed to get recommendations")
    
    async def search_places(
        self,
        tg_id: int,
        query: str,
        limit: int = 5
    ) -> Dict[str, Any]:
        """
        Поиск мест по запросу
        POST /api/v1/recommendations/search
        """
        data = {
            "query": query,
            "limit": limit,
            "telegram_id": tg_id
        }
        
        response = await self._make_request(
            "POST",
            "/api/v1/recommendations/search",
            json=data
        )
        
        if response:
            logger.info(f"Search completed for user {tg_id}, query: {query}")
            return response
        raise Exception("Failed to search places")
    
    # ========== МОДЕРАЦИЯ ==========
    
    async def get_moderation_queue(
        self,
        tg_id: int,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Получить очередь на модерацию (для модераторов)
        GET /api/v1/moderation/queue
        """
        try:
            response = await self._make_request(
                "POST",
                "/api/v1/moderation/queue",
                json={"telegram_id": tg_id, "limit": limit}
            )
            return response or []
        except Exception as e:
            logger.error(f"Error getting moderation queue: {e}")
            return []
    
    async def approve_review(
        self,
        tg_id: int,
        review_id: str,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Одобрить отзыв (для модераторов)
        POST /api/v1/moderation/reviews/{review_id}/approve
        """
        data = {"telegram_id": tg_id}
        if notes:
            data["notes"] = notes
        
        response = await self._make_request(
            "POST",
            f"/api/v1/moderation/reviews/{review_id}/approve",
            json=data
        )
        
        if response:
            logger.info(f"Review {review_id} approved by moderator {tg_id}")
            return response
        raise Exception("Failed to approve review")
    
    async def reject_review(
        self,
        tg_id: int,
        review_id: str,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Отклонить отзыв (для модераторов)
        POST /api/v1/moderation/reviews/{review_id}/reject
        """
        data = {"telegram_id": tg_id}
        if notes:
            data["notes"] = notes
        
        response = await self._make_request(
            "POST",
            f"/api/v1/moderation/reviews/{review_id}/reject",
            json=data
        )
        
        if response:
            logger.info(f"Review {review_id} rejected by moderator {tg_id}")
            return response
        raise Exception("Failed to reject review")
    
    # ========== СИСТЕМНЫЕ ==========
    
    async def check_api_health(self) -> bool:
        """Проверка доступности API с правильным эндпоинтом"""
        try:
            response = await self._make_request("GET", "/health")
            return response.get("status") == "healthy" if response else False
        except Exception as e:
            logger.error(f"API health check failed: {e}")
            return False
    
    async def llm_status(self) -> Dict[str, Any]:
        """Проверка статуса LLM"""
        try:
            response = await self._make_request("GET", "/llm-status")
            return response or {}
        except Exception as e:
            logger.error(f"Error checking LLM status: {e}")
            return {"status": "disconnected", "error": str(e)}
    
    # ========== УТИЛИТЫ ==========
    
    async def close(self):
        """Закрыть HTTP клиент"""
        await self.client.aclose()
        logger.info("HTTPClient closed")
    
    def __del__(self):
        """Деструктор для автоматического закрытия"""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(self.close())
        except:
            pass


# Глобальный экземпляр HTTP клиента
http_client = HTTPClient()