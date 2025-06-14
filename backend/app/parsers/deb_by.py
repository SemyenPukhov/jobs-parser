import asyncio
from bs4 import BeautifulSoup, ResultSet
from app.models import Job
from sqlmodel import select, Session
from datetime import datetime, timedelta
from app.utils.browser import fetch_html_async
from typing import Any, Dict, List
from app.logger import logger
from app.utils.slack import send_slack_message
from functools import lru_cache
import time
import uuid
from playwright.async_api import async_playwright,  TimeoutError as PlaywrightTimeoutError


# Уменьшаем количество одновременных запросов
# sem = asyncio.Semaphore(3)

# # Кэш для хранения результатов парсинга на 1 час
# CACHE_TTL = timedelta(hours=1)
# parsed_urls_cache: Dict[str, tuple[datetime, Dict]] = {}


URLS = [
    "https://jobs.devby.io/?filter[specialization_title]=Front-end/JS&filter[job_types][]=remote_job",
    "https://jobs.devby.io/?filter[job_types][]=remote_job&filter[search]=angular",
    "https://jobs.devby.io/?filter[job_types][]=remote_job&filter[search]=node.js",
    "https://jobs.devby.io/?filter[job_types][]=remote_job&filter[search]=javascript",
    "https://jobs.devby.io/?filter[job_types][]=remote_job&filter[search]=typescript",

]
SOURCE = "jobs.devby.io"
base_url = "https://jobs.devby.io"


def remove_duplicate_jobs(jobs_info):
    """Удаляет дубликаты вакансий по job_link"""
    unique_jobs = []
    seen_urls = set()

    for result in jobs_info:
        if isinstance(result, Exception) or result is None:
            continue

        for job in result:
            job_url = job.get('job_link', '')
            if job_url and job_url not in seen_urls:
                seen_urls.add(job_url)
                unique_jobs.append(job)

    return unique_jobs


async def get_job_detail(job: Dict[str, Any], browser):
    page_html = await fetch_html_async(job["job_link"], browser)
    soup = BeautifulSoup(page_html, "html.parser")
    job_description_div = soup.find("div", class_="vacancy__text")
    job_description = job_description_div.get_text()
    company_link_tag = soup.find("a", string="Профиль компании")
    company_link = company_link_tag["href"]
    job["company_link"] = company_link
    job["job_description"] = job_description
    print(31324123412, job_description, company_link)

    return job


async def get_jobs_details_from_page(url: str, browser):
    jobs = []
    page_html = await fetch_html_async(url, browser)
    soup = BeautifulSoup(page_html, "html.parser")
    jobs_divs = soup.find_all('div', class_='vacancies-list-item')
    if len(jobs_divs) == 1:
        logger.info('📊 Не найдено запросов для', url)
        return None
    for job_div in jobs_divs[:-1]:
        job_link_tag = job_div.find("a")
        href = job_link_tag["href"]
        job_title = job_link_tag.get_text()
        company_div = job_div.find(
            'div', class_='vacancies-list-item__company')
        if not company_div:
            continue
        text_parts = [t for t in company_div.contents if t.name != 'span']
        company_title = ''.join(t.strip()
                                for t in text_parts if isinstance(t, str))
        job_info = {
            "title": job_title,
            "job_link": f"{base_url}/{href}",
            "company_title": company_title
        }

        jobs.append(job_info)

    return jobs


async def _scrape_devby_jobs(session: Session):
    """Основная функция скрапинга"""
    start_time = time.time()

    # Статистика для отчета
    stats = {
        "total_found": 0,
        "successfully_parsed": 0,
        "added_to_db": 0,
        "duplicates_skipped": 0
    }

    browser = None
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)

            # Выполняем все задачи параллельно
            jobs_info = await asyncio.gather(*[
                get_jobs_details_from_page(url, browser) for url in URLS
            ])

            # Закрываем браузер ПОСЛЕ выполнения всех задач
            await browser.close()
            browser = None  # Помечаем как закрытый

    except Exception as e:
        logger.error(f"❌ Ошибка в scrape_devby_jobs: {e}")
        if browser:
            try:
                await browser.close()
            except:
                pass  # Игнорируем ошибки при закрытии
        return []


# Альтернативный вариант с более надежной обработкой ошибок:
async def scrape_devby_jobs(session: Session):
    """Основная функция скрапинга с улучшенной обработкой ошибок"""
    start_time = time.time()
    all_jobs = []

    stats = {
        "total_found": 0,
        "successfully_parsed": 0,
        "added_to_db": 0,
        "duplicates_skipped": 0
    }

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)

        try:
            # Выполняем все задачи параллельно
            jobs_info = await asyncio.gather(*[
                get_jobs_details_from_page(url, browser) for url in URLS
            ], return_exceptions=True)  # Не прерываем выполнение при ошибке в одной задаче

            unique_jobs = remove_duplicate_jobs(jobs_info)
            stats["total_found"] = len(unique_jobs)

            jobs_details = await asyncio.gather(*[
                get_job_detail(j, browser) for j in unique_jobs
            ], return_exceptions=True)  # Не прерываем выполнение при ошибке в одной задаче

            stats["successfully_parsed"] = len(jobs_details)

            for parsed_job in jobs_details:
                existing = session.exec(
                    select(Job).where(Job.url == parsed_job["job_link"])).first()
                if not existing:
                    job = Job(
                        title=parsed_job["title"],
                        url=parsed_job["job_link"],
                        description=parsed_job["job_description"],
                        source=SOURCE,
                        parsed_at=datetime.utcnow(),
                        company_url=parsed_job["company_link"],
                        company=parsed_job["company_title"]
                    )
                    session.add(job)
                    stats["added_to_db"] += 1
                    logger.info(f"✅ Сохранено: {parsed_job['title']}")
                else:
                    stats["duplicates_skipped"] += 1
                    logger.info(f"⚠️ Пропущено (дубликат): {existing.title}")
            session.commit()

            end_time = time.time()
            duration = end_time - start_time

        # Формируем и отправляем отчет в Slack
            report = (
                f"📊 *Сводка по парсингу* {SOURCE}:\n"
                f"Всего найдено запросов по запрос: {stats['total_found']}\n"
                f"Успешно спарсили: {stats['successfully_parsed']}\n"
                f"Добавили в БД: {stats['added_to_db']}\n"
                f"Пропустили дубликатов: {stats['duplicates_skipped']}\n"
                f"Время выполнения: {duration:.2f} секунд"
            )
            await send_slack_message(report)

        except Exception as e:
            logger.error(f"❌ Критическая ошибка в scrape_devby_jobs: {e}")
            return []
        finally:
            # Браузер автоматически закроется при выходе из контекста async with
            pass
