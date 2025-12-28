from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from app.parsers.startup_jobs import scrape_startup_jobs
from app.parsers.thehub_io import scrape_thehub_jobs
from app.parsers.vseti_app import scrape_vseti_app_jobs
from app.parsers.dev_by import scrape_devby_jobs
from app.parsers.justremote_co import scrape_justremote_jobs
from app.parsers.remoteok import scrape_remoteok_jobs

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


class PostponeJobRequest(BaseModel):
    comment: Optional[str] = None


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
    matching_results: Optional[dict]
    amocrm_lead_id: Optional[str] = None

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


@router.post("/scrape/justremote-jobs")
async def run_scraper(
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    background_tasks.add_task(scrape_justremote_jobs, session)
    return {"message": "Scraping started in background"}


@router.post("/scrape/vseti-app-jobs")
async def run_scraper(
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    # current_user: User = Depends(get_current_user)
):
    background_tasks.add_task(scrape_vseti_app_jobs, session)
    return {"message": "Scraping started in background"}


@router.post("/scrape/remoteok-jobs")
async def run_remoteok_scraper(
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    background_tasks.add_task(scrape_remoteok_jobs, session)
    return {"message": "Remote OK scraping started in background"}


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


@router.post("/jobs/{job_id}/postpone")
async def postpone(
    job_id: UUID,
    data: PostponeJobRequest,
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
        status=JobProcessingStatusEnum.POSTPONED,
        comment=data.comment,
        created_at=datetime.utcnow()
    )
    session.add(new_status)
    session.commit()
    session.refresh(new_status)

    # Отправляем уведомление в Slack
    comment_text = f" с комментарием: {data.comment}" if data.comment else ""
    message = f"Пользователь {current_user.email} отложил запрос {job.url}{comment_text}"
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
            parsed_at=job.parsed_at,
            matching_results=job.matching_results,
            amocrm_lead_id=job.amocrm_lead_id
        )
        for job in jobs
    ]

    return PendingJobsResponse(
        jobs=pending_jobs,
        available_sources=available_sources
    )


@router.get("/postponed-jobs", response_model=PendingJobsResponse)
def list_postponed_jobs(
    source: Optional[str] = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    # Get jobs with POSTPONED status
    statement = (
        select(Job)
        .join(JobProcessingStatus, Job.id == JobProcessingStatus.job_id)
        .where(JobProcessingStatus.status == JobProcessingStatusEnum.POSTPONED)
    )

    # Add source filter if specified
    if source:
        statement = statement.where(Job.source == source)

    # Add sorting
    statement = statement.order_by(desc(Job.parsed_at))

    jobs = session.exec(statement).all()

    # Get all unique sources from postponed jobs
    all_sources_statement = (
        select(Job.source)
        .join(JobProcessingStatus, Job.id == JobProcessingStatus.job_id)
        .where(JobProcessingStatus.status == JobProcessingStatusEnum.POSTPONED)
        .distinct()
    )
    available_sources = [source for source in session.exec(
        all_sources_statement).all()]

    # Convert Job to PendingJobRead
    postponed_jobs = [
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
            parsed_at=job.parsed_at,
            matching_results=job.matching_results,
            amocrm_lead_id=job.amocrm_lead_id
        )
        for job in jobs
    ]

    return PendingJobsResponse(
        jobs=postponed_jobs,
        available_sources=available_sources
    )


@router.post("/matching/run")
async def manual_matching(
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
):
    """
    Manually trigger the matching process of developers with jobs.
    This runs in the background and sends results to Slack.
    """
    # Import here to avoid circular dependency issues at startup
    from app.matching import run_matching, send_matching_results
    
    async def run_matching_task():
        """Wrapper to run matching with proper session handling"""
        from app.db import get_session
        from app.logger import logger
        from app.utils.slack import send_slack_message
        
        logger.info("🔍 Начинаю ручной запуск матчинга")
        await send_slack_message("🔍 Ручной запуск матчинга разработчиков")
        
        session = next(get_session())
        try:
            results = await run_matching(session)
            if results:
                await send_matching_results(results, session)
                logger.info(f"✅ Матчинг завершен. Найдено совпадений для {len(results)} вакансий")
                await send_slack_message(f"✅ Ручной матчинг завершен. Обработано {len(results)} вакансий")
            else:
                logger.info("ℹ️ Матчинг завершен. Совпадений не найдено")
                await send_slack_message("ℹ️ Матчинг завершен. Совпадений не найдено")
        except Exception as e:
            error_msg = f"❌ Ошибка при матчинге: {str(e)}"
            logger.error(error_msg)
            await send_slack_message(error_msg)
        finally:
            session.close()
    
    background_tasks.add_task(run_matching_task)
    return {"message": "Matching started in background", "status": "started"}
