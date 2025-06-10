
import asyncio
from playwright.async_api import async_playwright,  TimeoutError as PlaywrightTimeoutError
# from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from app.logger import logger
from typing import Optional

MAX_PAGES = 15
browser_semaphore = asyncio.Semaphore(MAX_PAGES)


# @retry(
#     stop=stop_after_attempt(3),
#     wait=wait_exponential(multiplier=1, min=2, max=10),
#     retry=retry_if_exception_type(PlaywrightTimeoutError)
# )
async def fetch_html_browser(url: str, screenshot_path: Optional[str] = None) -> str:
    async with async_playwright() as p:
        logger.info(f"📊 Запрашиваю HTML: {url}")

        # Настройки для VPS
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--no-first-run',
                '--no-default-browser-check',
                '--disable-default-apps'
            ]
        )

        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Linux; x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = await context.new_page()

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_load_state("networkidle", timeout=10000)
            await page.wait_for_timeout(1000)
        except PlaywrightTimeoutError:
            logger.warning(
                f"⚠️ Timeout на {url}, возвращаю возможный контент...")

        if screenshot_path:
            try:
                await page.screenshot(path=screenshot_path, full_page=True)
                logger.info(f"📸 Скриншот сохранен: {screenshot_path}")
            except Exception as e:
                logger.error(f"❌ Ошибка при создании скриншота: {e}")

        content = await page.content()
        await context.close()
        await browser.close()
        return content


# @retry(
#     stop=stop_after_attempt(3),
#     wait=wait_exponential(multiplier=1, min=2, max=10),
#     retry=retry_if_exception_type(PlaywrightTimeoutError)
# )
# async def _fetch_html_async(url: str, browser) -> str:
#     # async with async_playwright() as p:
#     logger.info(f"📊 Запрашиваю HTML: {url}")
#     # browser = await p.chromium.launch(headless=False)
#     page = await browser.new_page()

#     try:
#         await page.goto(url, wait_until="domcontentloaded", timeout=60000)
#         await page.wait_for_load_state("networkidle", timeout=10000)
#         await page.wait_for_timeout(1000)  # Подстраховка
#     except PlaywrightTimeoutError:
#         logger.warning(
#             f"⚠️ Timeout на {url}, возвращаю возможный контент...")

#     content = await page.content()
#     await browser.close()
#     return content


async def fetch_html_async(url: str, browser) -> str:
    """Загружает HTML содержимое страницы с помощью переданного браузера."""
    async with browser_semaphore:
        page = await browser.new_page()
        try:
            logger.info(f"🌐 Загружаю страницу: {url}")
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_load_state("networkidle", timeout=10000)
            await page.wait_for_timeout(1000)  # небольшой запас
            content = await page.content()
        except PlaywrightTimeoutError:
            logger.warning(
                f"⚠️ Timeout при загрузке {url}, возвращаю частичный контент")
            content = await page.content()
        except Exception as e:
            logger.error(f"❌ Ошибка при загрузке {url}: {e}")
            content = ""
        finally:
            await page.close()
        return content
