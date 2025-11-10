import httpx
from typing import List, Dict, Any
from sqlmodel import Session, select
from app.models import Job, JobProcessingStatus
from app.config import settings
from app.logger import logger
from app.utils.openrouter import evaluate_match_batch
from app.utils.slack import send_slack_message
from datetime import datetime
import re


async def fetch_developers() -> List[Dict[str, Any]]:
    """
    Fetch all active developers from the external API.
    
    Returns:
        List of developer dictionaries
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(settings.DEVELOPERS_API_URL)
            
            if response.status_code == 200:
                developers = response.json()
                logger.info(f"📊 Получено {len(developers)} разработчиков из API")
                return developers
            else:
                logger.error(f"❌ Ошибка при получении разработчиков: {response.status_code}")
                return []
                
    except Exception as e:
        logger.error(f"❌ Ошибка при запросе к API разработчиков: {str(e)}")
        return []


def filter_jobs(jobs: List[Job]) -> List[Job]:
    """
    Filter jobs to only include remote positions.
    Exclude jobs that mention office/onsite requirements.
    
    Args:
        jobs: List of Job objects
    
    Returns:
        Filtered list of remote jobs
    """
    office_keywords = [
        'office', 'onsite', 'on-site', 'офис', 'в офис', 
        'визит в офис', 'офисная', 'офисное', 'on site'
    ]
    
    filtered = []
    
    for job in jobs:
        # Check title and description for office keywords
        text_to_check = f"{job.title} {job.description or ''}".lower()
        
        # Skip if any office keyword is found
        if any(keyword in text_to_check for keyword in office_keywords):
            logger.info(f"⚠️ Пропускаю вакансию (требуется офис): {job.title}")
            continue
        
        filtered.append(job)
    
    logger.info(f"✅ Отфильтровано {len(filtered)} удаленных вакансий из {len(jobs)}")
    return filtered


async def run_matching(session: Session) -> Dict[str, List[Dict[str, Any]]]:
    """
    Main matching function that evaluates developers against open jobs.
    Returns ALL unprocessed jobs (for Slack), but only runs matching on jobs without results.
    
    Args:
        session: Database session
    
    Returns:
        Dictionary mapping job_id to list of matching developers with scores
    """
    logger.info("🔍 Начинаю процесс матчинга...")
    
    # Step 1: Fetch developers
    developers = await fetch_developers()
    if not developers:
        logger.warning("⚠️ Не найдено активных разработчиков")
        return {}
    
    # Step 2: Get ALL unprocessed jobs (not yet processed by manager)
    all_unprocessed_statement = (
        select(Job)
        .outerjoin(JobProcessingStatus, Job.id == JobProcessingStatus.job_id)
        .where(JobProcessingStatus.job_id == None)
    )
    all_unprocessed_jobs = session.exec(all_unprocessed_statement).all()
    
    if not all_unprocessed_jobs:
        logger.warning("⚠️ Не найдено необработанных вакансий")
        return {}
    
    logger.info(f"📊 Найдено {len(all_unprocessed_jobs)} необработанных вакансий")
    
    # Step 3: Separate jobs into those needing matching and those already matched
    jobs_needing_matching = [job for job in all_unprocessed_jobs if job.matching_results is None]
    jobs_already_matched = [job for job in all_unprocessed_jobs if job.matching_results is not None]
    
    logger.info(f"🆕 Новых вакансий для матчинга: {len(jobs_needing_matching)}")
    logger.info(f"✅ Вакансий с сохраненными результатами: {len(jobs_already_matched)}")
    
    # Step 4: Initialize results dictionary with jobs that already have matching results
    results = {}
    
    # Load existing matching results from database
    for job in jobs_already_matched:
        if job.matching_results and job.matching_results.get("matches"):
            # Reconstruct matches from saved data
            job_matches = []
            for match_data in job.matching_results["matches"]:
                # Find the developer by ID
                dev = next((d for d in developers if str(d.get("id")) == str(match_data["developer_id"])), None)
                if dev:
                    job_matches.append({
                        "developer": dev,
                        "score": match_data["score"],
                        "reasoning": match_data["reasoning"]
                    })
            
            if job_matches:
                results[str(job.id)] = job_matches
                logger.info(f"📥 Загружены сохраненные результаты для {job.title}: {len(job_matches)} кандидатов")
    
    # Step 5: Filter NEW jobs (remote only)
    filtered_jobs = filter_jobs(jobs_needing_matching)
    
    if not filtered_jobs:
        logger.info("ℹ️ Нет новых вакансий для матчинга после фильтрации")
        # Return existing results from already matched jobs
        return results
    
    # Step 6: Match developers to NEW jobs using BATCH evaluation
    total_evaluations = 0
    scores_list = []
    
    # Create a dictionary to lookup developers by ID
    developers_by_id = {str(dev.get('id', idx)): dev for idx, dev in enumerate(developers)}
    
    for job in filtered_jobs:
        logger.info(f"🔍 Оцениваю кандидатов для вакансии: {job.title}")
        
        job_info = {
            "title": job.title,
            "company": job.company or "Не указана",
            "description": job.description or "Не указано"
        }
        
        try:
            # Batch evaluate ALL developers for this job in ONE LLM call
            evaluations = await evaluate_match_batch(developers, job_info)
            total_evaluations += len(evaluations)
            
            job_matches = []
            
            for evaluation in evaluations:
                dev_id = evaluation.get("developer_id")
                score = evaluation.get("score", 0)
                reasoning = evaluation.get("reasoning", "")
                scores_list.append(score)
                
                # Get the full developer data
                dev = developers_by_id.get(str(dev_id))
                if not dev:
                    logger.warning(f"⚠️ Developer ID {dev_id} not found in lookup")
                    continue
                
                # Only include matches with score >= 50
                if score >= settings.MATCHING_THRESHOLD_LOW:
                    job_matches.append({
                        "developer": dev,
                        "score": score,
                        "reasoning": reasoning
                    })
                    logger.info(f"  ✅ {dev.get('name', 'Unknown')} - Score: {score}")
                else:
                    logger.info(f"  ❌ {dev.get('name', 'Unknown')} - Score: {score} (below threshold)")
            
            # Sort matches by score (descending)
            job_matches.sort(key=lambda x: x["score"], reverse=True)
            
            # Save matching results to database to avoid re-processing (even if no matches found)
            matching_data = {
                "matched_at": datetime.utcnow().isoformat(),
                "matches_count": len(job_matches),
                "matches": [
                    {
                        "developer_id": match["developer"].get("id"),
                        "developer_name": match["developer"].get("name"),
                        "score": match["score"],
                        "reasoning": match["reasoning"]
                    }
                    for match in job_matches
                ]
            }
            job.matching_results = matching_data
            session.add(job)
            session.commit()
            
            if job_matches:
                results[str(job.id)] = job_matches
                logger.info(f"✅ Найдено {len(job_matches)} подходящих кандидатов для {job.title}")
                logger.info(f"💾 Сохранены результаты матчинга в БД")
            else:
                logger.info(f"ℹ️ Для вакансии {job.title} не найдено подходящих кандидатов (сохранено в БД)")
            
        except Exception as e:
            logger.error(f"❌ Ошибка при batch оценке для вакансии {job.title}: {str(e)}")
            continue
    
    # Log statistics
    if scores_list:
        avg_score = sum(scores_list) / len(scores_list)
        min_score = min(scores_list)
        max_score = max(scores_list)
        logger.info(f"📊 Статистика оценок: avg={avg_score:.1f}, min={min_score}, max={max_score}")
    
    logger.info(f"✅ Матчинг завершен. Проведено {total_evaluations} оценок, найдено совпадений для {len(results)} вакансий")
    
    return results


async def send_matching_results(results: Dict[str, List[Dict[str, Any]]], session: Session):
    """
    Format and send matching results to Slack.
    
    Args:
        results: Dictionary with job_id -> list of matching developers
        session: Database session to fetch job details
    """
    if not results:
        logger.info("ℹ️ Нет результатов для отправки в Slack")
        return
    
    manager_mention = f"<@{settings.SLACK_MANAGER_ID}>" if settings.SLACK_MANAGER_ID else "<!here>"
    
    for job_id_str, matches in results.items():
        try:
            # Fetch job from database
            job = session.get(Job, job_id_str)
            if not job:
                logger.error(f"❌ Вакансия {job_id_str} не найдена в БД")
                continue
            
            # Separate matches by score threshold
            excellent_matches = [m for m in matches if m["score"] >= settings.MATCHING_THRESHOLD_HIGH]
            good_matches = [m for m in matches if settings.MATCHING_THRESHOLD_LOW <= m["score"] < settings.MATCHING_THRESHOLD_HIGH]
            
            # Build message
            message = f"""🎯 *Найдены подходящие кандидаты!*

📋 *Вакансия:* {job.title}
🏢 *Компания:* {job.company or 'Не указана'}
🌐 *Источник:* {job.source}
🔗 *Ссылка:* {job.url}
"""
            
            if excellent_matches:
                message += f"\n✅ *Отлично подходят ({settings.MATCHING_THRESHOLD_HIGH}+):*\n"
                for match in excellent_matches:
                    dev = match["developer"]
                    name = dev.get('name', 'Не указано')
                    score = match["score"]
                    reasoning = match["reasoning"]
                    
                    message += f"\n• *{name}* (оценка: {score}/100)\n"
                    message += f"  _Обоснование:_ {reasoning}\n"
            
            if good_matches:
                message += f"\n⚠️ *Возможно подходят ({settings.MATCHING_THRESHOLD_LOW}-{settings.MATCHING_THRESHOLD_HIGH-1}):*\n"
                for match in good_matches:
                    dev = match["developer"]
                    name = dev.get('name', 'Не указано')
                    score = match["score"]
                    reasoning = match["reasoning"]
                    
                    message += f"\n• *{name}* (оценка: {score}/100)\n"
                    message += f"  _Обоснование:_ {reasoning}\n"
            
            message += f"\n👤 {manager_mention}, прошу рассмотреть кандидатов"
            
            # Send to Slack
            await send_slack_message(message)
            logger.info(f"✅ Отправлено сообщение в Slack для вакансии: {job.title}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка при отправке результатов для вакансии {job_id_str}: {str(e)}")

