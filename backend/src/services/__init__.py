# backend/src/services/__init__.py
"""
Сервисы с бизнес-логикой
"""

from .llm_service import LLMService, OllamaCloudClient

__all__ = ['LLMService', 'OllamaCloudClient']