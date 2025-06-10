import asyncio
from bs4 import BeautifulSoup, ResultSet
from app.models import Job
from sqlmodel import select, Session
from datetime import datetime, timedelta
from app.utils.browser import fetch_html_browser
from typing import Any, Dict, List
from app.logger import logger
from functools import lru_cache
import time
import uuid

# Уменьшаем количество одновременных запросов
sem = asyncio.Semaphore(3)

# Кэш для хранения результатов парсинга на 1 час
CACHE_TTL = timedelta(hours=1)
parsed_urls_cache: Dict[str, tuple[datetime, Dict]] = {}


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


def get_cached_result(url: str) -> Dict | None:
    """Получить кэшированный результат или None если кэш устарел"""
    if url in parsed_urls_cache:
        timestamp, result = parsed_urls_cache[url]
        if datetime.utcnow() - timestamp < CACHE_TTL:
            return result
        del parsed_urls_cache[url]
    return None


def cache_result(url: str, result: Dict):
    """Сохранить результат в кэш"""
    parsed_urls_cache[url] = (datetime.utcnow(), result)


async def process_job_div_throttled(job_div):
    """Обработка div с вакансией с ограничением одновременных запросов"""
    async with sem:
        try:
            return await process_job_div(job_div)
        except Exception as e:
            logger.error(f"Error processing job div: {str(e)}")
            return None


def find_apply_link(s: BeautifulSoup) -> str | None:
    """Поиск ссылки на подачу заявки"""
    for a in s.find_all("a"):
        if "Apply for this job" in a.get_text(strip=True):
            return f"{base_url}/{a['href'].lstrip('/')}"
    return None


async def get_job_description(url: str) -> Dict[str, str]:
    """Получение описания вакансии с кэшированием"""
    # Проверяем кэш
    cached_result = get_cached_result(url)
    if cached_result:
        logger.info(f"📊 Использую кэшированное описание для {url}")
        return cached_result

    try:
        job_html = await fetch_html_browser(url)
        soup = BeautifulSoup(job_html, "html.parser")
        desc_div = soup.find("div", class_=["trix-content"])
        apply_url = find_apply_link(soup)

        if not desc_div:
            logger.warning(f"⚠️ Не найдено описание для {url}")
            return {"description": "", "apply_url": apply_url}

        result = {
            "description": desc_div.get_text(),
            "apply_url": apply_url
        }

        # Кэшируем результат
        cache_result(url, result)
        return result
    except Exception as e:
        logger.error(f"❌ Ошибка при получении описания {url}: {str(e)}")
        return {"description": "", "apply_url": None}


async def process_job_div(job_div: ResultSet[Any]) -> Dict | None:
    """Обработка div с вакансией"""
    try:
        link_tag = job_div.find(
            "a", attrs={"data-mark-visited-links-target": "anchor"})
        if not link_tag:
            return None

        href = link_tag["href"].lstrip("/")
        full_job_url = f"{base_url}/{href}"

        company_link_tag = link_tag.find_next("a")
        if not company_link_tag:
            return None

        company_href = company_link_tag["href"].lstrip("/")
        company_url = f"{base_url}/{company_href}"
        company_name = company_link_tag.get_text()
        job_title = " ".join(line.strip() for line in link_tag.get_text(
        ).strip().splitlines() if line.strip())

        job_info = await get_job_description(full_job_url)

        return {
            "url": full_job_url,
            "company_url": company_url,
            "company_name": company_name,
            "title": job_title,
            "description": job_info["description"],
            "apply_url": job_info["apply_url"]
        }
    except Exception as e:
        logger.error(f"❌ Ошибка при обработке вакансии: {str(e)}")
        return None


async def parse_jobs_from_html(html: str) -> List[Job]:
    """Парсинг вакансий из HTML"""
    try:
        soup = BeautifulSoup(html, "html.parser")
        hits_div = soup.find("div", attrs={"data-search-target": "hits"})
        if not hits_div:
            logger.warning("⚠️ Не найден div с вакансиями")
            return []

        job_rows = hits_div.find_all("div", class_="isolate")
        logger.info(f"📊 Найдено {len(job_rows)} вакансий")

        # Обрабатываем вакансии с ограничением одновременных запросов
        parsed_jobs = await asyncio.gather(
            *[process_job_div_throttled(job) for job in job_rows],
            return_exceptions=True
        )

        # Фильтруем None и исключения
        parsed_jobs = [
            job for job in parsed_jobs if job is not None and not isinstance(job, Exception)]

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
    except Exception as e:
        logger.error(f"❌ Ошибка при парсинге HTML: {str(e)}")
        return []


async def scrape_startup_jobs(session: Session):
    """Основная функция скрапинга"""
    start_time = time.time()
    all_jobs = []

    try:
        screenshot_uuid = str(uuid.uuid4())[:8]
        # Получаем HTML со всех URL с ограничением одновременных запросов
        tasks = [fetch_html_browser(
            url, f"startup_jobs_{screenshot_uuid}.png") for url in URLS]
        html_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Обрабатываем результаты
        for html in html_results:
            if isinstance(html, Exception):
                logger.error(f"❌ Ошибка при получении HTML: {str(html)}")
                continue

            jobs = await parse_jobs_from_html(html)

            # Проверяем дубликаты и сохраняем новые вакансии
            for job in jobs:
                existing = session.exec(
                    select(Job).where(Job.url == job.url)).first()

                if not existing:
                    logger.info(f"📊 Сохраняю в БД {job.url}")
                    session.add(job)
                    all_jobs.append(job)
                else:
                    logger.info(f"⚠️ Пропускаю дубликат {job.url}")

        # Сохраняем все изменения одним коммитом
        if all_jobs:
            session.commit()

        end_time = time.time()
        logger.info(
            f"✅ Скрапинг завершен за {end_time - start_time:.2f} секунд. Добавлено {len(all_jobs)} вакансий")

        return all_jobs
    except Exception as e:
        logger.error(f"❌ Критическая ошибка при скрапинге: {str(e)}")
        return []
