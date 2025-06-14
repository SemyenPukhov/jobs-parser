import asyncio
from bs4 import BeautifulSoup, ResultSet
from app.models import Job
from sqlmodel import select, Session
from datetime import datetime, timedelta
from app.utils.browser import fetch_html_browser, get_browser_page, fetch_html_async
from typing import Any, Dict, List, Optional
from app.logger import logger
from app.utils.slack import send_slack_message
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
        try:
            return await get_job_details(job, browser)
        except Exception as e:
            logger.error(
                f"❌ Ошибка при обработке вакансии {job.get('title', 'Unknown')}: {str(e)}")
            return None


async def get_full_jobs_page(url: str):
    max_pages = 10
    page_num = 0

    try:
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
    except Exception as e:
        logger.error(f"❌ Ошибка при загрузке страницы {url}: {str(e)}")
        return None


async def get_job_details(job: Dict[str, str], browser):
    try:
        html = await fetch_html_async(job["href"], browser)
        if not html:
            logger.warning(f"⚠️ Пустой HTML для {job['href']}")
            return None

        soup = BeautifulSoup(html, "html.parser")
        description_div = soup.find('div', class_="content_vacancy_div")
        job_description = description_div.get_text(
        ) if description_div is not None else "Не найдено"

        company_link_tag = soup.find("a", string="Подробнее о компании")
        company_url = company_link_tag['href'] if company_link_tag else ""

        return {
            "url": job["href"],
            "title": job["title"],
            "description": job_description,
            "company_url": company_url,
            "company": job["company"]
        }
    except Exception as e:
        logger.error(
            f"❌ Ошибка при парсинге деталей вакансии {job.get('href', 'Unknown')}: {str(e)}")
        return None


async def get_job_links_from_page(html: str) -> List[Dict[str, str]]:
    """Возвращает список вакансий или пустой список в случае ошибки"""
    if not html:
        logger.warning("⚠️ Пустой HTML при парсинге ссылок на вакансии")
        return []

    try:
        soup = BeautifulSoup(html, "html.parser")
        links = soup.find_all("a", class_="card-jobs")
        job_links = []

        for job_link in links:
            try:
                title_div = job_link.find('div', class_='company-titile')
                if not title_div:
                    continue

                company_p = title_div.find('p')
                if not company_p:
                    continue

                company = company_p.get_text(strip=True)
                job_title_tag = job_link.find('h1')
                if not job_title_tag:
                    continue

                job_title = job_title_tag.get_text(strip=True)
                job_href = job_link.get('href')
                if not job_href:
                    continue

                job_details = {
                    "title": job_title,
                    "company": company,
                    "href": job_href
                }
                job_links.append(job_details)
            except Exception as e:
                logger.warning(
                    f"⚠️ Ошибка при парсинге отдельной вакансии: {str(e)}")
                continue

        logger.info(f"📊 Найдено {len(job_links)} вакансий на странице")
        return job_links
    except Exception as e:
        logger.error(f"❌ Ошибка при парсинге ссылок на вакансии: {str(e)}")
        return []


async def scrape_vseti_app_jobs(session: Session):
    """Основная функция скрапинга"""
    start_time = time.time()
    all_jobs = []

    # Статистика для отчета
    stats = {
        "total_found": 0,
        "successfully_parsed": 0,
        "added_to_db": 0,
        "duplicates_skipped": 0
    }

    try:
        # Получаем HTML страниц
        tasks = [get_full_jobs_page(url) for url in URLS]
        html_pages = await asyncio.gather(*tasks, return_exceptions=True)

        # Фильтруем успешные результаты
        valid_html_pages = []
        for i, html in enumerate(html_pages):
            if isinstance(html, Exception):
                logger.error(
                    f"❌ Ошибка при загрузке URL {URLS[i]}: {str(html)}")
            elif html is not None:
                valid_html_pages.append(html)
            else:
                logger.warning(f"⚠️ Пустой HTML для URL {URLS[i]}")

        if not valid_html_pages:
            logger.error("❌ Не удалось загрузить ни одной страницы")
            return []

        # Парсим ссылки на вакансии
        job_links_tasks = [get_job_links_from_page(
            html) for html in valid_html_pages]
        jobs_nested = await asyncio.gather(*job_links_tasks, return_exceptions=True)

        # Объединяем все вакансии в один список
        jobs = []
        for job_list in jobs_nested:
            if isinstance(job_list, Exception):
                logger.error(f"❌ Ошибка при парсинге ссылок: {str(job_list)}")
            elif job_list is not None:
                jobs.extend(job_list)

        if not jobs:
            logger.warning("⚠️ Не найдено ни одной вакансии")
            return []

        stats["total_found"] = len(jobs)
        logger.info(
            f"📊 Всего найдено {len(jobs)} вакансий для детального парсинга")

        # Получаем детальную информацию о вакансиях
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)

            all_results = await asyncio.gather(*[
                process_page_throttled(job, browser) for job in jobs
            ], return_exceptions=True)

            await browser.close()

        # Обрабатываем результаты
        valid_jobs = []
        for result in all_results:
            if isinstance(result, Exception):
                logger.error(f"❌ Ошибка при обработке вакансии: {str(result)}")
            elif result is not None:
                valid_jobs.append(result)

        stats["successfully_parsed"] = len(valid_jobs)
        logger.info(f"📊 Успешно обработано {len(valid_jobs)} вакансий")

        # Сохраняем в базу данных
        for job_info in valid_jobs:
            try:
                existing = session.exec(
                    select(Job).where(Job.url == job_info["url"])).first()
                if not existing:
                    job = Job(
                        title=job_info["title"],
                        url=job_info["url"],
                        description=job_info["description"],
                        source=SOURCE,
                        parsed_at=datetime.utcnow(),
                        company_url=job_info.get("company_url", ""),
                        company=job_info["company"]
                    )
                    session.add(job)
                    all_jobs.append(job)
                    stats["added_to_db"] += 1
                    logger.info(f"✅ Сохранено: {job_info['title']}")
                else:
                    stats["duplicates_skipped"] += 1
                    logger.info(f"⚠️ Пропущено (дубликат): {existing.title}")
            except Exception as e:
                logger.error(
                    f"❌ Ошибка при сохранении вакансии {job_info.get('title', 'Unknown')}: {str(e)}")
                continue

        if all_jobs:
            try:
                session.commit()
                logger.info(f"✅ Коммит в БД успешен")
            except Exception as e:
                logger.error(f"❌ Ошибка при коммите в БД: {str(e)}")
                session.rollback()

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

        logger.info(
            f"✅ Скрапинг завершен за {duration:.2f} секунд. Добавлено {len(all_jobs)} вакансий")

        return all_jobs
    except Exception as e:
        error_message = f"❌ Критическая ошибка при скрапинге: {str(e)}"
        logger.error(error_message)
        await send_slack_message(f"❌ Ошибка при парсинге {SOURCE}:\n{str(e)}")
        return []
