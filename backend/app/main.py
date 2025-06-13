from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import jobs, auth
from app.db import init_db
from app.scheduler import start_scheduler

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Include routers
app.include_router(jobs.router, prefix="/api", tags=["jobs"])
app.include_router(auth.router, prefix="/api", tags=["auth"])


@app.on_event("startup")
def on_startup():
    init_db()
    start_scheduler()
