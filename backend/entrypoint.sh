#!/bin/bash
# backend/entrypoint.sh

set -e

# Определяем какой сервис запускать
if [ "$1" = "parser" ]; then
    echo "Запуск парсера..."
    exec python src/parser_unified.py --schedule
elif [ "$1" = "parser-once" ]; then
    echo "Запуск парсера один раз..."
    exec python src/parser_unified.py --once
elif [ "$1" = "parser-test" ]; then
    echo "Запуск тестового парсера..."
    exec python src/parser_unified.py --test
else
    echo "Запуск основного приложения..."
    exec uvicorn src.main_single:app --host 0.0.0.0 --port 8000
fi