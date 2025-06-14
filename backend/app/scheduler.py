from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
from app.parsers.startup_jobs import scrape_startup_jobs
from app.parsers.thehub_io import scrape_thehub_jobs
from app.parsers.vseti_app import scrape_vseti_app_jobs
from app.parsers.dev_by import scrape_devby_jobs

from app.db import get_session
from app.logger import logger
from app.utils.slack import send_slack_message
from app.analytics import send_daily_analytics
import asyncio

# Создаем планировщик
scheduler = AsyncIOScheduler()


async def run_parsers():
    """Запускает все парсеры последовательно"""
    logger.info("🚀 Начинаю запуск парсеров")
    await send_slack_message("🚀 Начинаю ежедневный запуск парсеров")

    session = next(get_session())

    try:
        # Запускаем парсеры последовательно
        logger.info("📊 Запускаю startup.jobs парсер")
        await send_slack_message(
            "Запуск парсера startup.jobs 🔨"
        )
        await scrape_startup_jobs(session)
        await send_slack_message(
            "Парсер startup.jobs завершил работу ✅",
        )

        logger.info("📊 Запускаю thehub.io парсер")
        await send_slack_message(
            "Запуск парсера thehub.io 🔨",
        )
        await scrape_thehub_jobs(session)
        await send_slack_message(
            "Парсер thehub.io завершил работу ✅",
        )

        logger.info("📊 Запускаю vseti.app парсер")
        await send_slack_message(
            "Запуск парсера vseti.app 🔨",
        )
        await scrape_vseti_app_jobs(session)
        await send_slack_message(
            "Парсер vseti.app завершил работу ✅",
        )

        logger.info("📊 Запускаю devby.jobs парсер")
        await send_slack_message(
            "Запуск парсера devby.jobs 🔨"
        )
        await scrape_devby_jobs(session)
        await send_slack_message(
            "Парсер vseti.app завершил работу ✅"
        )

        logger.info("✅ Все парсеры успешно завершили работу")
        await send_slack_message("✅ Все парсеры успешно завершили работу")
    except Exception as e:
        error_message = f"❌ Ошибка при запуске парсеров: {str(e)}"
        logger.error(error_message)
        await send_slack_message(error_message)
    finally:
        session.close()


def start_scheduler():
    """Запускает планировщик"""
    # Настраиваем время запуска (03:00 по Москве)
    moscow_tz = pytz.timezone('Europe/Moscow')

    # Добавляем задачу в планировщик для парсеров
    scheduler.add_job(
        run_parsers,
        trigger=CronTrigger(
            hour=3,
            minute=0,
            timezone=moscow_tz
        ),
        id='daily_parsers',
        name='Запуск парсеров каждый день в 03:00 по Москве'
    )

    # Добавляем задачу в планировщик для аналитики
    scheduler.add_job(
        send_daily_analytics,
        trigger=CronTrigger(
            hour=21,
            minute=0,
            timezone=moscow_tz
        ),
        id='daily_analytics',
        name='Отправка ежедневной аналитики в 21:00 по Москве'
    )

    # Запускаем планировщик
    scheduler.start()
    logger.info("✅ Планировщик запущен")
    asyncio.create_task(send_slack_message(
        "✅ Планировщик запущен и готов к работе"))

    # Запускаем парсеры сразу при старте (опционально)
    # asyncio.create_task(run_parsers())
