import asyncio
from bs4 import BeautifulSoup, ResultSet
from app.models import Job
from sqlmodel import select, Session
from datetime import datetime
from app.utils.browser import fetch_html_async
from app.logger import logger
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from playwright.async_api import async_playwright,  TimeoutError as PlaywrightTimeoutError
sem = asyncio.Semaphore(10)

URLS = [
    "https://thehub.io/jobs?roles=backenddeveloper&roles=engineer&roles=frontenddeveloper&roles=fullstackdeveloper&roles=mobiledevelopment&paid=true&countryCode=REMOTE&sorting=mostPopular"
]

SOURCE = "thehub.io"
base_url = "https://thehub.io"


async def process_page_throttled(url: str, browser):
    async with sem:
        return await process_page(url, browser)


def update_url_param(url: str, key: str, value: str) -> str:
    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.query)
    query_params[key] = [value]
    new_query = urlencode(query_params, doseq=True)
    return urlunparse(parsed_url._replace(query=new_query))


async def get_max_page(url: str, browser) -> int:
    page = await browser.new_page()
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_load_state("networkidle", timeout=10000)
        await page.wait_for_timeout(1000)
    except PlaywrightTimeoutError:
        logger.warning(f"⚠️ Timeout на {url}, пробуем найти пагинацию...")

    pagination = page.locator('ul[aria-label="Pagination"]')
    list_items = pagination.locator("li")
    count = await list_items.count()
    last_page = list_items.nth(count - 1)
    await last_page.click()
    await page.wait_for_url(lambda page_url: page_url != url, timeout=60000)

    updated_url = page.url
    await page.close()

    parsed = urlparse(updated_url)
    query_params = parse_qs(parsed.query)
    max_page_number = int(query_params.get("page", [1])[0])
    logger.info(f"📊 Найдено {max_page_number} страниц для {url}")
    return max_page_number


async def get_paginated_urls(url: str, browser) -> list[str]:
    max_page = await get_max_page(url, browser)
    return [update_url_param(url, "page", str(i + 1)) for i in range(max_page)]


async def process_job(job_div: ResultSet, browser) -> dict[str, str] | None:
    job_link_tag = job_div.find('a')
    if not job_link_tag:
        return None

    href = job_link_tag["href"].lstrip("/")
    job_url = f"{base_url}/{href}"

    job_page_html = await fetch_html_async(job_url, browser)
    soup = BeautifulSoup(job_page_html, "html.parser")
    content = soup.find('content')
    if not content:
        return None

    job_title_tag = content.find('h2')
    company_link_tag = job_title_tag.find_next("a") if job_title_tag else None

    job_title = job_title_tag.get_text(
        strip=True) if job_title_tag else "Untitled"
    company_href = company_link_tag['href'].lstrip(
        '/') if company_link_tag else "unknown"
    company = company_link_tag.get_text()

    description_content = content.find_next('content')
    description = description_content.get_text()
    company_url = f"{base_url}/{company_href}"

    return {
        "url": job_url,
        "title": job_title,
        "description": description,
        "company_url": company_url,
        "company": company
    }


async def process_page(url: str, browser) -> list[dict[str, str]]:
    page_html = await fetch_html_async(url, browser)
    soup = BeautifulSoup(page_html, "html.parser")
    content_tags = soup.find_all('content')
    if not content_tags:
        return []

    jobs_content = content_tags[-1]
    job_rows = jobs_content.find_all('div', recursive=False)

    return await asyncio.gather(*[
        process_job(job_row, browser)
        for job_row in job_rows
    ])


async def scrape_thehub_jobs(session: Session):
    all_jobs = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        urls_nested = await asyncio.gather(*[
            get_paginated_urls(url, browser) for url in URLS
        ])
        urls = [u for group in urls_nested for u in group]

        all_results = await asyncio.gather(*[
            process_page_throttled(url, browser) for url in urls
        ])
        flat_results = [job for group in all_results for job in group if job]

        for job_info in flat_results:
            existing = session.exec(
                select(Job).where(Job.url == job_info["url"])).first()
            if not existing:
                job = Job(
                    title=job_info["title"],
                    url=job_info["url"],
                    description=job_info["description"],
                    source=SOURCE,
                    parsed_at=datetime.utcnow(),
                    company_url=job_info["company_url"],
                    company=job_info["company"]
                )
                session.add(job)
                all_jobs.append(job)
                logger.info(f"✅ Сохранено: {job_info['title']}")
            else:
                logger.info(f"⚠️ Пропущено (дубликат): {existing.title}")

        session.commit()
        await browser.close()

    return all_jobs
