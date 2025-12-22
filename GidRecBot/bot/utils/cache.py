# bot/utils/cache.py
from typing import Any, Optional
import time

class TTLCache:
    """Простой in-memory кэш с TTL (временем жизни)"""
    def __init__(self, ttl: int = 300):  # 5 минут по умолчанию
        self._cache: dict = {}
        self._ttl = ttl

    def set(self, key: str, value: Any) -> None:
        self._cache[key] = (value, time.time())

    def get(self, key: str) -> Optional[Any]:
        if key not in self._cache:
            return None
        value, timestamp = self._cache[key]
        if time.time() - timestamp > self._ttl:
            del self._cache[key]
            return None
        return value

    def delete(self, key: str) -> None:
        self._cache.pop(key, None)

# Глобальные кэши (singleton)
user_cache = TTLCache(ttl=600)  # tg_id → user_id