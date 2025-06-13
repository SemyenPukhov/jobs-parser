from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
from app.parsers.startup_jobs import scrape_startup_jobs
from app.parsers.thehub_io import scrape_thehub_jobs
from app.parsers.vseti_app import scrape_vseti_app_jobs
from app.db import get_session
from app.logger import logger
import asyncio

# Создаем планировщик
scheduler = AsyncIOScheduler()


async def run_parsers():
    """Запускает все парсеры последовательно"""
    logger.info("🚀 Начинаю запуск парсеров")
    session = next(get_session())

    try:
        # Запускаем парсеры последовательно
        logger.info("📊 Запускаю startup.jobs парсер")
        await scrape_startup_jobs(session)

        logger.info("📊 Запускаю thehub.io парсер")
        await scrape_thehub_jobs(session)

        logger.info("📊 Запускаю vseti.app парсер")
        await scrape_vseti_app_jobs(session)

        logger.info("✅ Все парсеры успешно завершили работу")
    except Exception as e:
        logger.error(f"❌ Ошибка при запуске парсеров: {str(e)}")
    finally:
        session.close()


def start_scheduler():
    """Запускает планировщик"""
    # Настраиваем время запуска (03:00 по Москве)
    moscow_tz = pytz.timezone('Europe/Moscow')

    # Добавляем задачу в планировщик
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

    # Запускаем планировщик
    scheduler.start()
    logger.info("✅ Планировщик запущен")

    # Запускаем парсеры сразу при старте (опционально)
    # asyncio.create_task(run_parsers())
