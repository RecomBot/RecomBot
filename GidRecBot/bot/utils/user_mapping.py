# bot/utils/user_mapping.py
from uuid import UUID

# Маппинг telegram_id на тестовых пользователей бэкенда
USER_MAPPING = {
    # Обычный пользователь
    123456789: UUID("11111111-1111-1111-1111-111111111111"),  # user
    
    # Модератор (если у вас есть telegram_id 987654321)
    987654321: UUID("22222222-2222-2222-2222-222222222222"),  # moderator
    
    # Админ (если у вас есть telegram_id 999999999)
    999999999: UUID("33333333-3333-3333-3333-333333333333"),  # admin
}

def get_backend_user_id(tg_id: int) -> UUID:
    """Получает ID пользователя в бэкенде по telegram_id"""
    return USER_MAPPING.get(tg_id, USER_MAPPING[123456789])  # по умолчанию user