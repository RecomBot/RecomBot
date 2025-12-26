
## Запуск
```bash
cd GidRecBot
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # вставьте BOT_TOKEN
python mock_server.py &  # в фоне
python -m bot

---

├── bot/                           # Пакет Telegram-бота (aiogram)
│   ├── __main__.py               # Точка входа: запуск polling
│   ├── config.py                 # Настройки: BOT_TOKEN, API_BASE_URL
│   ├── bot.py                    # Инициализация: Bot, Dispatcher, MemoryStorage
│   │
│   ├── middlewares/
│   │   └── logging.py            # Middleware для логирования всех сообщений и callback'ов
│   │
│   ├── handlers/                 # Роутеры (обработчики)
│   │   ├── __init__.py           # Пустой (делает папку Python-пакетом)
│   │   ├── main_router.py        # /help, /cancel — базовые команды
│   │   ├── register_router.py    # /start → выбор города (1 шаг), профиль, справка, кнопки
│   │   ├── llm_router.py         # Natural language → LLM-рекомендации + пагинация [⬅️][➡️]
│   │   ├── review_router.py      # FSM отзыва: оценка → текст → отправка на модерацию
│   │   └── moderation_router.py  # /modqueue, одобрение/отклонение отзывов (для модераторов)
│   │
│   ├── states/                   # FSM-состояния
│   │   ├── __init__.py
│   │   └── review.py             # ReviewStates: place_id → rating → text
│   │
│   ├── keyboards/                # Клавиатуры
│   │   ├── __init__.py
│   │   ├── inline.py             # get_location_keyboard(), get_rating_keyboard(), get_place_keyboard()
│   │
│   ├── utils/                    # Вспомогательные модули
│   │   ├── __init__.py
│   │   ├── http_client.py        # HTTP-клиент для бэкенда: register_user(), get_user_by_tg_id(), recommend(), approve_review()
│   │   └── cache.py              # TTLCache: кэширование tg_id → user (для скорости)
│   │
│   └── models/                   # Модели данных
│       ├── __init__.py
│       ├── place.py              # Place: форматирование рейтинга
│       └── user.py               # User: is_moderator, is_admin — для ролевой модели
│
├── mock_server.py                # Мок-бэкенд (для разработки без FastAPI)
├── .env                           # Переменные окружения: BOT_TOKEN=..., API_BASE_URL=http://localhost:8000
├── requirements.txt               # Зависимости: aiogram, aiohttp, python-dotenv
