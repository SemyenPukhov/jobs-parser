"""
Active Jobs DB Parser
Fetches remote developer/engineer jobs from RapidAPI Active Jobs DB.
Uses API-level filtering for date, remote status, and job titles.
"""

import httpx
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from sqlmodel import Session, select
from app.models import Job
from app.logger import logger
from app.utils.slack import send_slack_message
from app.config import settings


# API configuration
API_URL = "https://active-jobs-db.p.rapidapi.com/active-ats-7d"
API_HOST = "active-jobs-db.p.rapidapi.com"
SOURCE = "activejobs_db"

# API query parameters
LIMIT = 10  # Free plan limit
TITLE_FILTER = '"developer" OR "engineer" OR "programmer" OR "software"'


def get_yesterday_date() -> str:
    """
    Calculate yesterday's date in YYYY-MM-DD format for date_filter.
    The API uses this as a "greater than" filter.
    """
    yesterday = datetime.utcnow() - timedelta(days=1)
    return yesterday.strftime("%Y-%m-%d")


def parse_salary(salary_data: Any) -> Optional[str]:
    """
    Parse salary information from API response.
    """
    if not salary_data:
        return None
    
    try:
        if isinstance(salary_data, str):
            return salary_data
        elif isinstance(salary_data, dict):
            min_val = salary_data.get("min") or salary_data.get("minValue")
            max_val = salary_data.get("max") or salary_data.get("maxValue")
            currency = salary_data.get("currency", "USD")
            period = salary_data.get("period", "year")
            
            if min_val and max_val:
                return f"{currency} {min_val:,} - {max_val:,} / {period}"
            elif min_val:
                return f"{currency} {min_val:,}+ / {period}"
            elif max_val:
                return f"Up to {currency} {max_val:,} / {period}"
    except Exception:
        pass
    
    return None


def format_location(job_data: Dict[str, Any]) -> Optional[str]:
    """
    Extract and format location from job data.
    """
    location = job_data.get("location")
    if location:
        if isinstance(location, list):
            return ", ".join(location[:2])
        return str(location)
    
    # Fallback to other location fields
    city = job_data.get("city")
    country = job_data.get("country")
    if city or country:
        parts = [p for p in [city, country] if p]
        return ", ".join(parts)
    
    return None


async def fetch_jobs_from_api() -> List[Dict[str, Any]]:
    """
    Fetch jobs from RapidAPI Active Jobs DB with filtering.
    Uses date_filter, title_filter and limit parameters.
    Returns list of job dictionaries.
    """
    if not settings.RAPID_ACTIVEJOBS_API_KEY:
        logger.error("❌ RAPID_ACTIVEJOBS_API_KEY not configured")
        return []
    
    yesterday = get_yesterday_date()
    
    params = {
        "limit": LIMIT,
        "offset": 0,
        "date_filter": yesterday,
        "title_filter": TITLE_FILTER,
        "description_type": "text",
    }
    
    logger.info(f"📡 API request: {API_URL}")
    logger.info(f"📡 Parameters: limit={LIMIT}, date_filter={yesterday}, title_filter={TITLE_FILTER}")
    
    headers = {
        "x-rapidapi-key": settings.RAPID_ACTIVEJOBS_API_KEY,
        "x-rapidapi-host": API_HOST,
    }
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(API_URL, headers=headers, params=params)
            
            logger.info(f"📡 API response: status={response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    logger.info(f"📊 Received {len(data)} jobs from Active Jobs DB API")
                    return data
                elif isinstance(data, dict):
                    # Some APIs wrap results in a dict
                    jobs = data.get("jobs", data.get("data", data.get("results", [])))
                    if isinstance(jobs, list):
                        logger.info(f"📊 Received {len(jobs)} jobs from Active Jobs DB API (from dict)")
                        return jobs
                    logger.warning("⚠️ Unexpected API response format: dict without jobs list")
                    return []
                else:
                    logger.warning(f"⚠️ Unexpected API response format: {type(data)}")
                    return []
            else:
                logger.error(f"❌ API error: {response.status_code} - {response.text[:500]}")
                return []
                
    except Exception as e:
        logger.error(f"❌ Error during API request: {str(e)}")
        return []


def map_job_to_model(job_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Map Active Jobs DB API response to Job model fields.
    """
    # Parse date
    parsed_at = datetime.utcnow()
    date_posted = job_data.get("date_posted") or job_data.get("posted_at") or job_data.get("datePosted")
    if date_posted:
        try:
            if isinstance(date_posted, str):
                # Handle various date formats
                for fmt in ["%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"]:
                    try:
                        parsed_at = datetime.strptime(date_posted.replace("Z", ""), fmt.replace("Z", ""))
                        break
                    except ValueError:
                        continue
        except Exception:
            pass
    
    # Build location string
    location = format_location(job_data)
    
    # Add remote indicator if present
    is_remote = job_data.get("remote", False) or job_data.get("is_remote", False)
    if is_remote and location:
        location = f"Remote, {location}"
    elif is_remote:
        location = "Remote"
    
    # Get job URL
    url = job_data.get("url") or job_data.get("job_url") or job_data.get("apply_url") or ""
    
    # Get company info
    company = job_data.get("company") or job_data.get("organization") or job_data.get("employer") or "Unknown Company"
    company_url = job_data.get("company_url") or job_data.get("organization_url") or job_data.get("employer_url")
    
    # Get description
    description = job_data.get("description") or location or ""
    # Truncate long descriptions
    if len(description) > 500:
        description = description[:500] + "..."
    
    return {
        "title": job_data.get("title", "Unknown Position"),
        "url": url,
        "description": description,
        "company": company,
        "company_url": company_url,
        "apply_url": job_data.get("apply_url"),
        "salary": parse_salary(job_data.get("salary") or job_data.get("salary_raw")),
        "source": SOURCE,
        "parsed_at": parsed_at,
    }


async def scrape_activejobs_db(session: Session) -> List[Job]:
    """
    Main function to scrape Active Jobs DB from RapidAPI.
    Fetches from API (filtering done at API level) and saves to database.
    """
    all_jobs = []
    start_time = time.time()
    
    # Statistics for report
    stats = {
        "total_fetched": 0,
        "added_to_db": 0,
        "duplicates_skipped": 0,
    }
    
    try:
        # Fetch jobs from API (already filtered by API)
        jobs_data = await fetch_jobs_from_api()
        stats["total_fetched"] = len(jobs_data)
        
        if not jobs_data:
            logger.warning("⚠️ No jobs received from Active Jobs DB API")
            await send_slack_message(f"⚠️ {SOURCE}: no jobs received from API")
            return []
        
        # Process jobs
        for job_data in jobs_data:
            # Map to model
            job_info = map_job_to_model(job_data)
            
            # Skip if no URL
            if not job_info["url"]:
                logger.warning(f"⚠️ Skipping job without URL: {job_info['title']}")
                continue
            
            # Check for duplicates
            existing = session.exec(
                select(Job).where(Job.url == job_info["url"])
            ).first()
            
            if existing:
                stats["duplicates_skipped"] += 1
                logger.debug(f"⏭️ Skipping duplicate: {job_info['title']}")
                continue
            
            # Create and save job
            job = Job(
                title=job_info["title"],
                url=job_info["url"],
                description=job_info["description"],
                company=job_info["company"],
                company_url=job_info.get("company_url"),
                apply_url=job_info.get("apply_url"),
                salary=job_info["salary"],
                source=SOURCE,
                parsed_at=job_info["parsed_at"],
            )
            
            session.add(job)
            all_jobs.append(job)
            stats["added_to_db"] += 1
            logger.info(f"✅ Saved: {job_info['title']} @ {job_info['company']}")
        
        # Commit all jobs
        session.commit()
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Send Slack report
        report = (
            f"📊 *Active Jobs DB parsing summary*:\n"
            f"Total jobs from API: {stats['total_fetched']}\n"
            f"Added to DB: {stats['added_to_db']}\n"
            f"Duplicates skipped: {stats['duplicates_skipped']}\n"
            f"Execution time: {duration:.2f} seconds"
        )
        await send_slack_message(report)
        
        logger.info(f"✅ {SOURCE} parsing completed. Added {stats['added_to_db']} jobs")
        
        return all_jobs
        
    except Exception as e:
        error_message = f"❌ Critical error during {SOURCE} parsing: {str(e)}"
        logger.error(error_message)
        await send_slack_message(f"❌ Error during {SOURCE} parsing:\n{str(e)}")
        return []

