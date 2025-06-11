import asyncio
from bs4 import BeautifulSoup, ResultSet
from app.models import Job
from sqlmodel import select, Session
from datetime import datetime, timedelta
from app.utils.browser import fetch_html_browser, get_browser_page, fetch_html_async
from typing import Any, Dict, List, Optional
from app.logger import logger
from functools import lru_cache
from playwright.async_api import async_playwright,  TimeoutError as PlaywrightTimeoutError

import time

sem = asyncio.Semaphore(10)

URLS = [
    "https://www.vseti.app/jobs?jobstype=%D0%A0%D0%B0%D0%B7%D1%80%D0%B0%D0%B1%D0%BE%D1%82%D0%BA%D0%B0&level=Middle%2CSenior&location=%D0%94%D1%80%D1%83%D0%B3%D0%BE%D0%B5%2C%D0%97%D0%B0+%D1%80%D1%83%D0%B1%D0%B5%D0%B6%D0%BE%D0%BC&format=%D0%A3%D0%B4%D0%B0%D0%BB%D1%91%D0%BD%D0%BD%D0%BE"
]
SOURCE = "vseti.app"


async def process_page_throttled(job: Dict[str, str], browser):
    async with sem:
        return await get_job_details(job, browser)


async def get_full_jobs_page(url: str):
    max_pages = 10
    page_num = 0

    async with get_browser_page(url) as page:
        while page_num < max_pages:
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            next_page_link = page.locator('a[aria-label="Next Page"]')

            if not await next_page_link.is_visible():
                logger.info(
                    f"📊 Кнопки 'Next Page' больше нет. Отдаю контент. Пройдено страниц: {page_num}")
                break

            logger.info(
                f"📊 Нашел кнопку 'Next Page'. Жму (страница {page_num + 1})")
            await next_page_link.click()

            try:
                await page.wait_for_load_state("networkidle", timeout=10000)
            except Exception as e:
                logger.warning(
                    f"⚠️ Загрузка не завершилась по networkidle: {e}. Жду ещё 5 секунд...")
                await page.wait_for_timeout(5000)

            page_num += 1
        return await page.content()


async def get_job_details(job: Dict[str, str], browser):
    html = await fetch_html_async(job["href"], browser)
    soup = BeautifulSoup(html, "html.parser")
    description_div = soup.find('div', class_="content_vacancy_div")
    job_description = description_div.get_text(
    ) if description_div is not None else "Не найдено"
    company_link_tag = soup.find("a", string="Подробнее о компании")
    company_url = company_link_tag['href']

    return {"url": job["href"],
            "title": job["title"],
            "description": job_description,
            "company_url": company_url,
            "company": job["company"]}


async def get_job_links_from_page(html: str) -> Optional[List[Dict[str, str]]]:
    try:
        soup = BeautifulSoup(html, "html.parser")
        links = soup.find_all("a", class_="card-jobs")
        job_links = []

        for job_link in links:
            try:
                title_div = job_link.find('div', class_='company-titile')
                company_p = title_div.find('p')
                company = company_p.get_text(strip=True)
                job_title_tag = job_link.find('h1')
                job_title = job_title_tag.get_text(strip=True)
                job_href = job_link['href']
                job_details = {
                    "title": job_title,
                    "company": company,
                    "href": job_href
                }
                job_links.append(job_details)
            except Exception as e:
                continue  # пропускаем сломанные элементы, но не всю страницу

        return job_links
    except Exception as e:
        return None


async def scrape_vseti_app_jobs(session: Session):
    """Основная функция скрапинга"""
    start_time = time.time()
    all_jobs = []

    try:
        tasks = [get_full_jobs_page(
            url) for url in URLS]
        html_pages = await asyncio.gather(*tasks, return_exceptions=True)

        job_links_task = [get_job_links_from_page(
            html) for html in html_pages]
        jobs_nested = await asyncio.gather(*job_links_task, return_exceptions=True)
        jobs = [job for sublist in jobs_nested if not isinstance(
            sublist, Exception) for job in sublist]

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)

            all_results = await asyncio.gather(*[
                process_page_throttled(job, browser) for job in jobs
            ])
            await browser.close()

        for job_info in all_results:
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

        if all_jobs:
            session.commit()

        end_time = time.time()
        logger.info(
            f"✅ Скрапинг завершен за {end_time - start_time:.2f} секунд. Добавлено {len(all_jobs)} вакансий")

        return all_jobs
    except Exception as e:
        logger.error(f"❌ Критическая ошибка при скрапинге: {str(e)}")
        return []
