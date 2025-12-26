# backend/src/schemas/recommendation.py
"""
Pydantic схемы для рекомендаций
"""

from typing import Optional, List
from pydantic import BaseModel


class RecommendationRequest(BaseModel):
    """Схема для запроса рекомендаций"""
    categories: Optional[List[str]] = None
    city: Optional[str] = None
    budget: Optional[str] = None


class RecommendationResponse(BaseModel):
    """Схема для ответа с рекомендациями"""
    recommendations: list
    source: str
    success: bool = True