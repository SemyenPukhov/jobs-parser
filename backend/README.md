# 🧱 jobs-parser

Минималистичный стек для бэкенда парсера вакансий:  
**FastAPI + SQLModel + PostgreSQL + Adminer**

---

## 🚀 Быстрый старт

### 1️⃣ Клонировать репозиторий

```bash
git clone https://github.com/your-user/jobs-parser.git
cd jobs-parser
```

---

### 2️⃣ Запустить PostgreSQL и Adminer (Docker)

```bash
docker compose up -d
```

Открыть в браузере:

- Adminer: http://localhost:8080  
- Подключение:
  - System: PostgreSQL  
  - Server: db  
  - User: postgres  
  - Password: postgres  
  - Database: jobs-parser

---

### 3️⃣ Настроить Python окружение

```bash
python3 -m venv venv
source venv/bin/activate
cd backend
pip install -r requirements.txt
```

---

### 4️⃣ Создать файл `.env`

```bash
cp .env.example .env
```

Содержимое `.env`:

```env
# Environment
ENVIRONMENT=dev

# Database
DB_USER=postgres
DB_PASSWORD=postgres
DB_NAME=jobs_parser
DB_HOST=localhost
DB_PORT=55432

# Slack
SLACK_BOT_TOKEN=xoxb-your-slack-bot-token
SLACK_CHANNEL_ID=C12345678
SLACK_MANAGER_ID=U12345678

# AI Matching (OpenRouter)
OPENROUTER_API_KEY=sk-or-v1-your-openrouter-api-key
DEVELOPERS_API_URL=http://103.54.16.194/api/resumes/active/all
MATCHING_THRESHOLD_HIGH=70
MATCHING_THRESHOLD_LOW=50

# Proxy (для JustRemote парсера)
PROXY_HOST=your-proxy-server-ip
# Для локальной разработки оставьте пустым или укажите IP продакшн сервера

# JustRemote credentials
JUST_REMOTE_LOGIN=your-email@example.com
JUST_REMOTE_PWD=your-password
```

---

## 🔒 Настройка прокси-сервера (Production)

Для парсинга JustRemote используется **Tinyproxy** с базовой авторизацией.

### Запуск прокси на продакшн сервере:

```bash
# 1. Создайте конфигурационный файл
cat > /tmp/tinyproxy.conf << 'EOF'
Port 8888
Listen 0.0.0.0
Timeout 600
DefaultErrorFile "/usr/share/tinyproxy/default.html"
LogFile "/var/log/tinyproxy/tinyproxy.log"
LogLevel Info
MaxClients 100
MinSpareServers 5
MaxSpareServers 20
StartServers 10
MaxRequestsPerChild 0
Allow 0.0.0.0/0
ViaProxyName "tinyproxy"
BasicAuth JOBS_PARSER KfhofKvhW9
EOF

# 2. Запустите Tinyproxy в Docker
docker run -d \
  --name proxy \
  --restart unless-stopped \
  -p 8000:8888 \
  -v /tmp/tinyproxy.conf:/etc/tinyproxy/tinyproxy.conf \
  vimagick/tinyproxy

# 3. Проверьте работу
docker logs proxy
curl -x "http://JOBS_PARSER:KfhofKvhW9@localhost:8000" https://justremote.co/a/sign-in -I
```

### Настройка .env для использования прокси:

```env
# На продакшн сервере (где запущен парсер)
PROXY_HOST=localhost  # или IP сервера где запущен Tinyproxy

# На локальной машине для разработки
PROXY_HOST=YOUR_PROD_SERVER_IP  # IP продакшн сервера с прокси
```

### Проверка прокси:

```bash
# С любой машины
curl -x "http://JOBS_PARSER:KfhofKvhW9@PROXY_HOST:8000" https://justremote.co/a/sign-in -I

# Должен вернуть HTTP/1.0 200 Connection established
```

**Важно:** Прокси необходим только для парсера JustRemote. Другие парсеры работают без прокси.

---

### 5️⃣ Запустить FastAPI

```bash
uvicorn app.main:app --reload --port 58000
```

- Swagger UI: http://localhost:58000/docs  
- Healthcheck: http://localhost:58000/

---

## 📦 API

### Получить все jobs

```http
GET http://localhost:58000/api/jobs
```

### Получить необработанные jobs

```http
GET http://localhost:58000/api/pending-jobs?source=startup.jobs
```

### Запустить матчинг разработчиков (ручной запуск)

```http
POST http://localhost:58000/api/matching/run
```

Требуется авторизация. Запускает процесс матчинга в фоне и отправляет результаты в Slack.

---

## 🤖 AI Матчинг разработчиков

Система автоматически сопоставляет свободных разработчиков с открытыми вакансиями используя LLM (OpenRouter).

### Как это работает:

1. **Получение данных**: Система получает список активных разработчиков из внешнего API
2. **Фильтрация вакансий**: Отбираются только удаленные вакансии (исключаются офисные)
3. **AI оценка**: LLM оценивает каждого разработчика для каждой вакансии (0-100 баллов)
4. **Уведомление**: Результаты отправляются в Slack с тегом ответственного менеджера

### Категории совпадений:

- **✅ Отлично подходят (70-100)** - рекомендуется подавать
- **⚠️ Возможно подходят (50-69)** - стоит рассмотреть
- **❌ Не подходят (0-49)** - не показываются

### Расписание:

Автоматический запуск: **понедельник-пятница в 9:00 МСК**

### Настройка:

1. Получить API ключ на [OpenRouter.ai](https://openrouter.ai/)
2. Добавить `OPENROUTER_API_KEY` в `.env`
3. Указать `SLACK_MANAGER_ID` для тегирования менеджера
4. Настроить пороги `MATCHING_THRESHOLD_HIGH` и `MATCHING_THRESHOLD_LOW`

---

## 📁 Структура проекта

```
jobs-parser/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── api.py
│   │   ├── models.py
│   │   └── db.py
│   ├── requirements.txt
│   ├── .env.example
│   └── README.md
├── docker-compose.yml
└── venv/
```

---

## 🛠 Используемый стек

| Компонент   | Технология          |
|-------------|---------------------|
| Backend     | FastAPI             |
| ORM         | SQLModel            |
| База данных | PostgreSQL (Docker) |
| GUI для БД  | Adminer (Docker)    |
| Python env  | venv (стандартный)  |

---

## 🔧 Полезные команды

```bash
# Остановить все контейнеры
docker compose down

# Перезапустить с чистой базой
docker compose down -v
docker compose up -d
```



alembic revision --autogenerate -m "add field X"
alembic upgrade head

Например, open-source инструменты типа:

gpt-scraper

llama_parse

alembic revision --autogenerate -m "replace int id with uuid"



<!-- clean up prod -->
docker image prune -f
docker container prune -f
docker network prune -f
docker builder prune -f