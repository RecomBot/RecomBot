# backend/src/dependencies.py
from fastapi import Depends 
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from .database import get_db
from .services.cache import CacheService
from .services.llm import LLMService
from .services.recommendation import RecommendationService
from shared.config import config

# Инициализация сервисов
cache_service = CacheService(redis_url=config.REDIS_URL)
llm_service = LLMService(
    base_url=config.OLLAMA_BASE_URL,
    api_key=config.OLLAMA_API_KEY,
    model=config.OLLAMA_MODEL
)

async def get_cache() -> CacheService:
    return cache_service

async def get_llm() -> LLMService:
    return llm_service

async def get_recommendation_service(cache: CacheService = Depends(get_cache)) -> RecommendationService:
    return RecommendationService(cache)

# Короткие алиасы для удобства
get_db_session = get_db