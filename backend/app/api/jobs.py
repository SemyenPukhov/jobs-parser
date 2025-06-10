from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from app.parsers.startup_jobs import scrape_startup_jobs
from app.parsers.thehub_io import scrape_thehub_jobs
from sqlmodel import Session, select
from app.db import get_session
from app.models import Job, JobProcessingStatus, JobProcessingStatusEnum, JobRead
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel


class AcceptOrRejectJobRequest(BaseModel):
    comment: str


router = APIRouter()


@router.post("/scrape/startup-jobs")
async def run_scraper(background_tasks: BackgroundTasks, session: Session = Depends(get_session)):
    background_tasks.add_task(scrape_startup_jobs, session)
    return {"message": "Scraping started in background"}


@router.post("/scrape/thehub-jobs")
async def run_scraper(background_tasks: BackgroundTasks, session: Session = Depends(get_session)):
    background_tasks.add_task(scrape_thehub_jobs, session)
    return {"message": "Scraping started in background"}


@router.post("/jobs/{job_id}/accept")
async def accept(job_id: UUID, data: AcceptOrRejectJobRequest, session: Session = Depends(get_session)):
    job = session.exec(select(Job).where(Job.id == job_id)).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    existing_status = session.exec(
        select(JobProcessingStatus).where(JobProcessingStatus.job_id == job_id)
    ).first()

    if existing_status:
        return {"success": False, "reason": "Already processed"}

    new_status = JobProcessingStatus(
        job_id=job_id,
        status=JobProcessingStatusEnum.APPLIED,
        comment=data.comment,
        created_at=datetime.utcnow()
    )
    session.add(new_status)
    session.commit()
    session.refresh(new_status)

    return {"success": True, "status_id": str(new_status.id)}


@router.post("/jobs/{job_id}/reject")
async def accept(job_id: UUID, data: AcceptOrRejectJobRequest, session: Session = Depends(get_session)):
    job = session.exec(select(Job).where(Job.id == job_id)).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    existing_status = session.exec(
        select(JobProcessingStatus).where(JobProcessingStatus.job_id == job_id)
    ).first()

    if existing_status:
        return {"success": False, "reason": "Already processed"}

    new_status = JobProcessingStatus(
        job_id=job_id,
        status=JobProcessingStatusEnum.NOT_SUITABLE,
        comment=data.comment,
        created_at=datetime.utcnow()
    )
    session.add(new_status)
    session.commit()
    session.refresh(new_status)

    return {"success": True, "status_id": str(new_status.id)}


@router.get("/jobs", response_model=list[JobRead])
def list_jobs(session: Session = Depends(get_session)):
    jobs = session.exec(select(Job)).all()
    return jobs


@router.get("/pending-jobs", response_model=list[JobRead])
def list_pending_jobs(session: Session = Depends(get_session)):
    statement = (
        select(Job)
        .outerjoin(JobProcessingStatus, Job.id == JobProcessingStatus.job_id)
        .where(JobProcessingStatus.job_id == None)
    )
    jobs = session.exec(statement).all()
    return jobs
