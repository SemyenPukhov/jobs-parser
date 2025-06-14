from datetime import datetime
from typing import Dict, List, Tuple
from sqlmodel import Session, select
from .models import JobProcessingStatus, Job, User
from collections import defaultdict


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
        user = db.get(User, status.user_id) if hasattr(status, 'user_id') else None
        manager_email = user.email if user else "Unknown"
        
        if status.status == "Applied":
            manager_stats[manager_email][0].append((job.url, status.comment or ""))
        elif status.status == "NotSuitable":
            manager_stats[manager_email][1].append((job.url, status.comment or ""))
    
    # Format the message
    date_str = date.strftime("%d %B %Y")
    message = f"Аналитика подачь за {date_str}\n\n"
    
    for manager_email, (applications, rejections) in manager_stats.items():
        message += f"Менеджер {manager_email}\n"
        message += f"Подачь - {len(applications)}\n"
        
        for url, comment in applications:
            message += f"- {url} - {comment}\n"
            
        message += f"\nОтказов - {len(rejections)}\n"
        for url, comment in rejections:
            message += f"- {url} - {comment}\n"
            
        message += "\n"
    
    return message 