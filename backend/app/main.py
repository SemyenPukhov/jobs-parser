from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import router as api_router
from app.db import init_db

app = FastAPI()

# Разрешённые источники (можно указать "*" для всех)
origins = [
    "http://localhost:5173",  # Vite dev сервер
    "http://127.0.0.1:5173",
    "https://your-frontend-domain.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # Или ["*"] для разрешения всех
    allow_credentials=True,
    allow_methods=["*"],    # Разрешить все методы: GET, POST и т.д.
    allow_headers=["*"],    # Разрешить все заголовки
)


@app.on_event("startup")
def startup():
    init_db()


app.include_router(api_router)
