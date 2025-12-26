# parser/Dockerfile - БЕЗ SELENIUM
FROM python:3.11-slim

WORKDIR /app

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Обновляем pip
RUN python -m pip install --upgrade pip

# Копируем зависимости
COPY parser/requirements.txt .
RUN pip install --no-cache-dir --default-timeout=100 -r requirements.txt

# Копируем shared модули
COPY shared/ ./shared/

# Копируем код парсера
COPY parser/ .

# Команда запуска
CMD ["python", "parser.py"]