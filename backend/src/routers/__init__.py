# backend/src/routers/__init__.py
"""
FastAPI роутеры
"""

from .auth import router as auth_router
from .places import router as places_router
from .reviews import router as reviews_router
from .moderation import router as moderation_router
from .recommendations import router as recommendations_router

__all__ = [
    'auth_router',
    'places_router',
    'reviews_router',
    'moderation_router',
    'recommendations_router',
]