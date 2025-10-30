"""
Обработчик сообщений для арендатора FIVE_DELUXE.

Клонирован из evopoliki_handler.py с адаптацией для Five Deluxe.
Основное отличие: НЕТ категории EVA-коврики.
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

    i18n = tenant_config.i18n

    # Получаем категории из локализации (БЕЗ EVA-ковриков для Five Deluxe)
    catalog_categories = i18n.get("buttons.catalog_categories") or []

    if not catalog_categories or len(catalog_categories) == 0:
        logger.error("❌ [FIVE_DELUXE] catalog_categories not found or empty!")
        return {
            "type": "text",
            "message": f"🚗 Здравствуйте, {sender_name}!\n\n⚠️ Меню временно недоступно. Свяжитесь с менеджером."
        }

    # Формируем секции для интерактивного списка
    sections = []

    # Секция 1: Каталог товаров
    catalog_rows = []
    for idx, category in enumerate(catalog_categories, start=1):
        text = category.get("text", "")
        callback_data = category.get("callback_data", "")

        # Создаем row для интерактивного списка
        catalog_rows.append({
            "id": callback_data,  # Например: "category:5d_mats"
            "title": text,  # Название категории
            "description": ""  # Убираем дублирование текста
        })

    sections.append({
        "title": "✨ Наши товары",
        "rows": catalog_rows
    })

    logger.info(f"✅ [FIVE_DELUXE] Generated interactive menu with {len(catalog_rows)} categories")

    return {
        "type": "interactive_list",
        "header": f"Привет, {sender_name}! 👋",
        "body": i18n.get("start.welcome") or "Добро пожаловать в 5Deluxe! Выберите раздел из меню:",
        "footer": "5Deluxe - Премиальные автоаксессуары",
        "button_text": "📋 Открыть меню",
        "sections": sections
    }


async def handle_5deluxe_list_response(
    chat_id: str,
    selected_id: str,
    tenant_config,
    session
) -> str:
    """
    Обрабатывает выбор из интерактивного списка для FIVE_DELUXE.

    Args:
        chat_id: ID чата WhatsApp
        selected_id: ID выбранного элемента (например, "category:5d_mats")
        tenant_config: Конфигурация арендатора
        session: AsyncSession для БД

    Returns:
        Текст ответа пользователю
    """
    logger.info(f"🎯 [FIVE_DELUXE] User selected: {selected_id}")

    # Импортируем нужные обработчики
    from ..whatsapp_handlers import handle_main_menu_choice
    from ..state_manager import set_state, WhatsAppState

    # Парсим selected_id
    if ":" in selected_id:
        action_type, action_value = selected_id.split(":", 1)

        if action_type == "category":
            # Устанавливаем состояние выбора категории
            logger.info(f"🛒 [FIVE_DELUXE] Starting order flow for category: {action_value}")

            # Вызываем существующий обработчик через его внутреннюю логику
            # Находим индекс категории в списке
            i18n = tenant_config.i18n
            catalog_categories = i18n.get("buttons.catalog_categories") or []

            # Находим индекс выбранной категории
            for idx, category in enumerate(catalog_categories, start=1):
                if category.get("callback_data") == selected_id:
                    # Вызываем универсальный обработчик с номером пункта меню
                    return await handle_main_menu_choice(chat_id, str(idx), tenant_config, session)

            return "❌ Ошибка: категория не найдена."

        elif action_type == "action" and action_value == "contact_manager":
            # Обработка запроса на связь с менеджером
            from ..state_manager import update_user_data

            set_state(chat_id, WhatsAppState.CONTACT_MANAGER)
            update_user_data(chat_id, {
                "application_type": "Запрос на звонок"
            })

            return i18n.get("contact_manager.text") or "📞 Введите ваше имя, и мы свяжемся с вами."

    return "❌ Неизвестная команда. Отправьте 'Меню' для возврата."


async def handle_5deluxe_message(
    chat_id: str,
    text_message: str,
    tenant_config,
    session,
    sender_name: str = "Гость"
) -> str:
    """
    Обрабатывает входящие сообщения для FIVE_DELUXE.

    Fallback обработчик для IVR режима (когда AI отключен).

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

    # Простой fallback: предлагаем показать меню
    return "Спасибо за сообщение! Отправьте 'Меню' для просмотра наших товаров."
