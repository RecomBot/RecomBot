# parser/models.py
"""
Модели для работы с БД парсера.
Используем общие модели из shared/models.
"""
import sys
import os
from pathlib import Path

# Добавляем shared в путь для импорта
shared_path = Path(__file__).parent.parent / "shared"
if str(shared_path) not in sys.path:
    sys.path.insert(0, str(shared_path))

from shared.models import Place, SourceType, PlaceCategory
from shared.models.base import Base

# Реэкспортируем для удобства
__all__ = ['Place', 'SourceType', 'PlaceCategory', 'Base']