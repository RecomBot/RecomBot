# GidRecBot/bot/utils/http_client.py
import aiohttp
import logging
from typing import Optional, Dict, Any
from uuid import UUID
from ..config import config
import json

logger = logging.getLogger(__name__)

class HTTPClient:
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.base_url = config.API_BASE_URL
        logger.info(f"HTTP клиент инициализирован. Base URL: {self.base_url}")

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(
                base_url=self.base_url,
                timeout=timeout,
                headers={"Content-Type": "application/json"}
            )
        return self.session

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    async def _make_request(self, method: str, endpoint: str, **kwargs) -> Optional[Dict[str, Any]]:
        """Универсальный метод для запросов"""
        session = await self._get_session()
        
        try:
            # Логируем запрос
            logger.debug(f"{method} {endpoint} with kwargs: {kwargs.get('json', {})}")
            
            async with session.request(method, endpoint, **kwargs) as response:
                response_text = await response.text()
                # Логируем сырой ответ
                logger.debug(f"Raw response ({response.status}): {response_text[:200]}")

                if response.status in [200, 201]:
                    # Успешный ответ
                    try:
                        data = await response.json()
                        logger.debug(f"Parsed response from {endpoint}: {data}")
                        return data
                    except json.JSONDecodeError:
                        logger.error(f"Failed to parse JSON from {endpoint}: {e}")
                        return {
                            "error": True,
                            "status_code": response.status,
                            "detail": f"Invalid JSON response: {response_text[:100]}",
                            "message": "Сервер вернул некорректный ответ"
                        }
                else:
                    # Ошибка - логируем подробно
                    logger.warning(f"HTTP {response.status} from {endpoint}: {response_text}")
                    
                    # Пробуем извлечь детали ошибки из JSON
                    try:
                        error_data = json.loads(response_text)
                        error_detail = error_data.get("detail", response_text)
                        
                        # Логируем детали ошибки
                        logger.info(f"Error details: {error_detail}")
                        
                        return {
                            "error": True,
                            "status_code": response.status,
                            "detail": error_detail,
                            "message": error_detail,  # Используем то же сообщение
                            "raw": error_data
                        }
                    except json.JSONDecodeError:
                        # Не JSON ответ
                        logger.warning(f"Non-JSON error response: {response_text}")
                        return {
                            "error": True,
                            "status_code": response.status,
                            "detail": response_text,
                            "message": f"Ошибка {response.status}: {response_text[:100]}",
                            "raw": response_text
                        }
            
        except aiohttp.ClientError as e:
            logger.error(f"Connection error to {endpoint}: {e}")
            return {
                "error": True,
                "detail": f"Connection error: {e}",
                "message": "Не удалось подключиться к серверу"
            }
        except Exception as e:
            logger.error(f"Unexpected error for {endpoint}: {e}")
            return {
                "error": True,
                "detail": str(e),
                "message": "У вас уже оставлен отзыв на это место"
            }

    async def intelligent_search(
        self,
        query: str,
        telegram_id: Optional[int] = None,
        limit: int = 10
    ) -> Optional[Dict[str, Any]]:
        """Интеллектуальный поиск с использованием LLM"""
        data = {
            "query": query,
            "limit": limit
        }
        
        if telegram_id:
            data["telegram_id"] = telegram_id
        
        return await self._make_request(
            "POST", 
            "/api/v1/recommendations/intelligent-search", 
            json=data
        )
    
    # --- Аутентификация и пользователи ---
    async def switch_role(self, role: str) -> Dict[str, Any]:
        """Переключение роли пользователя"""
        endpoint = f"/api/v1/auth/switch-role/{role}"
        response = await self._make_request("POST", endpoint)
        return response or {"success": False}

    async def get_current_user(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """Получение текущего пользователя"""
        # return await self._make_request("GET", "/api/v1/auth/current")
        return await self.get_telegram_user(telegram_id)

    async def get_user_permissions(self) -> Optional[Dict[str, Any]]:
        """Получение прав пользователя"""
        return await self._make_request("GET", "/api/v1/auth/permissions")

    # Метод для совместимости со старым кодом
    async def get_user_by_tg_id(self, tg_id: int) -> Optional[Dict[str, Any]]:
        """Получение пользователя по telegram_id (эмуляция)"""
        # Так как бэкенд работает с тестовыми пользователями,
        # возвращаем фиктивного пользователя
        return {
            "id": "11111111-1111-1111-1111-111111111111",
            "telegram_id": tg_id,
            "username": f"user_{tg_id}",
            "role": "user"
        }

    # --- Места ---
    async def get_places(
        self, 
        category: Optional[str] = None,
        city: Optional[str] = None,
        limit: int = 10
    ) -> Optional[Dict[str, Any]]:
        """Получение списка мест"""
        params = {"limit": limit}
        if category:
            params["category"] = category
        if city:
            params["city"] = city
            
        return await self._make_request("GET", "/api/v1/places/", params=params)

    async def get_place(self, place_id: str) -> Optional[Dict[str, Any]]:
        """Получение конкретного места"""
        return await self._make_request("GET", f"/api/v1/places/{place_id}")

    # --- Отзывы ---
    async def create_review(
        self, 
        place_id: str,
        rating: int,
        text: str,
        telegram_id: int
    ) -> Optional[Dict[str, Any]]:
        """Создание отзыва"""
        data = {
            "place_id": place_id,
            "rating": rating,
            "text": text
        }
        params = {"telegram_id": telegram_id}
        logger.info(f"Отправка отзыва на место {place_id}, оценка: {rating}, текст: {text[:50]}...")

        response = await self._make_request("POST", "/api/v1/reviews/", json=data, params=params)
    
        if response:
            if "error" in response:
                logger.warning(f"Ошибка от API: {response}")
            else:
                logger.info(f"Успешный ответ от API: {response.get('moderation_status', 'unknown')}")
        else:
            logger.error("API вернул None при создании отзыва")
        
        return response

    async def get_place_reviews(self, place_id: str, limit: int = 10) -> Optional[Dict[str, Any]]:
        """Получение отзывов места"""
        params = {"place_id": place_id, "limit": limit, "only_approved": True}
        return await self._make_request("GET", "/api/v1/reviews/", params=params)

    async def get_user_reviews(
        self, 
        telegram_id: int,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Optional[Dict[str, Any]]:
        """Получение отзывов пользователя"""
        params = {
            "limit": limit,
            "offset": offset
        }
        if status:
            params["status"] = status
        
        return await self._make_request(
            "GET", 
            f"/api/v1/reviews/user/{telegram_id}/reviews",
            params=params
        )

    async def delete_review(
        self,
        review_id: str,
        telegram_id: int
    ) -> Optional[Dict[str, Any]]:
        """Удаление отзыва"""
        params = {"telegram_id": telegram_id}
        return await self._make_request(
            "DELETE",
            f"/api/v1/reviews/{review_id}",
            params=params
        )
    # --- Рекомендации ---
    async def recommend(self, user_id: str, query: str) -> Optional[Dict[str, Any]]:
        """Рекомендации через чат-интерфейс"""
        data = {
            "query": query,
            "telegram_id": int(user_id) if user_id.isdigit() else None,
            "categories": [],
            "city": "",
            "budget": ""
        }
        data = {k: v for k, v in data.items() if v is not None}
        return await self._make_request("POST", "/api/v1/recommendations/chat", json=data)

    async def get_personal_recommendations(self) -> Optional[Dict[str, Any]]:
        """Персонализированные рекомендации"""
        return await self._make_request("GET", "/api/v1/recommendations/personal")

    # --- Модерация ---
    async def get_pending_reviews(self, limit: int = 10) -> Optional[Dict[str, Any]]:
        """Отзывы на модерацию"""
        params = {"limit": limit}
        return await self._make_request("GET", "/api/v1/moderation/pending-reviews", params=params)

    async def approve_review(self, review_id: str) -> Optional[Dict[str, Any]]:
        """Одобрение отзыва"""
        return await self._make_request("POST", f"/api/v1/moderation/reviews/{review_id}/approve")

    async def reject_review(self, review_id: str, notes: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Отклонение отзыва"""
        data = {}
        if notes:
            data["notes"] = notes
        return await self._make_request("POST", f"/api/v1/moderation/reviews/{review_id}/reject", json=data)
    
    async def create_telegram_user(
        self,
        telegram_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        role: str = "user"
    ) -> Optional[Dict[str, Any]]:
        """Создание/обновление пользователя из Telegram"""
        data = {
            "telegram_id": telegram_id,
            "username": username,
            "first_name": first_name,
            "last_name": last_name,
            "role": role
        }
        return await self._make_request(
            "POST", 
            "/api/v1/auth/create-telegram-user", 
            json=data
        )

    async def get_telegram_user(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """Получение пользователя по telegram_id"""
        return await self._make_request(
            "GET", 
            f"/api/v1/auth/telegram-user/{telegram_id}"
        )

# Глобальный экземпляр
http_client = HTTPClient()