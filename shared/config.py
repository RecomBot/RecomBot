# shared/config.py
import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field

# Определяем корень проекта (RecomBot/)
PROJECT_ROOT = Path(__file__).parent.parent


class Config(BaseSettings):
    #  Telegram Bot
    BOT_TOKEN: str = Field(..., validation_alias="BOT_TOKEN")

    #  Database
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/travel_db",
        validation_alias="DATABASE_URL"
    )

    #  JWT (только для бэкенда)
    JWT_SECRET_KEY: str = Field(
        default="your_super_secret_jwt_key_change_this_in_production_123",
        validation_alias="JWT_SECRET_KEY"
    )
    JWT_ALGORITHM: str = Field(
        default="HS256",
        validation_alias="JWT_ALGORITHM"
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=30,
        validation_alias="ACCESS_TOKEN_EXPIRE_MINUTES"
    )

    # Ollama Cloud 
    # ВАЖНО: переменная окружения называется OLLAMA_HOST, но в коде — OLLAMA_BASE_URL
    OLLAMA_BASE_URL: str = Field(
        default="https://ollama.com",
        validation_alias="OLLAMA_HOST"  
    )
    OLLAMA_MODEL: str = Field(
        default="qwen3-coder:480b-cloud",
        validation_alias="OLLAMA_MODEL"
    )
    OLLAMA_API_KEY: Optional[str] = Field(
        default=None,
        validation_alias="OLLAMA_API_KEY"
    )

    # Redis
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        validation_alias="REDIS_URL"
    )

    # URLs
    API_BASE_URL: str = Field(
        default="http://localhost:8001/api/v1",  # ← docker-compose:8001 → backend:8000
        validation_alias="API_BASE_URL"
    )

    class Config:
        env_file = PROJECT_ROOT / ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

    # Очистка URL от пробелов
    @property
    def clean_ollama_base_url(self) -> str:
        return self.OLLAMA_BASE_URL.strip()


# Единый экземпляр для всего проекта
config = Config()