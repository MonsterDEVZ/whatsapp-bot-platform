"""
Обработчик сообщений для арендатора FIVE_DELUXE.

ЗАГЛУШКА: Этот модуль содержит базовую реализацию для демонстрации
модульной архитектуры. В будущем здесь будет полная логика обработки.
"""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


async def handle_5deluxe_menu(chat_id: str, tenant_config, sender_name: str = "Гость") -> Dict[str, Any]:
    """
    Генерирует меню для арендатора FIVE_DELUXE.

    ЗАГЛУШКА: Возвращает простое текстовое сообщение.
    В будущем здесь будет полноценное интерактивное меню.

    Args:
        chat_id: ID чата WhatsApp
        tenant_config: Конфигурация арендатора (TenantConfig)
        sender_name: Имя отправителя

    Returns:
        Dict с типом сообщения и данными для отправки
    """
    logger.info(f"🏢 [FIVE_DELUXE] Generating stub menu for {sender_name} ({chat_id})")

    return {
        "type": "text",
        "message": (
            f"🌟 Привет, {sender_name}!\n\n"
            "🚧 Меню для Five Deluxe находится в разработке.\n\n"
            "Пожалуйста, свяжитесь с нашим менеджером для получения информации.\n\n"
            "📞 Мы скоро добавим полноценное меню!"
        )
    }


async def handle_5deluxe_message(
    chat_id: str,
    text_message: str,
    tenant_config,
    session,
    sender_name: str = "Гость"
) -> str:
    """
    Обрабатывает входящие сообщения для FIVE_DELUXE.

    ЗАГЛУШКА: Пока просто показывает меню на любое сообщение.

    Args:
        chat_id: ID чата WhatsApp
        text_message: Текст сообщения от пользователя
        tenant_config: Конфигурация арендатора
        session: AsyncSession для БД
        sender_name: Имя отправителя

    Returns:
        Текст ответа пользователю
    """
    logger.info(f"💬 [FIVE_DELUXE] Message from {sender_name}: {text_message}")

    # Пока просто показываем заглушку меню
    menu_data = await handle_5deluxe_menu(chat_id, tenant_config, sender_name)

    # Возвращаем текстовое сообщение
    return menu_data.get("message", "Меню для Five Deluxe в разработке.")
