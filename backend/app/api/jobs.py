from fastapi import APIRouter, Depends
from app.parsers.startup_jobs import scrape_startup_jobs
from sqlmodel import Session, select
from app.db import get_session
from app.models import Job

router = APIRouter()


@router.post("/scrape/startup-jobs")
async def run_scraper(session: Session = Depends(get_session)):
    jobs = await scrape_startup_jobs(session)
    return {"added": len(jobs)}


@router.get("/jobs", response_model=list[Job])
def list_jobs(session: Session = Depends(get_session)):
    return session.exec(select(Job)).all()
