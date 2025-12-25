# backend/Dockerfile (ИСПРАВЛЕННЫЙ)
FROM python:3.11-slim-bookworm

WORKDIR /app

# 1. Устанавливаем системные зависимости для Selenium, Chrome и ChromeDriver
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    curl \
    # Основные зависимости для Chrome в Docker
    libnss3 \
    libxss1 \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libgtk-3-0 \
    libx11-xcb1 \
    libxcomposite1 \
    libxrandr2 \
    libgbm1 \
    libxcb-dri3-0 \
    libdrm2 \
    # Удалены проблемные пакеты
    # Для эмуляции дисплея
    xvfb \
    && rm -rf /var/lib/apt/lists/*

# 2. Устанавливаем Google Chrome
# Используем официальный метод от Google
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# 3. Устанавливаем ChromeDriver (АКТУАЛЬНЫЙ метод для версий Chrome >= 115)
# Получаем точную версию установленного Chrome
RUN CHROME_VERSION=$(google-chrome-stable --version | grep -oP '\d+\.\d+\.\d+\.\d+') \
    # Используем новый URL для загрузки, если версия Chrome >= 115[citation:2]
    && if [ $(echo $CHROME_VERSION | cut -d'.' -f1) -ge 115 ]; then \
        echo "Используем новый URL для ChromeDriver (Chrome версии >= 115)" \
        && CD_URL="https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/$CHROME_VERSION/linux64/chromedriver-linux64.zip" \
        && CD_ZIP="chromedriver-linux64.zip" \
        && CD_BIN="chromedriver-linux64/chromedriver"; \
    else \
        echo "Используем старый URL для ChromeDriver" \
        && CD_URL="https://chromedriver.storage.googleapis.com/$CHROME_VERSION/chromedriver_linux64.zip" \
        && CD_ZIP="chromedriver_linux64.zip" \
        && CD_BIN="chromedriver"; \
    fi \
    # Скачиваем и распаковываем ChromeDriver
    && echo "Скачиваем ChromeDriver для Chrome $CHROME_VERSION" \
    && wget -q $CD_URL -O /tmp/$CD_ZIP \
    && unzip /tmp/$CD_ZIP -d /tmp/ \
    && mv /tmp/$CD_BIN /usr/local/bin/chromedriver \
    && chmod +x /usr/local/bin/chromedriver \
    && rm /tmp/$CD_ZIP \
    && echo "ChromeDriver установлен в /usr/local/bin/chromedriver"

# Копируем зависимости Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходный код
COPY src/ ./src/

# Команда по умолчанию для основного приложения
CMD ["uvicorn", "src.main_single:app", "--host", "0.0.0.0", "--port", "8000"]