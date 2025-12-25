# bot/utils/http_client.py
import aiohttp
import logging
from .cache import user_cache
from shared.config import config

logger = logging.getLogger(__name__)


class HTTPClient:
    def __init__(self):
        self.session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(base_url=config.API_BASE_URL)
        return self.session

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    # 🔑 РЕГИСТРАЦИЯ ПОЛЬЗОВАТЕЛЯ
    async def register_user(self, tg_id: int, location: str) -> dict:
        """POST /api/v1/auth/ → создаёт или возвращает пользователя по tg_id"""
        session = await self._get_session()
        payload = {"tg_id": tg_id, "location": location}
        try:
            async with session.post("/api/v1/auth/", json=payload) as resp:
                if resp.status == 201:
                    user = await resp.json()
                    user_cache.set(f"user_{tg_id}", user)
                    return user
                else:
                    text = await resp.text()
                    raise Exception(f"HTTP {resp.status}: {text}")
        except Exception as e:
            logger.error(f"❌ Ошибка регистрации: {e}")
            raise

    # 🔑 ПОЛУЧЕНИЕ ПРОФИЛЯ ПО TG_ID
    async def get_user_by_tg_id(self, tg_id: int) -> dict:
        """GET /api/v1/auth/by_tg/{tg_id} → профиль пользователя"""
        cached = user_cache.get(f"user_{tg_id}")
        if cached is not None:
            return cached

        session = await self._get_session()
        try:
            async with session.get(f"/api/v1/auth/by_tg/{tg_id}") as resp:
                if resp.status == 200:
                    user = await resp.json()
                    user_cache.set(f"user_{tg_id}", user)
                    return user
                else:
                    raise Exception(f"User not found: {resp.status}")
        except Exception as e:
            logger.error(f"❌ Ошибка получения пользователя: {e}")
            raise

    # 📝 ОТПРАВКА ОТЗЫВА
    async def create_review(self, tg_id: int, place_id: str, rating: int, text: str) -> dict:
        """POST /api/v1/reviews/ → отправка отзыва с tg_id в теле"""
        session = await self._get_session()
        payload = {
            "tg_id": tg_id,
            "place_id": place_id,
            "rating": rating,
            "text": text
        }
        try:
            async with session.post("/api/v1/reviews/", json=payload) as resp:
                if resp.status == 201:
                    return await resp.json()
                else:
                    text = await resp.text()
                    raise Exception(f"HTTP {resp.status}: {text}")
        except Exception as e:
            logger.error(f"❌ Ошибка отправки отзыва: {e}")
            raise

    # 🤖 РЕКОМЕНДАЦИИ ЧЕРЕЗ LLM
    async def recommend(self, tg_id: int, query: str) -> dict:
        """POST /api/v1/recommendations/chat → персонализированные рекомендации"""
        session = await self._get_session()
        payload = {
            "tg_id": tg_id,
            "query": query
        }
        try:
            async with session.post("/api/v1/recommendations/chat", json=payload) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    text = await resp.text()
                    raise Exception(f"HTTP {resp.status}: {text}")
        except Exception as e:
            logger.error(f"❌ Ошибка LLM-рекомендации: {e}")
            raise

    # 🔍 ПОИСК МЕСТ (для пагинации и natural language)
    async def search_places(self, tg_id: int, query: str) -> dict:
        """POST /api/v1/recommendations/search → поиск мест по запросу"""
        session = await self._get_session()
        payload = {
            "tg_id": tg_id,
            "query": query
        }
        try:
            async with session.post("/api/v1/recommendations/search", json=payload) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    text = await resp.text()
                    raise Exception(f"HTTP {resp.status}: {text}")
        except Exception as e:
            logger.error(f"❌ Ошибка поиска мест: {e}")
            raise

    # 👮 МОДЕРАЦИЯ: ОДОБРЕНИЕ ОТЗЫВА
    async def approve_review(self, tg_id: int, review_id: str) -> dict:
        """POST /api/v1/moderation/reviews/{review_id}/approve"""
        session = await self._get_session()
        payload = {"tg_id": tg_id}
        try:
            url = f"/api/v1/moderation/reviews/{review_id}/approve"
            async with session.post(url, json=payload) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    text = await resp.text()
                    raise Exception(f"HTTP {resp.status}: {text}")
        except Exception as e:
            logger.error(f"❌ Ошибка одобрения отзыва: {e}")
            raise

    # 👮 МОДЕРАЦИЯ: ОТКЛОНЕНИЕ ОТЗЫВА
    async def reject_review(self, tg_id: int, review_id: str, notes: str = None) -> dict:
        """POST /api/v1/moderation/reviews/{review_id}/reject"""
        session = await self._get_session()
        payload = {"tg_id": tg_id}
        if notes:
            payload["notes"] = notes

        try:
            url = f"/api/v1/moderation/reviews/{review_id}/reject"
            async with session.post(url, json=payload) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    text = await resp.text()
                    raise Exception(f"HTTP {resp.status}: {text}")
        except Exception as e:
            logger.error(f"❌ Ошибка отклонения отзыва: {e}")
            raise

    # 👮 МОДЕРАЦИЯ: ПОЛУЧЕНИЕ ОЧЕРЕДИ
    async def get_moderation_queue(self, tg_id: int) -> dict:
        """GET /api/v1/moderation/queue?tg_id=..."""
        session = await self._get_session()
        try:
            async with session.get(f"/api/v1/moderation/queue?tg_id={tg_id}") as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    raise Exception(f"HTTP {resp.status}")
        except Exception as e:
            logger.error(f"❌ Ошибка получения очереди модерации: {e}")
            raise


# Единый экземпляр
http_client = HTTPClient()