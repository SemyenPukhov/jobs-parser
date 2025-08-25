# Было (плавающее "slim" -> сейчас trixie):
# FROM python:3.11-slim
# Стало: явно фиксируемся на Debian 12 (bookworm)
FROM python:3.11-slim-bookworm

WORKDIR /app

# Билд-зависимости для wheels (psycopg2 и т.п.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
 && rm -rf /var/lib/apt/lists/*

# Python-зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwright: ставим браузер + системные зависимости одной командой
# (без legacy install-deps)
RUN playwright install --with-deps chromium

# Остальной код
COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
