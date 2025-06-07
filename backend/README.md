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
DATABASE_URL=postgresql://postgres:postgres@localhost:55432/jobs-parser
```

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
GET http://localhost:58000/jobs
```

Пример ответа:

```json
[]
```

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

alembic revision --autogenerate -m "add apply url field"