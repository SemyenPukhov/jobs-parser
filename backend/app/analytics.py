from datetime import datetime
from typing import Dict, List, Tuple
from sqlmodel import Session, select
from .models import JobProcessingStatus, Job, User
from collections import defaultdict
from .utils.slack import send_slack_message
from .logger import logger
from .db import get_session


def get_jobs_collection_analytics(db: Session, date: datetime = None) -> str:
    """
    Generate analytics of collected jobs per source for the day.

    Args:
        db: Database session
        date: Date to generate analytics for (defaults to current date)

    Returns:
        str: Formatted analytics message
    """
    if date is None:
        date = datetime.utcnow()

    # Get start and end of the day
    start_of_day = datetime(date.year, date.month, date.day, 0, 0, 0)
    end_of_day = datetime(date.year, date.month, date.day, 23, 59, 59)

    # Query all jobs parsed for the day
    statement = select(Job).where(
        Job.parsed_at >= start_of_day,
        Job.parsed_at <= end_of_day
    )
    jobs = db.exec(statement).all()

    # Group by source
    source_stats = defaultdict(int)
    for job in jobs:
        source_stats[job.source] += 1

    # Get count of unprocessed jobs
    unprocessed_statement = (
        select(Job)
        .outerjoin(JobProcessingStatus, Job.id == JobProcessingStatus.job_id)
        .where(JobProcessingStatus.job_id == None)
    )
    unprocessed_count = len(db.exec(unprocessed_statement).all())

    # Format the message
    date_str = date.strftime("%d %B %Y")
    message = f"🔎 *Отчет по собранным вакансиям за* {date_str}\n\n"

    if not source_stats:
        message += "За сегодня новых вакансий не добавлено. 🥲\n"
    else:
        for source, count in source_stats.items():
            message += f"[{source}] - добавили {count}\n"

    message += f"\nНеобработанных вакансий: {unprocessed_count} ⏳"

    return message


def get_daily_analytics(db: Session, date: datetime = None) -> str:
    """
    Generate daily analytics of job applications and rejections per manager.

    Args:
        db: Database session
        date: Date to generate analytics for (defaults to current date)

    Returns:
        str: Formatted analytics message
    """
    if date is None:
        date = datetime.utcnow()

    # Get start and end of the day
    start_of_day = datetime(date.year, date.month, date.day, 0, 0, 0)
    end_of_day = datetime(date.year, date.month, date.day, 23, 59, 59)

    # Query all job processing statuses for the day
    statement = select(JobProcessingStatus).where(
        JobProcessingStatus.created_at >= start_of_day,
        JobProcessingStatus.created_at <= end_of_day
    )
    statuses = db.exec(statement).all()

    # Format the message
    date_str = date.strftime("%d %B %Y")
    message = f"🧐 *Аналитика подач за* {date_str}\n\n"

    if not statuses:
        message += "За сегодня подач и отказов нет. 🥲\n"
        return message

    # Group by manager (email)
    manager_stats: Dict[str, Tuple[List[Tuple[str, str]], List[Tuple[str, str]]]] = defaultdict(
        lambda: ([], [])  # (applications, rejections)
    )

    for status in statuses:
        # Get the job and its URL
        job = db.get(Job, status.job_id)
        if not job:
            continue

        # Get the manager (user) who processed this job
        # Note: You might need to add a user_id field to JobProcessingStatus if not present
        user = db.get(User, status.user_id) if hasattr(
            status, 'user_id') else None
        manager_email = user.email if user else "Unknown"

        if status.status == "Applied":
            manager_stats[manager_email][0].append(
                (job.url, status.comment or ""))
        elif status.status == "NotSuitable":
            manager_stats[manager_email][1].append(
                (job.url, status.comment or ""))

    for manager_email, (applications, rejections) in manager_stats.items():
        message += f"Менеджер {manager_email}\n"
        message += f"Подач - {len(applications)}\n"

        for url, comment in applications:
            message += f"- {url} - {comment}\n"

        message += f"\nОтказов - {len(rejections)}\n"
        for url, comment in rejections:
            message += f"- {url} - {comment}\n"

        message += "\n"

    return message


async def send_daily_analytics():
    """Отправляет ежедневную аналитику в Slack"""
    logger.info("📊 Начинаю формирование ежедневной аналитики")

    try:
        session = next(get_session())

        # Получаем оба отчета
        jobs_analytics = get_jobs_collection_analytics(session)
        applications_analytics = get_daily_analytics(session)

        # Объединяем отчеты
        full_message = f"{jobs_analytics}\n\n{applications_analytics}"

        # Отправляем сообщение в Slack
        await send_slack_message(full_message)
        logger.info("✅ Ежедневная аналитика успешно отправлена")
    except Exception as e:
        error_message = f"❌ Ошибка при отправке ежедневной аналитики: {str(e)}"
        logger.error(error_message)
        await send_slack_message(error_message)
    finally:
        session.close()
