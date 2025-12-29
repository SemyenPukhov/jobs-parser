from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
from app.parsers.startup_jobs import scrape_startup_jobs
from app.parsers.thehub_io import scrape_thehub_jobs
from app.parsers.vseti_app import scrape_vseti_app_jobs
from app.parsers.dev_by import scrape_devby_jobs
from app.parsers.justremote_co import scrape_justremote_jobs
from app.parsers.remoteok import scrape_remoteok_jobs


from app.db import get_session
from app.logger import logger
from app.utils.slack import send_slack_message
from app.analytics import send_daily_analytics
import asyncio

# Создаем планировщик
scheduler = AsyncIOScheduler()


async def run_single_parser(name: str, parser_func, session):
    """Run a single parser with error handling."""
    try:
        logger.info(f"📊 Запускаю {name} парсер")
        await send_slack_message(f"Запуск парсера {name} 🔨")
        await parser_func(session)
        await send_slack_message(f"Парсер {name} завершил работу ✅")
        return True
    except Exception as e:
        error_msg = f"❌ Ошибка в парсере {name}: {str(e)}"
        logger.error(error_msg)
        await send_slack_message(error_msg)
        return False


async def run_parsers():
    """Запускает все парсеры последовательно"""
    logger.info("🚀 Начинаю запуск парсеров")
    await send_slack_message("🚀 Начинаю ежедневный запуск парсеров")

    session = next(get_session())
    
    parsers = [
        ("startup.jobs", scrape_startup_jobs),
        ("thehub.io", scrape_thehub_jobs),
        ("vseti.app", scrape_vseti_app_jobs),
        ("devby.jobs", scrape_devby_jobs),
        ("justremote.co", scrape_justremote_jobs),
        ("remoteok.io", scrape_remoteok_jobs),
    ]
    
    success_count = 0
    fail_count = 0
    
    try:
        for name, parser_func in parsers:
            result = await run_single_parser(name, parser_func, session)
            if result:
                success_count += 1
            else:
                fail_count += 1
        
        summary = f"✅ Парсеры завершили работу. Успешно: {success_count}, ошибок: {fail_count}"
        logger.info(summary)
        await send_slack_message(summary)
    finally:
        session.close()


async def run_matching_job():
    """Run matching of developers with jobs"""
    # Import here to avoid issues during startup
    from app.matching import run_matching, send_matching_results
    
    logger.info("🔍 Начинаю матчинг разработчиков с вакансиями")
    await send_slack_message("🔍 Запуск ежедневного матчинга разработчиков с вакансиями")
    
    session = next(get_session())
    try:
        results = await run_matching(session)
        
        if results:
            await send_matching_results(results, session)
            logger.info(f"✅ Матчинг завершен успешно. Найдено совпадений для {len(results)} вакансий")
            await send_slack_message(f"✅ Матчинг завершен успешно. Обработано {len(results)} вакансий")
        else:
            logger.info("ℹ️ Матчинг завершен. Совпадений не найдено")
            await send_slack_message("ℹ️ Матчинг завершен. Совпадений не найдено")
            
    except Exception as e:
        error_msg = f"❌ Ошибка при матчинге: {str(e)}"
        logger.error(error_msg)
        await send_slack_message(error_msg)
    finally:
        session.close()


def start_scheduler():
    """Запускает планировщик"""
    # Настраиваем время запуска (03:00 по Москве)
    moscow_tz = pytz.timezone('Europe/Moscow')

    # Добавляем задачу в планировщик для парсеров
    scheduler.add_job(
        run_parsers,
        trigger=CronTrigger(hour=3, minute=15, timezone=moscow_tz),
        id="daily_parsers",
        name="Запуск парсеров каждый день в 03:15 по Москве",
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

    # Добавляем задачу в планировщик для матчинга разработчиков с вакансиями
    scheduler.add_job(
        run_matching_job,
        trigger=CronTrigger(
            day_of_week='mon-fri',
            hour=9,
            minute=0,
            timezone=moscow_tz
        ),
        id='daily_matching',
        name='Матчинг разработчиков с вакансиями (пн-пт в 09:00 МСК)'
    )

    # Запускаем планировщик
    scheduler.start()
    logger.info("✅ Планировщик запущен")
    asyncio.create_task(send_slack_message(
        "✅ Планировщик запущен и готов к работе"))

    # Запускаем парсеры сразу при старте (опционально)
    # asyncio.create_task(run_parsers())
