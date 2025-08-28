import asyncio
from bs4 import BeautifulSoup, ResultSet
from app.models import Job
from sqlmodel import select, Session
from datetime import datetime
from app.utils.browser import fetch_html_async
from app.logger import logger
from app.utils.slack import send_slack_message
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse, urljoin
from playwright.async_api import (
    async_playwright,
    TimeoutError as PlaywrightTimeoutError,
)
import time
from typing import Dict, Any
import re

sem = asyncio.Semaphore(10)

URLS = [
    "https://thehub.io/jobs?roles=backenddeveloper&roles=engineer&roles=frontenddeveloper&roles=fullstackdeveloper&roles=mobiledevelopment&paid=true&countryCode=REMOTE&sorting=mostPopular"
]

SOURCE = "thehub.io"
base_url = "https://thehub.io"


async def process_page_throttled(url: str, browser, stats: Dict[str, Any]):
    async with sem:
        return await process_page(url, browser, stats)


def update_url_param(url: str, key: str, value: str) -> str:
    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.query)
    query_params[key] = [value]
    new_query = urlencode(query_params, doseq=True)
    return urlunparse(parsed_url._replace(query=new_query))


async def _dismiss_cookies(page):
    # 1) Пытаемся вызвать глобальную функцию баннера, если есть
    try:
        called = await page.evaluate(
            """
        () => {
            try {
                if (window.CookieInformation &&
                    typeof window.CookieInformation.submitAllCategories === 'function') {
                    window.CookieInformation.submitAllCategories();
                    return true;
                }
            } catch (e) {}
            return false;
        }
        """
        )
        if called:
            return
    except Exception:
        pass

    # 2) Кликаем по точному классу кнопки (как в вашем HTML)
    for sel in [
        "button.coi-consent-banner__agree-button",
        'button[onclick*="CookieInformation.submitAllCategories"]',
    ]:
        try:
            btn = page.locator(sel)
            if await btn.count() > 0:
                await btn.first.click(timeout=2500)
                return
        except Exception:
            pass

    # 3) Запасной вариант — кнопка с текстом OK
    try:
        await page.get_by_role("button", name=re.compile(r"^\s*ok\s*$", re.I)).click(
            timeout=2000
        )
    except Exception:
        pass


async def get_max_page(url: str, browser) -> int:
    page = await browser.new_page()
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)

        # Попробуем закрыть куки, чтобы они не перекрывали пагинацию/клики
        await _dismiss_cookies(page)

        # Дадим CSR дорисоваться, но без жестких ожиданий
        try:
            await page.wait_for_load_state("networkidle", timeout=10000)
        except PlaywrightTimeoutError:
            pass

        # Ждём появление списка пагинации (точно ваш селектор)
        pagination = None
        for sel in [
            'ul[aria-label="Pagination"]',
            'ul.pagination[aria-label="Pagination"]',  # запасной
            'ul.b-pagination[aria-label="Pagination"]',  # запасной
        ]:
            try:
                await page.wait_for_selector(sel, timeout=6000, state="attached")
                pagination = page.locator(sel)
                break
            except PlaywrightTimeoutError:
                continue

        if pagination is None:
            # возможно ленивый рендер — проскроллим и попробуем ещё раз
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(500)
            try:
                await page.wait_for_selector(
                    'ul[aria-label="Pagination"]', timeout=4000, state="attached"
                )
                pagination = page.locator('ul[aria-label="Pagination"]')
            except PlaywrightTimeoutError:
                # нет пагинации — одна страница
                return 1

        # Убедимся, что есть хотя бы одна ссылка
        await pagination.locator("a").first.wait_for(state="attached", timeout=4000)

        # --- Heuristic #1: aria-setsize на радио-ссылках (в вашем HTML это "2")
        max_pages = None
        try:
            radios = pagination.locator('a[role="menuitemradio"]')
            rcnt = await radios.count()
            sizes = []
            for i in range(rcnt):
                val = await radios.nth(i).get_attribute("aria-setsize")
                if val and val.isdigit():
                    sizes.append(int(val))
            if sizes:
                max_pages = max(sizes)
        except Exception:
            pass
        if isinstance(max_pages, int) and max_pages > 0:
            return max_pages

        # --- Heuristic #2: парсим параметр ?page= из href
        links = pagination.locator("a[href]")
        lcnt = await links.count()
        pages = []
        for i in range(lcnt):
            a = links.nth(i)
            href = await a.get_attribute("href") or ""
            if href:
                abs_url = urljoin(url, href)
                q = parse_qs(urlparse(abs_url).query)
                val = q.get("page", [None])[0]
                if val and str(val).isdigit():
                    pages.append(int(val))
                    continue
            # Иногда номер прямо в тексте <a>2</a>
            try:
                txt = (await a.inner_text()).strip()
                if re.fullmatch(r"\d+", txt):
                    pages.append(int(txt))
            except Exception:
                pass

        if pages:
            return max(pages)

        # --- Heuristic #3: ссылка "последняя" (» / last)
        try:
            last_link = pagination.locator(
                'a[aria-label*="last" i], a:has-text("»")'
            ).first
            if await last_link.count() > 0:
                href = await last_link.get_attribute("href")
                if href:
                    abs_url = urljoin(url, href)
                    q = parse_qs(urlparse(abs_url).query)
                    val = q.get("page", [None])[0]
                    if val and str(val).isdigit():
                        return int(val)
        except Exception:
            pass

        # если ничего не вышло — считаем, что 1 страница
        return 1

    except PlaywrightTimeoutError:
        logger.warning(f"⏱ Timeout при загрузке или поиске пагинации на {url}")
        return 1
    finally:
        await page.close()


async def get_paginated_urls(url: str, browser) -> list[str]:
    max_page = await get_max_page(url, browser)
    return [update_url_param(url, "page", str(i + 1)) for i in range(max_page)]


async def process_job(job_div: ResultSet, browser) -> dict[str, str] | None:
    job_link_tag = job_div.find("a")
    if not job_link_tag:
        return None

    href = job_link_tag["href"].lstrip("/")
    job_url = f"{base_url}/{href}"

    job_page_html = await fetch_html_async(job_url, browser)
    soup = BeautifulSoup(job_page_html, "html.parser")
    content = soup.find("content")
    if not content:
        return None

    job_title_tag = content.find("h2")
    company_link_tag = job_title_tag.find_next("a") if job_title_tag else None

    job_title = job_title_tag.get_text(strip=True) if job_title_tag else "Untitled"
    company_href = (
        company_link_tag["href"].lstrip("/") if company_link_tag else "unknown"
    )
    company = company_link_tag.get_text()

    description_content = content.find_next("content")
    description = description_content.get_text()
    company_url = f"{base_url}/{company_href}"

    return {
        "url": job_url,
        "title": job_title,
        "description": description,
        "company_url": company_url,
        "company": company,
    }


async def process_page(
    url: str, browser, stats: Dict[str, Any]
) -> list[dict[str, str]]:
    page_html = await fetch_html_async(url, browser)
    soup = BeautifulSoup(page_html, "html.parser")
    content_tags = soup.find_all("content")
    if not content_tags:
        return []

    jobs_content = content_tags[-1]
    job_rows = jobs_content.find_all("div", recursive=False)
    stats["total_found"] += len(job_rows)

    return await asyncio.gather(
        *[process_job(job_row, browser) for job_row in job_rows]
    )


async def scrape_thehub_jobs(session: Session):
    all_jobs = []
    start_time = time.time()

    # Статистика для отчета
    stats = {
        "total_found": 0,
        "successfully_parsed": 0,
        "added_to_db": 0,
        "duplicates_skipped": 0,
    }

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)

            urls_nested = await asyncio.gather(
                *[get_paginated_urls(url, browser) for url in URLS]
            )
            urls = [u for group in urls_nested for u in group]

            all_results = await asyncio.gather(
                *[process_page_throttled(url, browser, stats) for url in urls]
            )
            flat_results = [job for group in all_results for job in group if job]

            stats["successfully_parsed"] = len(flat_results)

            for job_info in flat_results:
                existing = session.exec(
                    select(Job).where(Job.url == job_info["url"])
                ).first()
                if not existing:
                    job = Job(
                        title=job_info["title"],
                        url=job_info["url"],
                        description=job_info["description"],
                        source=SOURCE,
                        parsed_at=datetime.utcnow(),
                        company_url=job_info["company_url"],
                        company=job_info["company"],
                    )
                    session.add(job)
                    all_jobs.append(job)
                    stats["added_to_db"] += 1
                    logger.info(f"✅ Сохранено: {job_info['title']}")
                else:
                    stats["duplicates_skipped"] += 1
                    logger.info(f"⚠️ Пропущено (дубликат): {existing.title}")

            session.commit()
            await browser.close()

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

        return all_jobs
    except Exception as e:
        error_message = f"❌ Критическая ошибка при скрапинге: {str(e)}"
        logger.error(error_message)
        await send_slack_message(f"❌ Ошибка при парсинге {SOURCE}:\n{str(e)}")
        return []
