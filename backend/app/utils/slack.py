import os
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from app.logger import logger
from app.config import settings

# Глобальная переменная для клиента
_client = None


def _get_slack_client():
    """Ленивая инициализация Slack клиента"""
    global _client
    
    if _client is not None:
        return _client
    
    slack_token = settings.SLACK_BOT_TOKEN
    slack_channel = settings.SLACK_CHANNEL_ID
    
    if not slack_token or not slack_channel:
        logger.warning(
            "⚠️ Slack токен или ID канала не настроены. Уведомления в Slack отключены.")
        return None
    
    _client = WebClient(token=slack_token)
    return _client


async def send_slack_message(message: str) -> bool:
    """
    Отправляет сообщение в Slack канал.

    Args:
        message: Текст сообщения
        blocks: Опциональные блоки форматирования Slack

    Returns:
        bool: True если сообщение отправлено успешно, False в случае ошибки
    """
    client = _get_slack_client()
    
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
            channel=settings.SLACK_CHANNEL_ID,
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
