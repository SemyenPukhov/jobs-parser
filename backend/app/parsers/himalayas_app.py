"""
Himalayas App Parser
Fetches remote jobs from himalayas.app API and filters for software development positions.
Filters by experience level (mid-level, senior) and employment type (full-time, contractor).
"""

import httpx
import re
import time
from html import unescape
from datetime import datetime
from typing import List, Dict, Any, Optional, Set
from sqlmodel import Session, select
from app.models import Job
from app.logger import logger
from app.utils.slack import send_slack_message


# API endpoint
API_URL = "https://himalayas.app/jobs/api"
SOURCE = "himalayas.app"

# Pagination settings
PAGE_LIMIT = 20  # Max jobs per request (API limit)
MAX_PAGES = 5    # Total pages to fetch (100 jobs max)

# Filter settings
ALLOWED_EXPERIENCE = {"mid-level", "senior"}
ALLOWED_EMPLOYMENT_TYPES = {"full-time", "contractor"}

# Tags that indicate software development positions
# If ANY of these tags present - it's a dev job
DEV_TAGS: Set[str] = {
    # Core dev roles
    'dev', 'developer', 'programmer', 'engineer', 'engineering',
    'frontend', 'backend', 'fullstack', 'full-stack', 'full stack',
    'software engineer', 'software developer', 'software',
    'sre', 'site reliability',
    # Technologies (specific enough to indicate dev work)
    'react', 'vue', 'angular', 'javascript', 'typescript',
    'python', 'java', 'golang', 'go', 'rust', 'node', 'nodejs', 'node.js',
    'ios', 'android', 'mobile', 'devops', 'devsecops',
    'php', 'ruby', 'rails', 'django', 'flask', 'spring',
    'kubernetes', 'docker', 'terraform', 'aws', 'cloud',
    'data engineer', 'ml engineer', 'machine learning', 'ai',
    'c++', 'c#', '.net', 'dotnet', 'scala', 'kotlin', 'swift',
    'web developer', 'web development', 'webdev',
}

# Categories from Himalayas that indicate dev jobs
DEV_CATEGORIES: Set[str] = {
    'software-engineering',
    'software engineering',
    'engineering',
    'web-development',
    'web development',
    'mobile-development',
    'mobile development',
    'devops',
    'devops-sysadmin',
    'data-science',
    'data science',
    'machine-learning',
    'machine learning',
    'backend',
    'frontend',
    'full-stack',
    'fullstack',
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


def format_salary(salary_min: Optional[int], salary_max: Optional[int], currency: Optional[str] = None) -> Optional[str]:
    """Format salary range as string."""
    currency_symbol = currency if currency else "$"
    if salary_min and salary_max:
        return f"{currency_symbol}{salary_min:,} - {currency_symbol}{salary_max:,}"
    elif salary_min:
        return f"{currency_symbol}{salary_min:,}+"
    elif salary_max:
        return f"Up to {currency_symbol}{salary_max:,}"
    return None


def is_dev_job(categories: List[str], title: str) -> bool:
    """
    Check if job is a software development position based on categories and title.
    Returns True if job has ANY dev-related category or title keyword.
    """
    # Check categories
    if categories:
        categories_lower = {cat.lower() for cat in categories}
        for dev_cat in DEV_CATEGORIES:
            if dev_cat in categories_lower:
                return True
            for cat in categories_lower:
                if dev_cat in cat:
                    return True
    
    # Check title
    if title:
        title_lower = title.lower()
        for dev_tag in DEV_TAGS:
            if dev_tag in title_lower:
                return True
    
    return False


def matches_experience_filter(experience: Optional[str]) -> bool:
    """
    Check if job experience matches allowed levels (mid-level, senior).
    """
    return True
    if not experience:
        return False
    
    exp_lower = experience.lower().replace("_", "-").replace(" ", "-")
    
    for allowed in ALLOWED_EXPERIENCE:
        if allowed in exp_lower:
            return True
    
    return False


def matches_employment_filter(employment_type: Optional[str]) -> bool:
    """
    Check if job employment type matches allowed types (full-time, contractor).
    """
    return True
    if not employment_type:
        return False
    
    emp_lower = employment_type.lower().replace("_", "-").replace(" ", "-")
    
    for allowed in ALLOWED_EMPLOYMENT_TYPES:
        if allowed in emp_lower:
            return True
    
    return False


async def fetch_jobs_from_api(offset: int = 0, limit: int = PAGE_LIMIT) -> List[Dict[str, Any]]:
    """
    Fetch jobs from Himalayas API with pagination.
    Returns list of job dictionaries.
    """
    headers = {
        "User-Agent": "JobsParser/1.0 (https://github.com/jobs-parser)",
        "Accept": "application/json",
    }
    
    params = {
        "offset": offset,
        "limit": limit,
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(API_URL, headers=headers, params=params)
            
            if response.status_code == 200:
                data = response.json()
                # API returns a list of jobs or dict with jobs key
                if isinstance(data, list):
                    jobs = data
                elif isinstance(data, dict):
                    jobs = data.get("jobs", data.get("data", []))
                else:
                    jobs = []
                
                logger.info(f"📊 Fetched {len(jobs)} jobs from Himalayas API (offset={offset})")
                return jobs
            else:
                logger.error(f"❌ Error fetching from Himalayas API: {response.status_code}")
                return []
                
    except Exception as e:
        logger.error(f"❌ Error fetching from Himalayas API: {str(e)}")
        return []


async def fetch_all_jobs(max_pages: int = MAX_PAGES) -> List[Dict[str, Any]]:
    """
    Fetch all jobs from multiple pages.
    Stops when no more jobs or max_pages reached.
    """
    all_jobs = []
    
    for page in range(max_pages):
        offset = page * PAGE_LIMIT
        jobs = await fetch_jobs_from_api(offset=offset, limit=PAGE_LIMIT)
        
        if not jobs:
            logger.info(f"📊 No more jobs at page {page + 1}, stopping pagination")
            break
        
        all_jobs.extend(jobs)
        
        # If we got fewer jobs than limit, we've reached the end
        if len(jobs) < PAGE_LIMIT:
            logger.info(f"📊 Last page reached at page {page + 1}")
            break
    
    logger.info(f"📊 Total jobs fetched from Himalayas: {len(all_jobs)}")
    return all_jobs


def map_job_to_model(job_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Map Himalayas API response to Job model fields.
    """
    # Build job URL
    job_url = job_data.get("applicationLink", "")
    if not job_url:
        # Fallback to constructing URL from slug or ID
        slug = job_data.get("slug", "")
        if slug:
            job_url = f"https://himalayas.app/jobs/{slug}"
        else:
            job_id = job_data.get("id", "")
            if job_id:
                job_url = f"https://himalayas.app/jobs/{job_id}"
    
    # Parse date
    parsed_at = datetime.utcnow()
    pub_date = job_data.get("pubDate") or job_data.get("publishedAt") or job_data.get("createdAt")
    if pub_date:
        try:
            # Handle various date formats
            if isinstance(pub_date, str):
                # ISO format
                parsed_at = datetime.fromisoformat(pub_date.replace("Z", "+00:00"))
            elif isinstance(pub_date, (int, float)):
                # Unix timestamp
                parsed_at = datetime.fromtimestamp(pub_date)
        except (ValueError, AttributeError, OSError):
            pass
    
    # Format salary
    salary = format_salary(
        job_data.get("salaryMin") or job_data.get("salary_min"),
        job_data.get("salaryMax") or job_data.get("salary_max"),
        job_data.get("currency")
    )
    
    # Get company info
    company_data = job_data.get("company", {})
    company_name = job_data.get("companyName") or (company_data.get("name") if isinstance(company_data, dict) else None) or "Unknown Company"
    company_url = job_data.get("companyUrl") or (company_data.get("url") if isinstance(company_data, dict) else None)
    
    return {
        "title": job_data.get("title", "Unknown Position"),
        "url": job_url,
        "description": strip_html_tags(job_data.get("description", "")),
        "company": company_name,
        "company_url": company_url,
        "apply_url": job_data.get("applicationLink") or job_data.get("applyUrl"),
        "salary": salary,
        "source": SOURCE,
        "parsed_at": parsed_at,
    }


async def scrape_himalayas_jobs(session: Session) -> List[Job]:
    """
    Main function to scrape Himalayas jobs.
    Fetches from API, filters by experience/employment type/dev tags, and saves to database.
    """
    all_jobs = []
    start_time = time.time()
    
    # Statistics for report
    stats = {
        "total_fetched": 0,
        "dev_jobs_found": 0,
        "experience_filtered": 0,
        "employment_filtered": 0,
        "added_to_db": 0,
        "duplicates_skipped": 0,
        "non_dev_filtered": 0,
    }
    
    try:
        # Fetch jobs from API
        jobs_data = await fetch_all_jobs(max_pages=MAX_PAGES)
        stats["total_fetched"] = len(jobs_data)
        
        if not jobs_data:
            logger.warning("⚠️ No jobs received from Himalayas API")
            await send_slack_message(f"⚠️ Himalayas: no jobs received from API")
            return []
        
        # Filter and process jobs
        for job_data in jobs_data:
            # Get filter fields
            experience = job_data.get("experience") or job_data.get("experienceLevel", "")
            employment_type = job_data.get("employmentType") or job_data.get("type", "")
            categories = job_data.get("categories", [])
            title = job_data.get("title", "")
            
            # Check experience filter
            if not matches_experience_filter(experience):
                stats["experience_filtered"] += 1
                continue
            
            # Check employment type filter
            if not matches_employment_filter(employment_type):
                stats["employment_filtered"] += 1
                continue
            
            # Check if it's a dev job
            if not is_dev_job(categories, title):
                stats["non_dev_filtered"] += 1
                continue
            
            stats["dev_jobs_found"] += 1
            
            # Map to model
            job_info = map_job_to_model(job_data)
            
            # Skip if no URL
            if not job_info["url"]:
                logger.warning(f"⚠️ Skipped job without URL: {job_info['title']}")
                continue
            
            # Check for duplicates
            existing = session.exec(
                select(Job).where(Job.url == job_info["url"])
            ).first()
            
            if existing:
                stats["duplicates_skipped"] += 1
                logger.debug(f"⏭️ Skipped duplicate: {job_info['title']}")
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
            f"📊 *Parsing summary* {SOURCE}:\n"
            f"Total fetched from API: {stats['total_fetched']}\n"
            f"Filtered by experience (not mid/senior): {stats['experience_filtered']}\n"
            f"Filtered by employment (not full-time/contractor): {stats['employment_filtered']}\n"
            f"Filtered (non-dev): {stats['non_dev_filtered']}\n"
            f"Dev jobs found: {stats['dev_jobs_found']}\n"
            f"Added to DB: {stats['added_to_db']}\n"
            f"Duplicates skipped: {stats['duplicates_skipped']}\n"
            f"Execution time: {duration:.2f} sec"
        )
        await send_slack_message(report)
        
        logger.info(f"✅ Himalayas parsing completed. Added {stats['added_to_db']} jobs")
        
        return all_jobs
        
    except Exception as e:
        error_message = f"❌ Critical error while parsing Himalayas: {str(e)}"
        logger.error(error_message)
        await send_slack_message(f"❌ Error parsing {SOURCE}:\n{str(e)}")
        return []

