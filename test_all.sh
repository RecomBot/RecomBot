#!/bin/bash

echo "=== Полное тестирование системы ==="

echo "1. Останавливаем все сервисы..."
docker-compose down

echo "2. Пересобираем образы..."
docker-compose build --no-cache

echo "3. Запускаем все сервисы..."
docker-compose up -d

echo "4. Ждем запуска..."
sleep 10

echo "5. Проверяем статус..."
docker-compose ps

echo "6. Проверяем здоровье..."
curl -s http://localhost:8000/health | jq -r '.status' || echo "API недоступен"

echo "7. Проверяем БД..."
docker-compose exec postgres psql -U postgres -d travel_db -c "SELECT 'users:' as table, COUNT(*) as count FROM users UNION ALL SELECT 'places:' as table, COUNT(*) as count FROM places UNION ALL SELECT 'reviews:' as table, COUNT(*) as count FROM reviews;"

echo "=== Тестирование завершено ==="