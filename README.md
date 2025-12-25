RecomBot/                          # ← корень репозитория
│
├── .env.example                   # ✅ ЕДИНЫЙ шаблон env для всех компонентов  
├── .gitignore                     # ✅ Игнорирует venv/, .env, __pycache__/  
├── docker-compose.yml             # ✅ Единый compose: backend, postgres, redis  
├── README.md                      # 📘 Инструкция по запуску, архитектура, демо  
│
├── shared/                        # 🔗 Общие модули (единая точка истины)
│   ├── __init__.py
│   └── config.py                  # ✅ Единый Config(PydanticSettings) для всего проекта
│
├── backend/                       # FastAPI + LLM + модерация
│   ├── src/
│   │   ├── __init__.py
│   │   ├── main_single.py         # ✅ Основной код: роутеры, модели, Ollama Cloud
│   │   └── ... (models/, etc.)
│   ├── Dockerfile                 # ✅ Собирает бэкенд с shared/config.py
│   └── requirements.txt           # fastapi, sqlalchemy, ollama, asyncpg...
│
├── GidRecBot/                     # Telegram-бот (aiogram)
│   ├── bot/                       # Пакет Aiogram-бота
│   │   ├── __main__.py           # Точка входа
│   │   ├── bot.py                # Bot, Dispatcher, MemoryStorage
│   │   ├── config.py             # ✅ УДАЛЁН (используется shared/config.py)
│   │   ├── middlewares/
│   │   ├── handlers/              # register_router.py, llm_router.py, review_router.py, moderation_router.py
│   │   ├── states/
│   │   ├── keyboards/
│   │   └── utils/
│   │       └── http_client.py     # ✅ Обновлён: вызывает /api/v1/ эндпоинты бэкенда
│   ├── __main__.py                # Запуск бота: python -m bot
│   ├── requirements.txt           # aiogram, aiohttp, python-dotenv, pydantic...
│   ├── .env                       # ← не коммитится (BOT_TOKEN, API_BASE_URL)
│   └── Dockerfile.bot             # ✅ Для запуска бота в Docker (опционально)
│
├── parser/                        # Парсер Афиши → PostgreSQL
│   ├── parser.py                  # Selenium-парсер для afisha.yandex.ru
│   ├── db.py                      # ✅ Использует shared/config.DATABASE_URL
│   ├── afisha_events_*.csv       # Результаты парсинга
│   └── requirements.txt           # selenium, pandas, sqlalchemy...
│

