# backend/src/routers/health.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
from ..dependencies import get_db_session, get_llm
from ..services.llm import LLMService

router = APIRouter(tags=["Health"])

@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db_session)):
    """Проверка работоспособности сервиса"""
    # Проверка БД
    db_ok = False
    try:
        await db.execute(select(1))
        db_ok = True
    except Exception:
        pass
    
    return {
        "status": "healthy" if db_ok else "degraded",
        "timestamp": datetime.utcnow().isoformat(),
        "database": "connected" if db_ok else "disconnected",
        "service": "travel-recommendation-api",
        "version": "1.0.0"
    }

@router.get("/llm-status")
async def llm_status(llm: LLMService = Depends(get_llm)):
    """Проверка статуса LLM"""
    is_connected = await llm.check_connection()
    
    test_result = None
    if is_connected:
        test_result = await llm.summarize_review("Отличное место, рекомендую!", 5)
    
    return {
        "status": "connected" if is_connected else "disconnected",
        "llm_provider": "Ollama Cloud",
        "model": llm.model,
        "base_url": llm.base_url,
        "api_key_set": bool(llm.headers.get('Authorization')),
        "connection_test": is_connected,
        "test_summary": test_result[:100] if test_result else None,
        "timestamp": datetime.utcnow().isoformat()
    }