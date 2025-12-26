# backend/src/models/__init__.py
# Реэкспортируем модели из shared
from shared.models import Base, User, Place, Review
from shared.models.enums import UserRole, ModerationStatus, PlaceCategory, SourceType

__all__ = [
    'Base',
    'User',
    'Place',
    'Review',
    'UserRole',
    'ModerationStatus',
    'PlaceCategory',
    'SourceType'
]