# bot/utils/http_client.py
import aiohttp
import logging
from .cache import user_cache
from ..config import API_BASE_URL

logger = logging.getLogger(__name__)

class HTTPClient:
    def __init__(self):
        self.session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(base_url=API_BASE_URL)
        return self.session

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    async def register_user(self, tg_id: int, location: str) -> dict:
        session = await self._get_session()
        user_data = {"tg_id": tg_id, "location": location}
        try:
            async with session.post("/api/users/", json=user_data) as resp:
                if resp.status == 201:
                    user = await resp.json()
                    user_cache.set(f"user_{tg_id}", user)  # ✅ кэшируем ВЕСЬ dict
                    return user
                else:
                    text = await resp.text()
                    raise Exception(f"HTTP {resp.status}: {text}")
        except Exception as e:
            logger.error(f"❌ Ошибка регистрации: {e}")
            raise

    async def get_user_by_tg_id(self, tg_id: int) -> dict:
        # ✅ Получаем ВЕСЬ объект из кэша
        cached = user_cache.get(f"user_{tg_id}")
        if cached is not None:
            return cached

        session = await self._get_session()
        try:
            async with session.get(f"/api/users/by_tg/{tg_id}") as resp:
                if resp.status == 200:
                    user = await resp.json()
                    user_cache.set(f"user_{tg_id}", user)  # ✅ кэшируем ВЕСЬ dict
                    return user
                else:
                    raise Exception(f"User not found: {resp.status}")
        except Exception as e:
            logger.error(f"❌ Ошибка получения пользователя: {e}")
            raise

    # ✅ МЕТОД ДЛЯ LLM — ОБЯЗАТЕЛЕН
    async def recommend(self, user_id: int, query: str = None) -> dict:
        """Mock-реализация до подключения бэкенда"""
        logger.info(f"🔍 Mock-запрос рекомендации: user_id={user_id}, query='{query}'")
        return {
            "text": "Вот что подойдёт именно вам:",
            "places": [
                {
                    "id": 1,
                    "name": "Кофейня у Патриарших",
                    "description": "Уютное место с домашней выпечкой и ароматным кофе.",
                    "category": "cafe",
                    "address": "Тверская, 12",
                    "rating_avg": 4.7,
                    "rating_count": 23
                },
                {
                    "id": 3,
                    "name": "Парк Горького",
                    "description": "Зелёная зона с прокатом велосипедов и летней верандой.",
                    "category": "park",
                    "address": "Крымский Вал, 9",
                    "rating_avg": 4.8,
                    "rating_count": 156
                }
            ]
        }

http_client = HTTPClient()