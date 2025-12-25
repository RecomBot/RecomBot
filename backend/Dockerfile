FROM python:3.11-slim

WORKDIR /app

# Копируем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем общий config
COPY shared/ ./shared/

# Копируем исходный код
COPY src/ ./src/

CMD ["uvicorn", "src.main_single:app", "--host", "0.0.0.0", "--port", "8000"]