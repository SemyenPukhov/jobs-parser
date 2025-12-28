"""
Remote OK Parser
Fetches remote jobs from remoteok.io API and filters for software development positions.
"""

import httpx
import re
import time
from html import unescape
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlmodel import Session, select
from app.models import Job
from app.logger import logger
from app.utils.slack import send_slack_message


# API endpoint
API_URL = "https://remoteok.io/api"
SOURCE = "remoteok.io"

# Tags that indicate software development positions
# If ANY of these tags present - it's a dev job
DEV_TAGS = {
    # Core dev roles
    'dev', 'developer', 'programmer',
    'frontend', 'backend', 'fullstack', 'full-stack', 'full stack',
    'software engineer', 'software developer',
    'sre', 'site reliability',
    # Technologies (specific enough to indicate dev work)
    'react', 'vue', 'angular', 'javascript', 'typescript',
    'python', 'java', 'golang', 'rust', 'node', 'nodejs',
    'ios', 'android', 'devops', 'devsecops',
    'php', 'ruby', 'rails', 'django', 'flask', 'spring',
    'kubernetes', 'docker', 'terraform',
    'data engineer', 'ml engineer', 'machine learning',
    'c++', 'c#', '.net', 'dotnet', 'scala', 'kotlin', 'swift'
}


def strip_html_tags(html: str) -> str:
    """Remove HTML tags from string and decode HTML entities."""
    if not html:
        return ""
    # Remove HTML tags
    clean = re.sub(r'<[^>]+>', ' ', html)
    # Decode HTML entities
    clean = unescape(clean)
    # Normalize whitespace
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean


def format_salary(salary_min: Optional[int], salary_max: Optional[int]) -> Optional[str]:
    """Format salary range as string."""
    if salary_min and salary_max:
        return f"${salary_min:,} - ${salary_max:,}"
    elif salary_min:
        return f"${salary_min:,}+"
    elif salary_max:
        return f"Up to ${salary_max:,}"
    return None


def is_dev_job(tags: List[str]) -> bool:
    """
    Check if job is a software development position based on tags.
    Returns True if job has ANY dev-related tag (frontend, backend, react, etc.)
    """
    if not tags:
        return False
    
    tags_lower = {tag.lower() for tag in tags}
    
    # Check if it has any dev-related tags
    for dev_tag in DEV_TAGS:
        # Exact match
        if dev_tag in tags_lower:
            return True
        # Partial match (tag contains dev keyword)
        for tag in tags_lower:
            if dev_tag in tag:
                return True
    
    return False


async def fetch_jobs_from_api() -> List[Dict[str, Any]]:
    """
    Fetch jobs from Remote OK API.
    Returns list of job dictionaries.
    """
    headers = {
        "User-Agent": "JobsParser/1.0 (https://github.com/jobs-parser)"
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(API_URL, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                # First element is usually legal/info, skip it
                jobs = [item for item in data if isinstance(item, dict) and item.get("position")]
                logger.info(f"📊 Получено {len(jobs)} вакансий из Remote OK API")
                return jobs
            else:
                logger.error(f"❌ Ошибка при запросе к Remote OK API: {response.status_code}")
                return []
                
    except Exception as e:
        logger.error(f"❌ Ошибка при запросе к Remote OK API: {str(e)}")
        return []


def map_job_to_model(job_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Map Remote OK API response to Job model fields.
    """
    # Build job URL
    job_url = job_data.get("url", "")
    if not job_url and job_data.get("slug"):
        job_url = f"https://remoteok.io/remote-jobs/{job_data['slug']}"
    
    # Parse date
    parsed_at = datetime.utcnow()
    if job_data.get("date"):
        try:
            parsed_at = datetime.fromisoformat(job_data["date"].replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            pass
    
    return {
        "title": job_data.get("position", "Unknown Position"),
        "url": job_url,
        "description": strip_html_tags(job_data.get("description", "")),
        "company": job_data.get("company", "Unknown Company"),
        "company_url": job_data.get("company_url"),
        "salary": format_salary(
            job_data.get("salary_min"),
            job_data.get("salary_max")
        ),
        "source": SOURCE,
        "parsed_at": parsed_at,
    }


async def scrape_remoteok_jobs(session: Session) -> List[Job]:
    """
    Main function to scrape Remote OK jobs.
    Fetches from API, filters dev jobs, and saves to database.
    """
    all_jobs = []
    start_time = time.time()
    
    # Statistics for report
    stats = {
        "total_fetched": 0,
        "dev_jobs_found": 0,
        "added_to_db": 0,
        "duplicates_skipped": 0,
        "filtered_out": 0,
    }
    
    try:
        # Fetch jobs from API
        jobs_data = await fetch_jobs_from_api()
        stats["total_fetched"] = len(jobs_data)
        
        if not jobs_data:
            logger.warning("⚠️ Не получено вакансий из Remote OK API")
            await send_slack_message(f"⚠️ Remote OK: не получено вакансий из API")
            return []
        
        # Filter and process jobs
        for job_data in jobs_data:
            tags = job_data.get("tags", [])
            
            # Check if it's a dev job
            if not is_dev_job(tags):
                stats["filtered_out"] += 1
                continue
            
            stats["dev_jobs_found"] += 1
            
            # Map to model
            job_info = map_job_to_model(job_data)
            
            # Skip if no URL
            if not job_info["url"]:
                logger.warning(f"⚠️ Пропущена вакансия без URL: {job_info['title']}")
                continue
            
            # Check for duplicates
            existing = session.exec(
                select(Job).where(Job.url == job_info["url"])
            ).first()
            
            if existing:
                stats["duplicates_skipped"] += 1
                logger.debug(f"⏭️ Пропущен дубликат: {job_info['title']}")
                continue
            
            # Create and save job
            job = Job(
                title=job_info["title"],
                url=job_info["url"],
                description=job_info["description"],
                company=job_info["company"],
                company_url=job_info.get("company_url"),
                salary=job_info["salary"],
                source=SOURCE,
                parsed_at=job_info["parsed_at"],
            )
            
            session.add(job)
            all_jobs.append(job)
            stats["added_to_db"] += 1
            logger.info(f"✅ Сохранено: {job_info['title']} @ {job_info['company']}")
        
        # Commit all jobs
        session.commit()
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Send Slack report
        report = (
            f"📊 *Сводка по парсингу* {SOURCE}:\n"
            f"Всего получено из API: {stats['total_fetched']}\n"
            f"Dev-вакансий найдено: {stats['dev_jobs_found']}\n"
            f"Отфильтровано (не dev): {stats['filtered_out']}\n"
            f"Добавлено в БД: {stats['added_to_db']}\n"
            f"Пропущено дубликатов: {stats['duplicates_skipped']}\n"
            f"Время выполнения: {duration:.2f} сек"
        )
        await send_slack_message(report)
        
        logger.info(f"✅ Remote OK парсинг завершен. Добавлено {stats['added_to_db']} вакансий")
        
        return all_jobs
        
    except Exception as e:
        error_message = f"❌ Критическая ошибка при парсинге Remote OK: {str(e)}"
        logger.error(error_message)
        await send_slack_message(f"❌ Ошибка при парсинге {SOURCE}:\n{str(e)}")
        return []

