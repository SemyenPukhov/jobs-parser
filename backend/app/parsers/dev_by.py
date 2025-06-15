import asyncio
from bs4 import BeautifulSoup, ResultSet
from app.models import Job
from sqlmodel import select, Session
from datetime import datetime, timedelta
from app.utils.browser import fetch_html_async
from typing import Any, Dict, List, Optional
from app.logger import logger
from app.utils.slack import send_slack_message
from functools import lru_cache
import time
import uuid
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError


# Семафор для ограничения количества одновременных операций
MAX_CONCURRENT_TABS = 5
sem = asyncio.Semaphore(MAX_CONCURRENT_TABS)

URLS = [
    "https://jobs.devby.io/?filter[specialization_title]=Front-end/JS&filter[job_types][]=remote_job",
    "https://jobs.devby.io/?filter[job_types][]=remote_job&filter[search]=angular",
    "https://jobs.devby.io/?filter[job_types][]=remote_job&filter[search]=node.js",
    "https://jobs.devby.io/?filter[job_types][]=remote_job&filter[search]=javascript",
    "https://jobs.devby.io/?filter[job_types][]=remote_job&filter[search]=typescript",
]

SOURCE = "jobs.devby.io"
BASE_URL = "https://jobs.devby.io"


def remove_duplicate_jobs(jobs_info: List[Any]) -> List[Dict[str, Any]]:
    """Удаляет дубликаты вакансий по job_link"""
    unique_jobs = []
    seen_urls = set()

    for result in jobs_info:
        if isinstance(result, Exception) or result is None:
            logger.warning(f"Пропускаем некорректный результат: {result}")
            continue

        for job in result:
            job_url = job.get('job_link', '')
            if job_url and job_url not in seen_urls:
                seen_urls.add(job_url)
                unique_jobs.append(job)

    return unique_jobs


async def get_job_detail(job: Dict[str, Any], browser) -> Optional[Dict[str, Any]]:
    """Получает детальную информацию о вакансии с использованием семафора"""
    async with sem:  # Ограничиваем количество одновременных запросов
        try:
            page_html = await fetch_html_async(job["job_link"], browser)
            if not page_html:
                logger.warning(
                    f"Не удалось получить HTML для {job['job_link']}")
                return None

            soup = BeautifulSoup(page_html, "html.parser")

            # Получаем описание вакансии
            job_description_div = soup.find("div", class_="vacancy__text")
            job_description = job_description_div.get_text(
                strip=True) if job_description_div else "Описание не найдено"

            # Получаем ссылку на компанию
            company_link_tag = soup.find("a", string="Профиль компании")
            company_link = company_link_tag.get(
                "href", "") if company_link_tag else ""

            job["company_link"] = company_link
            job["job_description"] = job_description

            logger.info(f"✅ Получены детали для: {job['title']}")
            return job

        except Exception as e:
            logger.error(
                f"❌ Ошибка получения деталей для {job.get('title', 'Unknown')}: {e}")
            return None


async def get_jobs_details_from_page(url: str, browser) -> Optional[List[Dict[str, Any]]]:
    """Получает список вакансий со страницы с использованием семафора"""
    async with sem:  # Ограничиваем количество одновременных запросов
        try:
            jobs = []
            page_html = await fetch_html_async(url, browser)

            if not page_html:
                logger.warning(f"Не удалось получить HTML для {url}")
                return None

            soup = BeautifulSoup(page_html, "html.parser")
            jobs_divs = soup.find_all('div', class_='vacancies-list-item')

            if len(jobs_divs) <= 1:
                logger.info(f'📊 Не найдено вакансий для {url}')
                return []

            # Исключаем последний элемент (обычно это пагинация)
            for job_div in jobs_divs[:-1]:
                try:
                    job_link_tag = job_div.find("a")
                    if not job_link_tag:
                        continue

                    href = job_link_tag.get("href", "")
                    job_title = job_link_tag.get_text(strip=True)

                    company_div = job_div.find(
                        'div', class_='vacancies-list-item__company')
                    if not company_div:
                        continue

                    # Извлекаем название компании
                    text_parts = [
                        t for t in company_div.contents if t.name != 'span']
                    company_title = ''.join(
                        t.strip() for t in text_parts if isinstance(t, str)).strip()

                    if not company_title:
                        company_title = "Компания не указана"

                    job_info = {
                        "title": job_title,
                        "job_link": f"{BASE_URL}/{href.lstrip('/')}",
                        "company_title": company_title
                    }

                    jobs.append(job_info)

                except Exception as e:
                    logger.error(f"❌ Ошибка парсинга вакансии: {e}")
                    continue

            logger.info(f"📋 Найдено {len(jobs)} вакансий на странице {url}")
            return jobs

        except Exception as e:
            logger.error(f"❌ Ошибка парсинга страницы {url}: {e}")
            return None


async def scrape_devby_jobs(session: Session) -> List[Dict[str, Any]]:
    """Основная функция скрапинга с улучшенной обработкой ошибок и семафором"""
    start_time = time.time()
    all_jobs = []

    stats = {
        "total_found": 0,
        "successfully_parsed": 0,
        "added_to_db": 0,
        "duplicates_skipped": 0,
        "errors": 0
    }

    logger.info(
        f"🚀 Начинаем парсинг {SOURCE} с максимум {MAX_CONCURRENT_TABS} одновременными вкладками")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            # Дополнительные аргументы для стабильности
            args=['--no-sandbox', '--disable-dev-shm-usage']
        )

        try:
            # Этап 1: Получаем списки вакансий со всех страниц
            logger.info("📋 Получаем списки вакансий...")
            jobs_info = await asyncio.gather(*[
                get_jobs_details_from_page(url, browser) for url in URLS
            ], return_exceptions=True)

            # Удаляем дубликаты
            unique_jobs = remove_duplicate_jobs(jobs_info)
            stats["total_found"] = len(unique_jobs)
            logger.info(
                f"📊 Найдено уникальных вакансий: {stats['total_found']}")

            if not unique_jobs:
                logger.warning("⚠️ Не найдено вакансий для обработки")
                return []

            # Этап 2: Получаем детальную информацию о каждой вакансии
            logger.info("🔍 Получаем детальную информацию о вакансиях...")
            jobs_details = await asyncio.gather(*[
                get_job_detail(job, browser) for job in unique_jobs
            ], return_exceptions=True)

            # Фильтруем успешно обработанные вакансии
            successful_jobs = []
            for job_detail in jobs_details:
                if isinstance(job_detail, Exception):
                    stats["errors"] += 1
                    logger.error(f"❌ Ошибка обработки вакансии: {job_detail}")
                elif job_detail is not None:
                    successful_jobs.append(job_detail)

            stats["successfully_parsed"] = len(successful_jobs)
            logger.info(
                f"✅ Успешно обработано вакансий: {stats['successfully_parsed']}")

            # Этап 3: Сохраняем в базу данных
            logger.info("💾 Сохраняем в базу данных...")
            for parsed_job in successful_jobs:
                try:
                    existing = session.exec(
                        select(Job).where(Job.url == parsed_job["job_link"])
                    ).first()

                    if not existing:
                        job = Job(
                            title=parsed_job["title"],
                            url=parsed_job["job_link"],
                            description=parsed_job["job_description"],
                            source=SOURCE,
                            parsed_at=datetime.utcnow(),
                            company_url=parsed_job.get("company_link", ""),
                            company=parsed_job["company_title"]
                        )
                        session.add(job)
                        stats["added_to_db"] += 1
                        logger.info(f"✅ Сохранено: {parsed_job['title']}")
                    else:
                        stats["duplicates_skipped"] += 1
                        logger.info(
                            f"⚠️ Пропущено (дубликат): {existing.title}")

                except Exception as e:
                    logger.error(
                        f"❌ Ошибка сохранения вакансии {parsed_job.get('title', 'Unknown')}: {e}")
                    stats["errors"] += 1

            session.commit()
            logger.info("💾 Изменения сохранены в базу данных")

        except Exception as e:
            logger.error(f"❌ Критическая ошибка в scrape_devby_jobs: {e}")
            stats["errors"] += 1
            session.rollback()
        finally:
            await browser.close()
            logger.info("🔒 Браузер закрыт")

    # Формируем и отправляем отчет
    end_time = time.time()
    duration = end_time - start_time

    report = (
        f"📊 *Сводка по парсингу {SOURCE}*:\n"
        f"Всего найдено вакансий: {stats['total_found']}\n"
        f"Успешно обработано: {stats['successfully_parsed']}\n"
        f"Добавлено в БД: {stats['added_to_db']}\n"
        f"Пропущено дубликатов: {stats['duplicates_skipped']}\n"
        f"Ошибок: {stats['errors']}\n"
        f"Время выполнения: {duration:.2f} секунд\n"
        f"Максимум одновременных вкладок: {MAX_CONCURRENT_TABS}"
    )

    try:
        await send_slack_message(report)
        logger.info("📤 Отчет отправлен в Slack")
    except Exception as e:
        logger.error(f"❌ Ошибка отправки отчета в Slack: {e}")

    logger.info(report)
    return successful_jobs


# Функция для настройки семафора (опционально)
def set_max_concurrent_tabs(max_tabs: int):
    """Позволяет изменить максимальное количество одновременных вкладок"""
    global sem, MAX_CONCURRENT_TABS
    MAX_CONCURRENT_TABS = max_tabs
    sem = asyncio.Semaphore(max_tabs)
    logger.info(
        f"🔧 Установлено максимальное количество одновременных вкладок: {max_tabs}")
