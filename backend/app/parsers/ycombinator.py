"""
Y Combinator Jobs Parser
Fetches jobs from RapidAPI active-jobs-db and filters for software development positions.
"""

import httpx
import time
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlmodel import Session, select
from app.models import Job
from app.logger import logger
from app.utils.slack import send_slack_message
from app.config import settings


# API configuration
API_URL = "https://free-y-combinator-jobs-api.p.rapidapi.com/active-jb-7d"
API_HOST = "free-y-combinator-jobs-api.p.rapidapi.com"
SOURCE = "ycombinator"

# Keywords that indicate software development positions
DEV_KEYWORDS = {
    # Core dev roles
    'developer', 'engineer', 'programmer', 'software',
    'frontend', 'front-end', 'front end',
    'backend', 'back-end', 'back end',
    'fullstack', 'full-stack', 'full stack',
    'sre', 'site reliability',
    # Technologies
    'react', 'vue', 'angular', 'javascript', 'typescript',
    'python', 'java', 'golang', 'go ', 'rust', 'node', 'nodejs',
    'ios', 'android', 'mobile',
    'devops', 'devsecops', 'platform engineer',
    'php', 'ruby', 'rails', 'django', 'flask', 'spring',
    'kubernetes', 'k8s', 'docker', 'terraform', 'aws', 'cloud',
    'data engineer', 'ml engineer', 'machine learning', 'ai engineer',
    'c++', 'c#', '.net', 'dotnet', 'scala', 'kotlin', 'swift',
    # Specific roles
    'web developer', 'api developer', 'systems engineer',
    'embedded', 'firmware', 'linux', 'unix',
}


def is_dev_job(title: str, description: str = "") -> bool:
    """
    Check if job is a software development position based on title and description.
    Returns True if title or description contains any dev-related keyword.
    """
    if not title:
        return False
    
    # Combine title and description for checking
    text_lower = f"{title} {description or ''}".lower()
    
    # Check for dev-related keywords
    for keyword in DEV_KEYWORDS:
        if keyword in text_lower:
            return True
    
    return False


def parse_salary(salary_raw: Optional[str]) -> Optional[str]:
    """
    Parse salary information from raw JSON string.
    Example: '{"@type":"MonetaryAmount","currency":"USD","value":{"@type":"QuantitativeValue","minValue":72000,"maxValue":77000,"unitText":"YEAR"}}'
    """
    if not salary_raw:
        return None
    
    try:
        salary_data = json.loads(salary_raw)
        value = salary_data.get("value", {})
        currency = salary_data.get("currency", "USD")
        min_val = value.get("minValue")
        max_val = value.get("maxValue")
        unit = value.get("unitText", "YEAR")
        
        if min_val and max_val:
            return f"{currency} {min_val:,} - {max_val:,} / {unit}"
        elif min_val:
            return f"{currency} {min_val:,}+ / {unit}"
        elif max_val:
            return f"Up to {currency} {max_val:,} / {unit}"
    except (json.JSONDecodeError, TypeError, KeyError):
        pass
    
    return None


def format_location(job_data: Dict[str, Any]) -> Optional[str]:
    """
    Extract and format location from job data.
    """
    locations = job_data.get("locations_derived", [])
    if locations:
        return ", ".join(locations[:2])  # Take first 2 locations
    return None


async def fetch_jobs_from_api() -> List[Dict[str, Any]]:
    """
    Fetch jobs from RapidAPI Y Combinator jobs API.
    Returns list of job dictionaries.
    """
    if not settings.RAPID_YCOMB_API_KEY:
        logger.error("❌ RAPID_YCOMB_API_KEY не настроен")
        return []
    
    headers = {
        "x-rapidapi-key": settings.RAPID_YCOMB_API_KEY,
        "x-rapidapi-host": API_HOST,
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(API_URL, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    logger.info(f"📊 Получено {len(data)} вакансий из Y Combinator API")
                    return data
                else:
                    logger.warning(f"⚠️ Неожиданный формат ответа от API: {type(data)}")
                    return []
            else:
                logger.error(f"❌ Ошибка API: {response.status_code} - {response.text[:200]}")
                return []
                
    except Exception as e:
        logger.error(f"❌ Ошибка при запросе к API: {str(e)}")
        return []


async def fetch_all_jobs() -> List[Dict[str, Any]]:
    """
    Fetch all jobs from Y Combinator API.
    Returns list of jobs.
    """
    jobs = await fetch_jobs_from_api()
    logger.info(f"📊 Всего получено вакансий: {len(jobs)}")
    return jobs


def map_job_to_model(job_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Map RapidAPI job data to Job model fields.
    """
    # Parse date
    parsed_at = datetime.utcnow()
    date_posted = job_data.get("date_posted")
    if date_posted:
        try:
            parsed_at = datetime.fromisoformat(date_posted.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            pass
    
    # Build location string
    location = format_location(job_data)
    
    # Check if remote
    is_remote = job_data.get("remote_derived", False)
    if is_remote:
        location = f"Remote{', ' + location if location else ''}"
    
    return {
        "title": job_data.get("title", "Unknown Position"),
        "url": job_data.get("url", ""),
        "description": location or "",  # Use location as brief description
        "company": job_data.get("organization", "Unknown Company"),
        "company_url": job_data.get("organization_url"),
        "salary": parse_salary(job_data.get("salary_raw")),
        "source": SOURCE,
        "parsed_at": parsed_at,
    }


async def scrape_ycombinator_jobs(session: Session) -> List[Job]:
    """
    Main function to scrape Y Combinator jobs from RapidAPI.
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
        # Fetch all jobs from API
        jobs_data = await fetch_all_jobs()
        stats["total_fetched"] = len(jobs_data)
        
        if not jobs_data:
            logger.warning("⚠️ Не получено вакансий из Y Combinator API")
            await send_slack_message(f"⚠️ {SOURCE}: не получено вакансий из API")
            return []
        
        # Filter and process jobs
        for job_data in jobs_data:
            title = job_data.get("title", "")
            
            # Check if it's a dev job
            if not is_dev_job(title):
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
            f"📊 *Сводка по парсингу {SOURCE}*:\n"
            f"Всего найдено вакансий: {stats['dev_jobs_found']}\n"
            f"Добавлено в БД: {stats['added_to_db']}\n"
            f"Пропущено дубликатов: {stats['duplicates_skipped']}\n"
            f"Время выполнения: {duration:.2f} секунд"
        )
        await send_slack_message(report)
        
        logger.info(f"✅ Парсинг {SOURCE} завершен. Добавлено {stats['added_to_db']} вакансий")
        
        return all_jobs
        
    except Exception as e:
        error_message = f"❌ Критическая ошибка при парсинге {SOURCE}: {str(e)}"
        logger.error(error_message)
        await send_slack_message(f"❌ Ошибка при парсинге {SOURCE}:\n{str(e)}")
        return []

