import os
from typing import Optional
from dotenv import load_dotenv

# Загружаем .env файл
load_dotenv()

class Settings:
    """Настройки приложения"""
    
    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        "postgresql+asyncpg://postgres:postgres@postgres:5432/travel_db"
    )
    
    # JWT
    JWT_SECRET_KEY: str = os.getenv(
        "JWT_SECRET_KEY", 
        "your_super_secret_jwt_key_change_this_in_production_123"
    )
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
    
    # Ollama Cloud
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_HOST", "https://ollama.com")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen3-coder:480b-cloud")
    OLLAMA_API_KEY: Optional[str] = os.getenv("OLLAMA_API_KEY")
    
    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://redis:6379/0")
    
    @classmethod
    def print_config(cls):
        """Печать конфигурации (для отладки)"""
        print("=" * 50)
        print("CONFIGURATION:")
        print(f"DATABASE_URL: {cls.DATABASE_URL[:50]}...")
        print(f"OLLAMA_BASE_URL: {cls.OLLAMA_BASE_URL}")
        print(f"OLLAMA_MODEL: {cls.OLLAMA_MODEL}")
        print("=" * 50)

settings = Settings()