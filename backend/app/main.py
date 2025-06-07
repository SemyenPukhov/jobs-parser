from fastapi import FastAPI
from app.api import router as api_router
from app.db import init_db

app = FastAPI()


@app.on_event("startup")
def startup():
    init_db()


app.include_router(api_router)
