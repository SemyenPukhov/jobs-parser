from sqlmodel import select, Session
import time
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError, Browser, Page
from app.config import settings
from datetime import datetime
from bs4 import BeautifulSoup, ResultSet
import asyncio
from app.logger import logger
from app.utils.slack import send_slack_message
from app.models import Job

LOGIN_URL = "https://justremote.co/a/sign-in"
SOURCE = "justremote.co"

MAX_CONCURRENT_TABS = 5
sem = asyncio.Semaphore(MAX_CONCURRENT_TABS)


def get_today_formatted_date():
    day = datetime.today().day
    month = datetime.today().strftime("%b")

    if 10 <= day % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")

    return f"{day}{suffix} {month}"


async def login(browser: Browser) -> Page:
    page = await browser.new_page()

    await page.goto(LOGIN_URL)

    await page.locator('input[type="email"]').fill(settings.JUST_REMOTE_LOGIN)
    await page.locator('input[type="password"]').fill(settings.JUST_REMOTE_PWD)
    await page.locator('form button').click()

    await page.wait_for_load_state("networkidle")

    # await page.locator('div[class*="power-search-category-filter__Option"]:has-text("Developer")').click()
    await page.locator('//div[contains(@class, "power-search-category-filter__Option") and contains(text(), "Developer")]').click()
    await page.wait_for_load_state("networkidle")
    await page.wait_for_selector("div.infinite-scroll-component")

    return page


async def get_fresh_job_rows(page: Page):
    page_html = await page.content()
    soup = BeautifulSoup(page_html, "html.parser")

    container = soup.find("div", class_="infinite-scroll-component")
    if not container:
        return []

    today = get_today_formatted_date()
    matching_links = []

    for child in container.find_all("a", recursive=False):
        date_p = child.find("p", class_=lambda x: x and x.startswith(
            "power-search-job-item__Date"))
        if not date_p:
            continue

        text = date_p.get_text(strip=True)
        if text == today:
            matching_links.append(child)

    return matching_links


async def process_job(browser: Browser, job: dict):
    job_details = dict(job)

    async with sem:
        page = await browser.new_page()
        try:
            try:
                await page.goto(job['href'], wait_until="domcontentloaded", timeout=60000)
                await page.wait_for_load_state("networkidle", timeout=10000)
                await page.wait_for_timeout(1000)
            except PlaywrightTimeoutError:
                logger.info(
                    f"[WARN] Timeout on {job['href']} — trying to proceed anyway")

            soup = BeautifulSoup(await page.content(), "html.parser")

            fields = [
                soup.find("div", attrs={"data-qa": "job-description"}),
                soup.find("div", attrs={"data-qa": "salary-range"}),
                soup.find("div", attrs={"data-qa": "closing-description"})
            ]
            job_description = "\n".join(
                field.get_text(strip=True) for field in fields if field is not None
            )
            job_details["job_description"] = job_description

            apply_link_tag = soup.find(
                "a", attrs={"data-qa": "show-page-apply"})
            if apply_link_tag:
                job_details["apply_link_href"] = apply_link_tag.get("href")

            footer = soup.find("div", class_="main-footer")
            if footer:
                company_link_tag = footer.find("a")
                if company_link_tag:
                    job_details["company_href"] = company_link_tag.get("href")

            return job_details

        except Exception as e:
            logger.error(f"[ERROR] Failed to process {job['href']}: {e}")
            return None

        finally:
            await page.close()


async def scrape_justremote_jobs(session: Session):
    """Основная функция скрапинга"""
    start_time = time.time()

    stats = {
        "total_found": 0,
        "successfully_parsed": 0,
        "added_to_db": 0,
        "duplicates_skipped": 0,
        "errors": 0
    }

    proxy = {
        "server": f"socks5://{settings.SOCKS5_HOST}:1080",
        "username": settings.SOCKS5_USER,
        "password": settings.SOCKS5_PASSWORD,
    }

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-dev-shm-usage'],
            proxy=proxy
        )
        page = await login(browser)
        job_links = await get_fresh_job_rows(page)

        stats["total_found"] = len(job_links)

        jobs = []

        for job_link in job_links:
            href = job_link["href"]

            job_title_tag = job_link.find("h2")

            if not job_title_tag:
                continue
            job_title = job_title_tag.get_text(strip=True)

            company_p = job_link.find("p", class_=lambda x: x and x.startswith(
                "power-search-job-item__Company"))
            if not company_p:
                continue
            company_name = company_p.get_text(strip=True)

            jobs.append({
                "href": href,
                "job_title": job_title,
                "company_name": company_name
            })

        tasks = [process_job(browser, job) for job in jobs]
        results = await asyncio.gather(*tasks)

        clean_results = [res for res in results if res is not None]
        stats["successfully_parsed"] = len(clean_results)

        logger.info("💾 Сохраняем в базу данных...")

        for parsed_job in clean_results:
            try:
                existing = session.exec(
                    select(Job).where(Job.url == parsed_job["href"])
                ).first()

                if not existing:
                    job = Job(
                        title=parsed_job["job_title"],
                        url=parsed_job["href"],
                        description=parsed_job["job_description"],
                        source=SOURCE,
                        parsed_at=datetime.utcnow(),
                        company_url=parsed_job.get("company_href", None),
                        company=parsed_job["company_name"],
                        apply_url=parsed_job.get("apply_link_href", None)
                    )
                    session.add(job)
                    stats["added_to_db"] += 1
                    logger.info(f"✅ Сохранено: {parsed_job['job_title']}")
                else:
                    stats["duplicates_skipped"] += 1
                    logger.info(
                        f"⚠️ Пропущено (дубликат): {existing.title}")

            except Exception as e:
                logger.error(
                    f"❌ Ошибка сохранения вакансии {parsed_job.get('job_title', 'Unknown')}: {e}")
                stats["errors"] += 1

        session.commit()
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
