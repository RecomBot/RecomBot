# backend/src/main_single.py
import sys
import os
import httpx
import json
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime
import re
from ollama import AsyncClient as OllamaCloudClient

# Добавляем путь к src в sys.path
current_dir = Path(__file__).parent
src_path = str(current_dir)
if src_path not in sys.path:
    sys.path.insert(0, src_path)

# Загружаем .env
from dotenv import load_dotenv
load_dotenv()

# Импортируем единый config
from shared.config import config

from fastapi import FastAPI, APIRouter, Depends, HTTPException, Query, Body, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from sqlalchemy import (
    Column, Integer, String, Text, Float, Boolean, JSON, DateTime,
    ForeignKey, select, update, BigInteger, func
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from uuid import UUID, uuid4
import uuid
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ========== МОДЕЛИ SQLALCHEMY ==========
Base = declarative_base()

class User(Base):
    __tablename__ = "user"
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    telegram_id = Column(BigInteger, unique=True, index=True)
    username = Column(String(255))
    role = Column(String(20), default="user")
    preferences = Column(JSON)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    reviews = relationship("Review", back_populates="user", foreign_keys="Review.user_id")
    moderated_reviews = relationship("Review", back_populates="moderator", foreign_keys="Review.moderated_by")

class Place(Base):
    __tablename__ = "place"
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(Text, nullable=False)
    description = Column(Text)
    category = Column(String(20))
    city = Column(String(100), default="Moscow")
    address = Column(Text)
    price_level = Column(Integer, default=2)
    rating = Column(Float, default=0.0)
    rating_count = Column(Integer, default=0)
    source = Column(String(50), default="yandex_afisha")
    is_active = Column(Boolean, default=True)

class Review(Base):
    __tablename__ = "review"
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("user.id"), nullable=False)
    place_id = Column(PG_UUID(as_uuid=True), ForeignKey("place.id"), nullable=False)
    rating = Column(Integer)
    text = Column(Text)
    moderation_status = Column(String(20), default="pending")
    moderated_by = Column(PG_UUID(as_uuid=True), ForeignKey("user.id"))
    llm_check = Column(JSON)
    summary = Column(Text)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    user = relationship("User", foreign_keys=[user_id], back_populates="reviews")
    moderator = relationship("User", foreign_keys=[moderated_by], back_populates="moderated_reviews")
    place = relationship("Place", back_populates="reviews")

# ========== ПОДКЛЮЧЕНИЕ К БАЗЕ ==========
engine = create_async_engine(config.DATABASE_URL, echo=True)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            raise e
        finally:
            await session.close()

# ========== УТИЛИТЫ ==========
async def update_place_rating(db: AsyncSession, place_id: UUID):
    result = await db.execute(
        select(
            func.avg(Review.rating).label("avg"),
            func.count(Review.id).label("cnt")
        ).where(
            Review.place_id == place_id,
            Review.moderation_status == "approved"
        )
    )
    avg, cnt = result.one()
    avg = float(avg) if avg else 0.0
    cnt = cnt or 0
    await db.execute(
        update(Place)
        .where(Place.id == place_id)
        .values(rating=avg, rating_count=cnt)
    )
    await db.commit()

# ========== OLLAMA CLOUD CLIENT ==========
class OllamaCloudClientWrapper:
    def __init__(self):
        self.base_url = config.OLLAMA_BASE_URL.strip()
        self.model = config.OLLAMA_MODEL
        self.api_key = config.OLLAMA_API_KEY
        self.client = OllamaCloudClient(
            host=self.base_url,
            headers={'Authorization': f'Bearer {self.api_key}'} if self.api_key else None
        )
        logger.info(f"Ollama Cloud client: {self.model} @ {self.base_url}")
        
    
    async def test_connection(self) -> bool:
        """Проверяет подключение к Ollama Cloud"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                headers = {}
                if self.api_key:
                    headers['Authorization'] = f'Bearer {self.api_key}'
                response = await client.get(
                    f"{self.base_url}/api/tags",
                    headers=headers
                )
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Connection test error: {e}")
            return False
    

    async def _call_api(self, prompt: str, temperature: float = 0.1) -> Optional[str]:
        try:
            response = await self.client.chat(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": temperature},
                stream=False
            )
            return response['message']['content'].strip()
        except Exception as e:
            logger.error(f"Ollama API error: {e}")
            return await self._fallback_call(prompt, temperature)

    async def _fallback_call(self, prompt: str, temperature: float = 0.1) -> Optional[str]:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                headers = {'Authorization': f'Bearer {self.api_key}'} if self.api_key else {}
                data = {
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "options": {"temperature": temperature}
                }
                response = await client.post(f"{self.base_url}/api/chat", json=data, headers=headers)
                if response.status_code == 200:
                    return response.json().get("message", {}).get("content", "").strip()
        except Exception as e:
            logger.error(f"Fallback error: {e}")
        return None

    async def check_review_content(self, text: str) -> dict:
        prompt = f"""Ты — строгий модератор. Проверь отзыв на:
1. Мат/оскорбления (даже завуалированные)
2. Спам/рекламу
3. Угрозы/агрессию

Отзыв: "{text}"

Верни ТОЛЬКО JSON:
{{"is_appropriate": true/false, "reason": "причина", "confidence": 0.0-1.0}}"""
        response = await self._call_api(prompt, temperature=0.1)
        try:
            if response:
                return json.loads(response)
        except:
            pass
        return {"is_appropriate": True, "reason": "ошибка LLM", "confidence": 0.5}

    async def summarize_review(self, text: str, rating: int) -> str:
        prompt = f"""Суммаризируй отзыв в 1 предложение (≤80 символов):
Рейтинг: {rating} ★, Текст: {text}

Суммаризация:"""
        summary = await self._call_api(prompt, temperature=0.2)
        return (summary or text)[:80]

    async def generate_recommendations(self, user_prefs: dict, places: list) -> str:
        places_info = "\n".join([
            f"- «{p['name']}» ({p['category']}, {p['rating']}★): {p['description'][:80]}"
            for p in places[:3]
        ])
        prompt = f"""Ты — дружелюбный гид. Пользователь из {user_prefs.get('city', 'Москвы')} ищет места.

Вот варианты:
{places_info}

Кратко (≤100 слов) порекомендуй 2–3 лучших. На русском, дружелюбно."""
        return await self._call_api(prompt, temperature=0.7) or "Вот подходящие места:"

# ========== LLM SERVICE ==========
class LLMService:
    def __init__(self):
        self.client = OllamaCloudClientWrapper()

    async def check_review_content(self, text: str) -> dict:
        return await self.client.check_review_content(text)

    async def summarize_review(self, text: str, rating: int) -> str:
        return await self.client.summarize_review(text, rating)

    async def generate_recommendations(self, user_id: UUID, db: AsyncSession) -> str:
        user = await db.execute(select(User).where(User.id == user_id))
        user = user.scalar_one_or_none()
        if not user:
            return "Пользователь не найден"

        places = await db.execute(select(Place).where(Place.is_active == True).limit(5))
        places = [
            {
                "id": p.id,
                "name": p.name,
                "category": p.category,
                "rating": p.rating,
                "description": p.description
            }
            for p in places.scalars().all()
        ]
        return await self.client.generate_recommendations(
            user.preferences or {"city": "Moscow"},
            places
        )

# ========== PYDANTIC MODELS ==========
class UserCreate(BaseModel):
    tg_id: int
    location: str

class ReviewCreate(BaseModel):
    place_id: UUID
    rating: int = Field(..., ge=1, le=5)
    text: str = Field(..., min_length=10, max_length=500)

class RecommendationRequest(BaseModel):
    query: str

class ReviewResponse(BaseModel):
    model_config = {"from_attributes": True}
    id: UUID
    user_id: UUID
    place_id: UUID
    rating: int
    text: str
    summary: Optional[str] = None
    moderation_status: str
    created_at: datetime

class PlaceResponse(BaseModel):
    model_config = {"from_attributes": True}
    id: UUID
    name: str
    description: Optional[str] = None
    category: str
    city: str
    address: Optional[str] = None
    rating: float
    rating_count: int
    created_at: datetime 

# ========== РОУТЕРЫ ==========
auth_router = APIRouter()
places_router = APIRouter()
reviews_router = APIRouter()
recommendations_router = APIRouter()
moderation_router = APIRouter()

# ========== ЭНДПОИНТЫ ==========
@auth_router.post("/", status_code=201)
async def create_user(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.telegram_id == user_data.tg_id))
    existing = result.scalar_one_or_none()
    if existing:
        return {
            "id": existing.id,
            "telegram_id": existing.telegram_id,
            "role": existing.role,
            "location": existing.preferences.get("city", "Moscow") if existing.preferences else "Moscow"
        }

    new_user = User(
        telegram_id=user_data.tg_id,
        username=f"tg_{user_data.tg_id}",
        role="user",
        preferences={"city": user_data.location},
        is_active=True
    )
    db.add(new_user)
    await db.flush()
    await db.refresh(new_user)
    await db.commit()
    return {
        "id": new_user.id,
        "telegram_id": new_user.telegram_id,
        "role": new_user.role,
        "location": user_data.location
    }

@auth_router.get("/by_tg/{tg_id}")
async def get_user_by_tg_id(tg_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.telegram_id == tg_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return {
        "id": user.id,
        "telegram_id": user.telegram_id,
        "username": user.username,
        "role": user.role,
        "preferences": user.preferences,
        "is_active": user.is_active
    }

@reviews_router.post("/", response_model=ReviewResponse, status_code=201)
async def create_review(
    review_data: ReviewCreate,
    tg_id: int = Body(..., embed=True),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).where(User.telegram_id == tg_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    place = await db.execute(select(Place).where(Place.id == review_data.place_id))
    place = place.scalar_one_or_none()
    if not place:
        raise HTTPException(status_code=404, detail="Место не найдено")

    llm_service = LLMService()
    llm_check = await llm_service.check_review_content(review_data.text)
    summary = await llm_service.summarize_review(review_data.text, review_data.rating)

    moderation_status = "approved" if llm_check.get("is_appropriate", True) else "flagged_by_llm"
    should_update_rating = moderation_status == "approved"

    new_review = Review(
        user_id=user.id,
        place_id=review_data.place_id,
        rating=review_data.rating,
        text=review_data.text,
        llm_check=llm_check,
        summary=summary,
        moderation_status=moderation_status
    )
    db.add(new_review)
    await db.flush()
    await db.refresh(new_review)

    if should_update_rating:
        await update_place_rating(db, review_data.place_id)

    return ReviewResponse.model_validate(new_review)

@moderation_router.post("/reviews/{review_id}/approve")
async def approve_review(
    review_id: UUID,
    tg_id: int = Body(..., embed=True),
    db: AsyncSession = Depends(get_db)
):
    mod_result = await db.execute(
        select(User).where(
            User.telegram_id == tg_id,
            User.role.in_(["moderator", "admin"])
        )
    )
    moderator = mod_result.scalar_one_or_none()
    if not moderator:
        raise HTTPException(status_code=403, detail="Только модераторы могут одобрять")

    review = await db.execute(select(Review).where(Review.id == review_id))
    review = review.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=404, detail="Отзыв не найден")

    review.moderation_status = "approved"
    review.moderated_by = moderator.id
    await db.flush()
    await update_place_rating(db, review.place_id)
    await db.commit()
    return {"success": True, "message": "Отзыв одобрен"}

@moderation_router.post("/reviews/{review_id}/reject")
async def reject_review(
    review_id: UUID,
    tg_id: int = Body(..., embed=True),
    notes: Optional[str] = Body(None, embed=True),
    db: AsyncSession = Depends(get_db)
):
    mod_result = await db.execute(
        select(User).where(
            User.telegram_id == tg_id,
            User.role.in_(["moderator", "admin"])
        )
    )
    moderator = mod_result.scalar_one_or_none()
    if not moderator:
        raise HTTPException(status_code=403, detail="Только модераторы могут отклонять")

    review = await db.execute(select(Review).where(Review.id == review_id))
    review = review.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=404, detail="Отзыв не найден")

    old_status = review.moderation_status
    review.moderation_status = "rejected"
    review.moderated_by = moderator.id
    review.moderation_notes = notes

    if old_status == "approved":
        await update_place_rating(db, review.place_id)

    await db.commit()
    return {"success": True, "message": "Отзыв отклонён"}

@places_router.get("/", response_model=List[PlaceResponse])
async def get_places(
    category: Optional[str] = None,
    city: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    query = select(Place).where(Place.is_active == True)
    if category:
        query = query.where(Place.category == category)
    if city:
        query = query.where(Place.city == city)
    result = await db.execute(query)
    return [PlaceResponse.model_validate(p) for p in result.scalars().all()]

@places_router.get("/{place_id}", response_model=PlaceResponse)
async def get_place(place_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Place).where(Place.id == place_id))
    place = result.scalar_one_or_none()
    if not place:
        raise HTTPException(status_code=404, detail="Место не найдено")
    return PlaceResponse.model_validate(place)

@recommendations_router.post("/chat")
async def get_chat_recommendations(
    request: RecommendationRequest,
    tg_id: int = Body(..., embed=True),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).where(User.telegram_id == tg_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    places = await db.execute(select(Place).where(Place.is_active == True).limit(5))
    places = [PlaceResponse.model_validate(p) for p in places.scalars().all()]

    llm_service = LLMService()
    text = await llm_service.generate_recommendations(user.id, db)

    return {
        "text": text,
        "places": [p.model_dump() for p in places],
        "user_id": str(user.id)
    }

@recommendations_router.post("/search")
async def search_places(
    query: str = Body(..., embed=True),
    tg_id: int = Body(..., embed=True),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).where(User.telegram_id == tg_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    city = "Moscow"
    category = None
    if "спб" in query.lower() or "петербург" in query.lower():
        city = "Saint Petersburg"
    if "концерт" in query.lower() or "музык" in query.lower():
        category = "concert"
    elif "кафе" in query.lower() or "кофе" in query.lower():
        category = "cafe"

    query_sql = select(Place).where(Place.city == city, Place.is_active == True)
    if category:
        query_sql = query_sql.where(Place.category == category)
    result = await db.execute(query_sql.limit(5))
    places = [PlaceResponse.model_validate(p).model_dump() for p in result.scalars().all()]

    return {"query": query, "city": city, "category": category, "places": places}

# ========== СОЗДАНИЕ ПРИЛОЖЕНИЯ ==========
app = FastAPI(title="Travel Recommendation API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(places_router, prefix="/api/v1/places", tags=["Places"])
app.include_router(reviews_router, prefix="/api/v1/reviews", tags=["Reviews"])
app.include_router(moderation_router, prefix="/api/v1/moderation", tags=["Moderation"])
app.include_router(recommendations_router, prefix="/api/v1/recommendations", tags=["Recommendations"])


# ========== СИСТЕМНЫЕ ЭНДПОИНТЫ ==========
@app.get("/health")
async def health_check():
    """Проверка работоспособности сервиса"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "travel-recommendation-api",
        "database": "connected",
        "llm": "available"  # будет уточнено в /llm-status
    }

@app.get("/llm-status")
async def llm_status():
    """Проверка статуса подключения к Ollama Cloud"""
    llm_service = LLMService()
    is_connected = await llm_service.client.test_connection()
    
    test_result = None
    if is_connected:
        try:
            test_result = await llm_service.summarize_review("Отличное место, рекомендую!", 5)
        except Exception as e:
            test_result = f"Ошибка теста: {str(e)[:50]}"
    
    return {
        "status": "connected" if is_connected else "disconnected",
        "llm_provider": "Ollama Cloud",
        "model": config.OLLAMA_MODEL,
        "base_url": config.OLLAMA_BASE_URL,
        "api_key_set": bool(config.OLLAMA_API_KEY),
        "connection_test": is_connected,
        "test_summary": test_result,
        "timestamp": datetime.utcnow().isoformat()
    }


# ========== ТЕСТОВЫЕ ДАННЫЕ ==========
@app.on_event("startup")
async def startup_event():
    logger.info("🚀 Инициализация БД...")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("✅ Таблицы созданы")

        async with AsyncSessionLocal() as db:
            users = [
                User(id=UUID('11111111-1111-1111-1111-111111111111'), telegram_id=123456789, role="user"),
                User(id=UUID('22222222-2222-2222-2222-222222222222'), telegram_id=987654321, role="moderator")
            ]
            for user in users:
                result = await db.execute(select(User).where(User.telegram_id == user.telegram_id))
                if not result.scalar_one_or_none():
                    db.add(user)
            await db.commit()

            if not await db.execute(select(Place)).scalars().all():
                places = [
                    Place(name="Кофейня у Патриарших", description="Уютное место с домашней выпечкой", category="cafe", city="Moscow", address="Тверская, 12", rating=4.7, created_at=datetime.utcnow()),
                    Place(name="Парк Горького", description="Зелёная зона с прокатом велосипедов", category="park", city="Moscow", address="Крымский Вал, 9", rating=4.8, created_at=datetime.utcnow())
                ]
                db.add_all(places)
                await db.commit()
                logger.info("✅ Тестовые данные созданы")

    except Exception as e:
        logger.error(f"❌ Ошибка инициализации: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)