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
    Генерирует интерактивное меню для арендатора FIVE_DELUXE.

    Возвращает структуру для отправки через GreenAPI Interactive List.

    Args:
        chat_id: ID чата WhatsApp
        tenant_config: Конфигурация арендатора (TenantConfig)
        sender_name: Имя отправителя

    Returns:
        Dict с типом сообщения и данными для отправки
    """
    logger.info(f"🏢 [FIVE_DELUXE] Generating menu for {sender_name} ({chat_id})")

    # Категории товаров для Five Deluxe
    categories = [
        {"id": "category:5d_mats", "title": "💎 Премиальные 5D-коврики"},
        {"id": "category:prestige_covers", "title": "💺 Чехлы из экокожи \"Prestige\""},
        {"id": "category:trunk_organizers", "title": "📦 Органайзеры в багажник"},
        {"id": "category:dashboard_covers", "title": "🎯 Накидки на панель из алькантары"},
        {"id": "action:contact_manager", "title": "📞 Связаться с менеджером"}
    ]

    # Формируем секции для интерактивного списка
    sections = []
    catalog_rows = []

    for category in categories:
        catalog_rows.append({
            "id": category.get("id"),
            "title": category.get("title"),
            "description": ""  # Чистое меню без дублирования
        })

    sections.append({
        "title": "🌟 Наши премиальные товары",
        "rows": catalog_rows
    })

    logger.info(f"✅ [FIVE_DELUXE] Generated interactive menu with {len(catalog_rows)} categories")

    return {
        "type": "interactive_list",
        "header": f"Привет, {sender_name}! 👋",
        "body": "Добро пожаловать в Five Deluxe! Выберите раздел из меню:",
        "footer": "FIVE DELUXE - Премиальные аксессуары для вашего автомобиля",
        "button_text": "📋 Открыть меню",
        "sections": sections
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

    На данный момент показывает меню - дальнейшая логика будет реализована позже.

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

    # На текущем этапе показываем главное меню
    # В будущем здесь будет полноценная обработка категорий
    return "Спасибо за сообщение! Отправьте 'Меню' для просмотра наших товаров."
