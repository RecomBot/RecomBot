# backend/src/utils/__init__.py
"""
Вспомогательные утилиты
"""

from .rating_updater import update_place_rating, update_all_place_ratings

__all__ = ['update_place_rating', 'update_all_place_ratings']