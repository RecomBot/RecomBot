# backend/src/services/llm.py
import json
import httpx
from typing import Optional, Dict, Any
from typing import List, Dict, Optional, Any
import logging
from shared.config import config

logger = logging.getLogger(__name__)

class LLMService:
    """Сервис для работы с LLM (Ollama Cloud)"""
    
    def __init__(self, base_url: str, api_key: Optional[str], model: str):
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.headers = {'Authorization': f'Bearer {api_key}'} if api_key else {}
        self.timeout = 30.0
    
    async def _make_request(self, endpoint: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Общий метод для запросов к API"""
        url = f"{self.base_url}{endpoint}"
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    url,
                    json=data,
                    headers=self.headers
                )
                response.raise_for_status()
                return response.json()
            except httpx.TimeoutException:
                logger.error(f"LLM request timeout to {url}")
                return None
            except httpx.HTTPStatusError as e:
                logger.error(f"LLM HTTP error: {e.response.status_code} - {e.response.text}")
                return None
            except Exception as e:
                logger.error(f"LLM request error: {e}")
                return None
    
    async def check_connection(self) -> bool:
        """Проверить подключение к LLM сервису"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}/api/tags",
                    headers=self.headers
                )
                return response.status_code == 200
        except Exception as e:
            logger.error(f"LLM connection check failed: {e}")
            return False
    
    async def check_review_content(self, text: str) -> Dict[str, Any]:
        """Проверить содержание отзыва"""
        prompt = f"""Ты — модератор контента. Проверь отзыв на:
1. Мат/оскорбления (даже завуалированные)
2. Спам/рекламу
3. Угрозы/агрессию
4. Личные данные (номера телефонов, адреса)

Отзыв: "{text}"

Верни ТОЛЬКО JSON:
{{"is_appropriate": true/false, "reason": "краткая причина", "confidence": 0.0-1.0, "flagged_words": []}}"""
        
        data = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.1}
        }
        
        result = await self._make_request("/api/chat", data)
        if result and "message" in result:
            try:
                content = result["message"]["content"]
                return json.loads(content.strip())
            except json.JSONDecodeError:
                pass
        
        # Фолбэк если LLM не ответил
        return {
            "is_appropriate": True,
            "reason": "LLM недоступен, пропущено автоматически",
            "confidence": 0.5,
            "flagged_words": []
        }
    
    async def summarize_review(self, text: str, rating: int) -> str:
        """Суммаризировать отзыв"""
        prompt = f"""Суммаризируй отзыв в 1-2 предложения (максимум 100 символов):
Рейтинг: {rating}/5
Текст: {text}

Суммаризация:"""
        
        data = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": 0.2}
        }
        
        result = await self._make_request("/api/chat", data)
        if result and "message" in result:
            summary = result["message"]["content"].strip()
            return summary[:100] if summary else f"Отзыв {rating}⭐"
        
        return f"Отзыв {rating}⭐"
    
    async def generate_recommendations(self, user_prefs: Dict, places: List[Dict]) -> str:
        """Сгенерировать текстовые рекомендации"""
        if not places:
            return "К сожалению, по вашему запросу ничего не найдено."
        
        places_text = "\n".join([
            f"- {p.get('name', 'Место')} ({p.get('category', 'без категории')}, рейтинг {p.get('rating', 0)}/5): {p.get('description', '')[:50]}..."
            for p in places[:5]
        ])
        
        prompt = f"""Ты — дружелюбный гид по городу {user_prefs.get('city', 'Москва')}.

Пользователь ищет: {user_prefs.get('query', 'интересные места')}

Вот подходящие места:
{places_text}

Сгенерируй краткие персональные рекомендации (2-3 предложения, максимум 150 слов). 
Будь дружелюбным и полезным. Предложи лучшие варианты."""

        data = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": 0.7}
        }
        
        result = await self._make_request("/api/chat", data)
        if result and "message" in result:
            return result["message"]["content"].strip()
        
        return "Вот несколько интересных мест, которые могут вам понравиться:"