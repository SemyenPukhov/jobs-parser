import asyncio
from bs4 import BeautifulSoup, ResultSet
from app.models import Job
from sqlmodel import select, Session
from datetime import datetime
from app.utils.browser import fetch_html_browser
from typing import Any
from app.logger import logger
sem = asyncio.Semaphore(10)

URLS = [
    "https://startup.jobs/?remote=true&since=24h&q=%22React%22",
    "https://startup.jobs/?remote=true&since=24h&q=%22Node%22",
    "https://startup.jobs/?remote=true&since=24h&q=%22Angular%22",
    "https://startup.jobs/?remote=true&since=24h&q=javascript",
    "https://startup.jobs/?remote=true&since=24h&q=web+developer",
    "https://startup.jobs/?remote=true&since=24h&q=python",
]
SOURCE = "startup.jobs"
base_url = "https://startup.jobs"


async def process_job_div_throttled(job_div):
    async with sem:
        return await process_job_div(job_div)


def find_apply_link(s: BeautifulSoup):
    for a in s.find_all("a"):
        if "Apply for this job" in a.get_text(strip=True):
            return f"{base_url}/{a["href"].lstrip("/")}"
    return None


async def get_job_description(url: str) -> str:
    job_html = await fetch_html_browser(url)
    soup = BeautifulSoup(job_html, "html.parser")
    desc_div = soup.find("div", class_=["trix-content"])
    apply_url = find_apply_link(soup)
    logger.info(f"📊 Ищу описание вакансии {url}")

    return {
        "description": desc_div.get_text(),
        "apply_url": apply_url
    }


async def process_job_div(job_div: ResultSet[Any]):
    link_tag = job_div.find(
        "a", attrs={"data-mark-visited-links-target": "anchor"})
    href = link_tag["href"].lstrip("/")
    full_job_url = f"{base_url}/{href}"
    company_link_tag = link_tag.find_next("a")
    company_href = company_link_tag["href"].lstrip("/")
    company_url = f"{base_url}/{company_href}"
    company_name = company_link_tag.get_text()
    job_title = " ".join(line.strip() for line in link_tag.get_text(
    ).strip().splitlines() if line.strip())

    description, apply_url = (await get_job_description(full_job_url)).values()

    return {
        "url": full_job_url,
        "company_url": company_url,
        "company_name": company_name,
        "title": job_title,
        "description": description,
        "apply_url": apply_url
    }


async def parse_jobs_from_html(html: str) -> None:
    soup = BeautifulSoup(html, "html.parser")

    hits_div = soup.find("div", attrs={"data-search-target": "hits"})

    job_rows = hits_div.find_all("div", class_="isolate")
    logger.info(f"📊 Найдено {len(job_rows)} вакансий")

    parsed_jobs = await asyncio.gather(
        *[process_job_div_throttled(job) for job in job_rows]
    )

    jobs = []

    for job in parsed_jobs:
        job_data = Job(
            title=job["title"],
            url=job["url"],
            source=SOURCE,
            description=job["description"],
            company=job["company_name"],
            company_url=job["company_url"],
            parsed_at=datetime.utcnow(),
            apply_url=job["apply_url"]
        )
        jobs.append(job_data)

    return jobs


async def scrape_startup_jobs(session: Session):
    all_jobs = []

    tasks = [fetch_html_browser(url) for url in URLS]
    html_results = await asyncio.gather(*tasks)

    for html in html_results:
        jobs = await parse_jobs_from_html(html)
        for job in jobs:
            existing = session.exec(
                select(Job).where(Job.url == job.url)).first()

            if not existing:
                logger.info(f"📊 Сохраняю в БД {job["url"]}")
                session.add(job)
                all_jobs.append(job)
            else:
                logger.info(
                    f"⚠️ Не сохраняю. Дубликат {existing.model_dump()}")

    session.commit()
    return all_jobs
