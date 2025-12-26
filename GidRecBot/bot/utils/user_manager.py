# GidRecBot/bot/utils/user_manager.py (ПОЛНОСТЬЮ ПЕРЕПИСАННЫЙ)
import logging
from typing import Optional, Dict, Any
from .http_client import http_client
from .cache import user_cache
from uuid import UUID
logger = logging.getLogger(__name__)

async def get_or_create_user(
    tg_id: int, 
    username: str = None, 
    first_name: str = None, 
    last_name: str = None
) -> Optional[Dict[str, Any]]:
    """
    Получает или создает пользователя в backend.
    Возвращает информацию о пользователе из БД.
    """
    # Проверяем кэш
    cache_key = f"user_{tg_id}"
    cached_user = user_cache.get(cache_key)
    if cached_user:
        logger.info(f"✅ Пользователь {tg_id} найден в кэше")
        return cached_user
    
    logger.info(f"🔄 Начинаем get_or_create_user для tg_id={tg_id}")
    logger.info(f"   Переданные параметры: username='{username}', first_name='{first_name}'")
    
    try:
        # 1. Пробуем получить существующего пользователя
        logger.info(f"   Вызываем http_client.get_telegram_user({tg_id})")
        user_info = await http_client.get_telegram_user(tg_id)
        
        if user_info:
            logger.info(f"✅ Пользователь {tg_id} найден в БД: {user_info.get('username', 'N/A')}")
            logger.info(f"   Данные из БД: username='{user_info.get('username')}', first_name='{user_info.get('first_name')}'")
            
            # Проверяем нужно ли обновить информацию
            needs_update = False
            update_data = {}
            
            # Логируем сравнение
            if username and user_info.get("username") != username:
                logger.info(f"   Обновляем username: '{user_info.get('username')}' -> '{username}'")
                update_data["username"] = username
                needs_update = True
                
            if first_name and user_info.get("first_name") != first_name:
                logger.info(f"   Обновляем first_name: '{user_info.get('first_name')}' -> '{first_name}'")
                update_data["first_name"] = first_name
                needs_update = True
                
            if last_name and user_info.get("last_name") != last_name:
                logger.info(f"   Обновляем last_name: '{user_info.get('last_name')}' -> '{last_name}'")
                update_data["last_name"] = last_name
                needs_update = True
            
            if needs_update:
                logger.info(f"📝 Обновляем информацию пользователя {tg_id}")
                logger.info(f"   Данные для обновления: {update_data}")
                user_info = await http_client.create_telegram_user(
                    telegram_id=tg_id,
                    username=username or user_info.get("username"),
                    first_name=first_name or user_info.get("first_name"),
                    last_name=last_name or user_info.get("last_name"),
                    role=user_info.get("role", "user")
                )
                if user_info:
                    logger.info(f"✅ Пользователь {tg_id} обновлен")
            else:
                logger.info(f"✅ Данные пользователя {tg_id} актуальны, обновление не требуется")
        else:
            # 2. Пользователь не найден - создаем нового
            logger.info(f"➕ Пользователь {tg_id} не найден в БД - создаем нового")
            user_info = await http_client.create_telegram_user(
                telegram_id=tg_id,
                username=username or f"user_{tg_id}",
                first_name=first_name or "",
                last_name=last_name or "",
                role="user"
            )
            if user_info:
                logger.info(f"✅ Новый пользователь {tg_id} создан: {user_info.get('id', 'N/A')}")
        
        if user_info:
            # Сохраняем в кэш
            user_cache.set(cache_key, user_info)
            logger.info(f"💾 Пользователь {tg_id} сохранен в кэш")
            return user_info
        else:
            logger.error(f"❌ Не удалось создать/получить пользователя {tg_id}")
            return None
            
    except Exception as e:
        logger.error(f"❌ Ошибка в get_or_create_user для {tg_id}: {e}", exc_info=True)
        return None

async def ensure_user_exists(tg_id: int, **user_data) -> Optional[Dict[str, Any]]:
    """
    Устаревшая функция для совместимости.
    Использует get_or_create_user.
    """
    return await get_or_create_user(
        tg_id,
        username=user_data.get("username"),
        first_name=user_data.get("first_name"),
        last_name=user_data.get("last_name")
    )

async def get_user_info(tg_id: int) -> Optional[Dict[str, Any]]:
    """Получение информации о пользователе"""
    logger.info(f"🔍 Вызов get_user_info для tg_id={tg_id}")
    
    try:
        # Просто получаем пользователя без обновления данных
        # НЕ передаем username и first_name, чтобы не пытаться обновить
        cache_key = f"user_{tg_id}"
        cached_user = user_cache.get(cache_key)
        
        if cached_user:
            logger.info(f"✅ Пользователь {tg_id} найден в кэше")
            return cached_user
        
        logger.info(f"🔄 Пробуем получить пользователя {tg_id} из БД")
        user_info = await http_client.get_telegram_user(tg_id)
        
        if user_info:
            logger.info(f"✅ Пользователь {tg_id} получен из БД: {user_info.get('username', 'N/A')}")
            # Сохраняем в кэш
            user_cache.set(cache_key, user_info)
            return user_info
        else:
            logger.warning(f"⚠️ Пользователь {tg_id} не найден в БД")
            # Пробуем создать через get_or_create_user
            user_info = await get_or_create_user(tg_id)
            return user_info
            
    except Exception as e:
        logger.error(f"❌ Ошибка в get_user_info для {tg_id}: {e}", exc_info=True)
        return None

async def switch_user_role(tg_id: int) -> bool:
    """
    Устаревшая функция.
    Теперь просто создает/получает пользователя.
    """
    user = await get_or_create_user(tg_id)
    return user is not None

def get_backend_user_id(tg_id: int) -> str:
    """Получает UUID пользователя в бэкенде"""
    # Эта функция теперь работает с реальными данными через кэш
    cache_key = f"user_{tg_id}"
    cached_user = user_cache.get(cache_key)
    
    if cached_user:
        return cached_user.get("id", "")
    
    # Если нет в кэше, возвращаем пустую строку
    # Реальный ID будет получен при следующем вызове get_or_create_user
    return ""