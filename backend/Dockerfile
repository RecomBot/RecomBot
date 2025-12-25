FROM python:3.11-slim

WORKDIR /app

# Копируем зависимости ИЗ backend/
COPY backend/requirements.txt .    
RUN pip install --no-cache-dir -r requirements.txt

# Копируем shared/ из корня
COPY shared/ ./shared/

# Копируем исходный код бэкенда
COPY backend/src/ ./src/

CMD ["uvicorn", "src.main_single:app", "--host", "0.0.0.0", "--port", "8000"]