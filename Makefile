# Makefile
.PHONY: help build up down logs ps restart clean test init parser

help: ## Показать эту справку
	@echo "Доступные команды:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

build: ## Собрать все Docker образы
	docker-compose build --parallel

up: ## Запустить все сервисы
	docker-compose up -d

down: ## Остановить все сервисы
	docker-compose down

logs: ## Показать логи всех сервисов
	docker-compose logs -f

logs-backend: ## Логи бэкенда
	docker-compose logs -f backend

logs-bot: ## Логи бота
	docker-compose logs -f bot

logs-parser: ## Логи парсера
	docker-compose logs -f parser

ps: ## Показать статус сервисов
	docker-compose ps

restart: ## Перезапустить все сервисы
	docker-compose restart

clean: ## Очистить все (стоп, удалить контейнеры, тома, образы)
	docker-compose down -v --rmi all

test: ## Запустить тесты
	docker-compose exec backend pytest tests/

init: ## Инициализировать БД (создать таблицы)
	docker-compose exec backend python -c "from src.database import create_tables; import asyncio; asyncio.run(create_tables())"

parser: ## Запустить парсер
	docker-compose run --rm parser

parser-city: ## Запустить парсер для конкретного города
	docker-compose run --rm -e PARSE_CITY=$(city) parser

shell-backend: ## Запустить shell в контейнере бэкенда
	docker-compose exec backend bash

shell-bot: ## Запустить shell в контейнере бота
	docker-compose exec bot bash

shell-db: ## Подключиться к БД
	docker-compose exec postgres psql -U postgres -d travel_db

health: ## Проверить здоровье сервисов
	@echo "=== Health Checks ==="
	@echo "Backend: $$(curl -s http://localhost:8000/health | jq -r .status || echo 'unavailable')"
	@echo "Postgres: $$(docker-compose exec postgres pg_isready -U postgres && echo 'ready' || echo 'unavailable')"
	@echo "Redis: $$(docker-compose exec redis redis-cli ping | grep -q PONG && echo 'ready' || echo 'unavailable')"

stats: ## Статистика системы
	@echo "=== System Statistics ==="
	@echo "Containers:"
	@docker-compose ps
	@echo ""
	@echo "Database size:"
	@docker-compose exec postgres psql -U postgres -d travel_db -c "SELECT pg_size_pretty(pg_database_size('travel_db'));"
	@echo ""
	@echo "Table counts:"
	@docker-compose exec postgres psql -U postgres -d travel_db -c "SELECT relname as table, n_live_tup as rows FROM pg_stat_user_tables ORDER BY n_live_tup DESC;"