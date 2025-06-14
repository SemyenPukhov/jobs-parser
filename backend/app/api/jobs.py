from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from app.parsers.startup_jobs import scrape_startup_jobs
from app.parsers.thehub_io import scrape_thehub_jobs
from app.parsers.vseti_app import scrape_vseti_app_jobs
from app.parsers.dev_by import scrape_devby_jobs
from app.utils.slack import send_slack_message

from sqlmodel import Session, select, desc
from sqlalchemy.orm import selectinload
from app.db import get_session
from app.models import Job, JobProcessingStatus, JobProcessingStatusEnum, JobRead, User
from app.auth import get_current_user
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel
from typing import Optional, List


class AcceptOrRejectJobRequest(BaseModel):
    comment: str


class PendingJobRead(BaseModel):
    id: UUID
    title: str
    url: str
    source: str
    description: Optional[str]
    company: Optional[str]
    company_url: Optional[str]
    apply_url: Optional[str]
    salary: Optional[str]
    parsed_at: datetime

    class Config:
        orm_mode = True


class PendingJobsResponse(BaseModel):
    jobs: List[PendingJobRead]
    available_sources: List[str]


router = APIRouter()


@router.post("/scrape/startup-jobs")
async def run_scraper(
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    background_tasks.add_task(scrape_startup_jobs, session)
    return {"message": "Scraping started in background"}


@router.post("/scrape/devby-jobs")
async def run_scraper(
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    # current_user: User = Depends(get_current_user)
):
    background_tasks.add_task(scrape_devby_jobs, session)
    return {"message": "Scraping started in background"}


@router.post("/scrape/thehub-jobs")
async def run_scraper(
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    background_tasks.add_task(scrape_thehub_jobs, session)
    return {"message": "Scraping started in background"}


@router.post("/scrape/vseti-app-jobs")
async def run_scraper(
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    # current_user: User = Depends(get_current_user)
):
    background_tasks.add_task(scrape_vseti_app_jobs, session)
    return {"message": "Scraping started in background"}


@router.post("/jobs/{job_id}/accept")
async def accept(
    job_id: UUID,
    data: AcceptOrRejectJobRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
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
        user_id=current_user.id,
        status=JobProcessingStatusEnum.APPLIED,
        comment=data.comment,
        created_at=datetime.utcnow()
    )
    session.add(new_status)
    session.commit()
    session.refresh(new_status)

    # Отправляем уведомление в Slack
    message = f"Пользователь {current_user.email} откликнулся на запрос {job.url} и подал: {data.comment}"
    await send_slack_message(message)

    return {"success": True, "status_id": str(new_status.id)}


@router.post("/jobs/{job_id}/reject")
async def reject(
    job_id: UUID,
    data: AcceptOrRejectJobRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
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
        user_id=current_user.id,
        status=JobProcessingStatusEnum.NOT_SUITABLE,
        comment=data.comment,
        created_at=datetime.utcnow()
    )
    session.add(new_status)
    session.commit()
    session.refresh(new_status)

    # Отправляем уведомление в Slack
    message = f"Пользователь {current_user.email} отклонил запрос {job.url} по причине: {data.comment}"
    await send_slack_message(message)

    return {"success": True, "status_id": str(new_status.id)}


@router.get("/jobs", response_model=list[JobRead])
def list_jobs(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    statement = (
        select(Job)
        .outerjoin(JobProcessingStatus)
        .options(selectinload(Job.processing_status))
    )
    jobs = session.exec(statement).all()
    return jobs


@router.get("/pending-jobs", response_model=PendingJobsResponse)
def list_pending_jobs(
    source: Optional[str] = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    # Базовый запрос для pending jobs
    statement = (
        select(Job)
        .outerjoin(JobProcessingStatus, Job.id == JobProcessingStatus.job_id)
        .where(JobProcessingStatus.job_id == None)
    )

    # Добавляем фильтр по source, если он указан
    if source:
        statement = statement.where(Job.source == source)

    # Добавляем сортировку
    statement = statement.order_by(desc(Job.parsed_at))

    jobs = session.exec(statement).all()

    # Получаем все уникальные источники из всех pending jobs (без фильтра по source)
    all_sources_statement = (
        select(Job.source)
        .outerjoin(JobProcessingStatus, Job.id == JobProcessingStatus.job_id)
        .where(JobProcessingStatus.job_id == None)
        .distinct()
    )
    available_sources = [source for source in session.exec(
        all_sources_statement).all()]

    # Преобразуем Job в PendingJobRead
    pending_jobs = [
        PendingJobRead(
            id=job.id,
            title=job.title,
            url=job.url,
            source=job.source,
            description=job.description,
            company=job.company,
            company_url=job.company_url,
            apply_url=job.apply_url,
            salary=job.salary,
            parsed_at=job.parsed_at
        )
        for job in jobs
    ]

    return PendingJobsResponse(
        jobs=pending_jobs,
        available_sources=available_sources
    )
