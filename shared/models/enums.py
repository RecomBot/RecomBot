# shared/models/enums.py
from enum import Enum

class UserRole(str, Enum):
    """Роли пользователей"""
    USER = "user"
    MODERATOR = "moderator"
    ADMIN = "admin"

class ModerationStatus(str, Enum):
    """Статусы модерации отзывов"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    FLAGGED_BY_LLM = "flagged_by_llm"

class PlaceCategory(str, Enum):
    """Категории мест"""
    CAFE = "cafe"
    RESTAURANT = "restaurant"
    PARK = "park"
    MUSEUM = "museum"
    THEATER = "theater"
    CONCERT = "concert"
    CINEMA = "cinema"
    ART = "art"
    EXCURSION = "excursion"
    QUEST = "quest"
    BAR = "bar"
    SHOPPING = "shopping"
    SPORT = "sport"
    OTHER = "other"

class SourceType(str, Enum):
    """Источники данных"""
    YANDEX_AFISHA = "yandex_afisha"
    GOOGLE_MAPS = "google_maps"
    USER = "user"
    TELEGRAM = "telegram"
    API = "api"