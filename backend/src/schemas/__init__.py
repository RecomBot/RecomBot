# backend/src/schemas/__init__.py
"""
Pydantic схемы для API
"""

from .user import UserCreate, UserResponse, UserUpdate
from .place import PlaceCreate, PlaceResponse, PlaceUpdate, PlaceStats
from .review import ReviewCreate, ReviewResponse, ReviewModeration
from .recommendation import RecommendationRequest, RecommendationResponse

__all__ = [
    'UserCreate', 'UserResponse', 'UserUpdate',
    'PlaceCreate', 'PlaceResponse', 'PlaceUpdate', 'PlaceStats',
    'ReviewCreate', 'ReviewResponse', 'ReviewModeration',
    'RecommendationRequest', 'RecommendationResponse',
]