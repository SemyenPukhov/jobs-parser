import os
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from app.logger import logger
from app.config import settings

# Инициализируем клиент Slack
slack_token = settings.SLACK_BOT_TOKEN
slack_channel = settings.SLACK_CHANNEL_ID

if not slack_token or not slack_channel:
    logger.warning(
        "⚠️ Slack токен или ID канала не настроены. Уведомления в Slack отключены.")
    client = None
else:
    client = WebClient(token=slack_token)


async def send_slack_message(message: str) -> bool:
    """
    Отправляет сообщение в Slack канал.

    Args:
        message: Текст сообщения
        blocks: Опциональные блоки форматирования Slack

    Returns:
        bool: True если сообщение отправлено успешно, False в случае ошибки
    """
    if not client:
        logger.warning(
            "⚠️ Попытка отправить сообщение в Slack, но клиент не инициализирован")
        return False

    try:
        # Добавляем префикс окружения к сообщению
        prefixed_message = f"[{settings.ENVIRONMENT.upper()}] {message}"

        # Если есть блоки, добавляем префикс к тексту в первом блоке
        # if blocks and len(blocks) > 0 and blocks[0].get("type") == "section":
        #     if "text" in blocks[0] and "text" in blocks[0]["text"]:
        #         blocks[0]["text"]["text"] = f"[{settings.ENVIRONMENT.upper()}] {blocks[0]['text']['text']}"

        response = client.chat_postMessage(
            channel=slack_channel,
            text=prefixed_message,  # Оставляем простой текст для уведомлений
            # blocks=blocks,
            icon_emoji=":robot_face:",
            username="Алерт бот",
            mrkdwn=True
        )
        return response["ok"]
    except SlackApiError as e:
        logger.error(f"❌ Ошибка при отправке сообщения в Slack: {str(e)}")
        return False


async def send_crm_lead_created_alert(
    job_title: str,
    job_company: str | None,
    job_url: str,
    lead_id: str,
    candidates: list
) -> bool:
    """
    Send Slack notification when a CRM lead is created.
    
    Args:
        job_title: Job title
        job_company: Company name
        job_url: URL to original job posting
        lead_id: AmoCRM lead ID
        candidates: List of candidates with score >= 70
    
    Returns:
        bool: True if message was sent successfully
    """
    manager_mention = f"<@{settings.SLACK_MANAGER_ID}>" if settings.SLACK_MANAGER_ID else "<!here>"
    
    crm_url = f"{settings.AMOCRM_BASE_URL}/leads/detail/{lead_id}"
    
    message = f"""🏢 *Создана карточка в AmoCRM!*

📋 *Вакансия:* {job_title}
🏢 *Компания:* {job_company or 'Не указана'}
🔗 *Оригинал:* {job_url}
🔗 *CRM:* {crm_url}

✅ *Кандидаты (score >= 70):*
"""
    
    for candidate in candidates:
        name = candidate.get("developer_name") or candidate.get("developer", {}).get("name", "Unknown")
        score = candidate.get("score", 0)
        message += f"• {name} - {score}%\n"
    
    message += f"\n👤 {manager_mention}"
    
    return await send_slack_message(message)


def create_parser_status_block(parser_name: str, status: str, details: str = None) -> list:
    """
    Создает форматированный блок для статуса парсера.

    Args:
        parser_name: Название парсера
        status: Статус (success/error/in_progress)
        details: Дополнительные детали

    Returns:
        list: Блоки форматирования Slack
    """
    status_emoji = {
        "success": "✅",
        "error": "❌",
        "in_progress": "🔄"
    }.get(status, "ℹ️")

    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"{status_emoji} *{parser_name}*\n{details or ''}"
            }
        }
    ]

    return blocks
