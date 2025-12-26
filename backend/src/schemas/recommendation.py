# backend/src/schemas/recommendation.py
from typing import List, Optional
from pydantic import Field
from .base import BaseSchema
from .place import PlaceResponse

class RecommendationRequest(BaseSchema):
    """Запрос рекомендаций"""
    query: str = Field(..., min_length=2, max_length=200)
    limit: int = Field(default=5, ge=1, le=20)

class RecommendationResponse(BaseSchema):
    """Ответ с рекомендациями"""
    text: str  # Текст от LLM
    places: List[PlaceResponse]
    user_id: str
    city: str
    query: str