import os
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from app.logger import logger

# Получаем окружение
ENV = os.getenv("ENVIRONMENT", "dev").upper()

# Инициализируем клиент Slack
slack_token = os.getenv("SLACK_BOT_TOKEN")
slack_channel = os.getenv("SLACK_CHANNEL_ID")

if not slack_token or not slack_channel:
    logger.warning("⚠️ Slack токен или ID канала не настроены. Уведомления в Slack отключены.")
    client = None
else:
    client = WebClient(token=slack_token)

async def send_slack_message(message: str, blocks: list = None) -> bool:
    """
    Отправляет сообщение в Slack канал.
    
    Args:
        message: Текст сообщения
        blocks: Опциональные блоки форматирования Slack
    
    Returns:
        bool: True если сообщение отправлено успешно, False в случае ошибки
    """
    if not client:
        logger.warning("⚠️ Попытка отправить сообщение в Slack, но клиент не инициализирован")
        return False

    try:
        # Добавляем префикс окружения к сообщению
        prefixed_message = f"[{ENV}] {message}"
        
        # Если есть блоки, добавляем префикс к тексту в первом блоке
        if blocks and len(blocks) > 0 and blocks[0].get("type") == "section":
            if "text" in blocks[0] and "text" in blocks[0]["text"]:
                blocks[0]["text"]["text"] = f"[{ENV}] {blocks[0]['text']['text']}"

        response = client.chat_postMessage(
            channel=slack_channel,
            text=prefixed_message,
            blocks=blocks
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