# backend/src/schemas/base.py
from pydantic import BaseModel, ConfigDict
from datetime import datetime
from uuid import UUID

class BaseSchema(BaseModel):
    """Базовая схема с настройками"""
    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)

class TimestampSchema(BaseSchema):
    """Схема с временными метками"""
    created_at: datetime
    updated_at: datetime | None = None