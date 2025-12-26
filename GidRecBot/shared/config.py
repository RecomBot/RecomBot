# GidRecBot/shared/config.py
from pydantic import Field
from pydantic_settings import BaseSettings
import os

class Settings(BaseSettings):
    # Telegram Bot
    BOT_TOKEN: str = Field(..., env="BOT_TOKEN")
    
    # Backend API
    API_BASE_URL: str = Field("http://backend:8000", env="API_BASE_URL")
    
    # Backend credentials (для модераторов/админов)
    MODERATOR_TG_ID: int = Field(987654321, env="MODERATOR_TG_ID")
    ADMIN_TG_ID: int = Field(999999999, env="ADMIN_TG_ID")

    class Config:
        # Ищем .env в разных местах
        env_file = os.path.join(os.path.dirname(__file__), '..', '.env')
        env_file_encoding = "utf-8"

config = Settings()