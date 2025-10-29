"""
Модуль для отправки сообщений-заглушек ("песочные часы") перед медленными операциями.

Улучшает UX, показывая пользователю, что его запрос обрабатывается.
"""

import logging
import aiohttp
from typing import Optional

logger = logging.getLogger(__name__)

# Текст сообщения-заглушки
LOADING_MESSAGE = "Ищу, секундочку... ⏳"


async def send_loading_message_whatsapp(
    chat_id: str,
    instance_id: str,
    api_token: str,
    api_url: str
) -> Optional[str]:
    """
    Отправляет сообщение-заглушку в WhatsApp перед медленной операцией.
    
    Args:
        chat_id: ID чата WhatsApp (например, "79001234567@c.us")
        instance_id: ID инстанса GreenAPI
        api_token: API токен
        api_url: URL API
        
    Returns:
        str: ID отправленного сообщения (для возможного редактирования)
        None: если не удалось отправить
    """
    try:
        url = f"{api_url}/waInstance{instance_id}/sendMessage/{api_token}"
        
        payload = {
            "chatId": chat_id,
            "message": LOADING_MESSAGE
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    message_id = data.get("idMessage")
                    logger.info(f"[LOADING] Sent loading message to {chat_id}: '{LOADING_MESSAGE}'")
                    return message_id
                else:
                    logger.warning(f"[LOADING] Failed to send loading message: {response.status}")
                    return None
            
    except Exception as e:
        logger.error(f"[LOADING] Error sending loading message: {e}")
        return None


def get_whatsapp_credentials_from_config(config):
    """
    Извлекает WhatsApp credentials из конфигурации.
    
    Args:
        config: Объект Config
        
    Returns:
        dict: {instance_id, api_token, api_url} или None
    """
    try:
        import os
        tenant_slug = config.tenant_slug
        tenant_prefix = tenant_slug.upper().replace("-", "_")
        
        instance_id = os.getenv(f"{tenant_prefix}_WHATSAPP_INSTANCE_ID")
        api_token = os.getenv(f"{tenant_prefix}_WHATSAPP_API_TOKEN")
        api_url = os.getenv(f"{tenant_prefix}_WHATSAPP_API_URL")
        
        if instance_id and api_token and api_url:
            return {
                "instance_id": instance_id,
                "api_token": api_token,
                "api_url": api_url
            }
        return None
    except Exception as e:
        logger.error(f"[LOADING] Error getting WhatsApp credentials: {e}")
        return None
