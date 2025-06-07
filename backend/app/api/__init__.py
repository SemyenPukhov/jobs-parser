from fastapi import APIRouter
from app.api import jobs

router = APIRouter()
router.include_router(jobs.router, prefix="/api")
