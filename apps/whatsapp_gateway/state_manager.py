"""
State Manager для WhatsApp Gateway.

Управляет состояниями пользователей (FSM аналог из Telegram).
Использует in-memory хранилище (dict) для простоты.
"""

from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


# In-memory хранилище: {chat_id: {"state": str, "data": dict, "updated_at": datetime}}
user_states: Dict[str, Dict[str, Any]] = {}

# Время жизни состояния (15 минут)
# Если пользователь неактивен более 15 минут, его сессия сбрасывается
STATE_TTL = timedelta(minutes=15)


class WhatsAppState:
    """Возможные состояния пользователя в WhatsApp боте."""

    # Начальное состояние
    IDLE = "idle"

    # Главное меню
    MAIN_MENU = "main_menu"
    WAITING_FOR_CATEGORY_CHOICE = "waiting_for_category_choice"

    # Сценарий EVA-коврики
    EVA_WAITING_BRAND = "eva_waiting_brand"
    EVA_WAITING_MODEL = "eva_waiting_model"
    EVA_SELECTING_OPTIONS = "eva_selecting_options"
    EVA_CONFIRMING_ORDER = "eva_confirming_order"

    # Сбор контактов
    WAITING_FOR_NAME = "waiting_for_name"

    # Связь с менеджером
    CONTACT_MANAGER = "contact_manager"


def set_state(chat_id: str, state: str, data: Optional[Dict[str, Any]] = None):
    """
    Устанавливает состояние пользователя.

    Args:
        chat_id: ID чата пользователя
        state: Новое состояние
        data: Дополнительные данные для сохранения
    """
    if chat_id not in user_states:
        user_states[chat_id] = {
            "state": state,
            "data": data or {},
            "updated_at": datetime.now()
        }
    else:
        user_states[chat_id]["state"] = state
        user_states[chat_id]["updated_at"] = datetime.now()

        # Обновляем данные (merge)
        if data:
            user_states[chat_id]["data"].update(data)


def get_state(chat_id: str) -> str:
    """
    Получает текущее состояние пользователя.

    Args:
        chat_id: ID чата пользователя

    Returns:
        Текущее состояние или IDLE если не найдено
    """
    if chat_id not in user_states:
        return WhatsAppState.IDLE

    # Проверяем TTL
    user_data = user_states[chat_id]
    elapsed_time = datetime.now() - user_data["updated_at"]

    if elapsed_time > STATE_TTL:
        # Состояние устарело - очищаем
        logger.info(
            f"⏱️  Сессия для пользователя {chat_id} сброшена по таймауту "
            f"({int(elapsed_time.total_seconds())}s неактивности)"
        )
        clear_state(chat_id)
        return WhatsAppState.IDLE

    return user_data["state"]


def get_user_data(chat_id: str) -> Dict[str, Any]:
    """
    Получает данные пользователя.

    Args:
        chat_id: ID чата пользователя

    Returns:
        Словарь с данными пользователя
    """
    if chat_id not in user_states:
        return {}

    return user_states[chat_id].get("data", {})


def update_user_data(chat_id: str, data: Dict[str, Any]):
    """
    Обновляет данные пользователя (merge).

    Args:
        chat_id: ID чата пользователя
        data: Данные для обновления
    """
    if chat_id not in user_states:
        user_states[chat_id] = {
            "state": WhatsAppState.IDLE,
            "data": data,
            "updated_at": datetime.now()
        }
    else:
        user_states[chat_id]["data"].update(data)
        user_states[chat_id]["updated_at"] = datetime.now()


def clear_state(chat_id: str):
    """
    Очищает состояние пользователя.

    Args:
        chat_id: ID чата пользователя
    """
    if chat_id in user_states:
        del user_states[chat_id]


def cleanup_expired_states():
    """
    Очищает устаревшие состояния (старше STATE_TTL).

    Рекомендуется вызывать периодически (например, каждый час).
    """
    now = datetime.now()
    expired_chats = [
        chat_id
        for chat_id, data in user_states.items()
        if now - data["updated_at"] > STATE_TTL
    ]

    for chat_id in expired_chats:
        del user_states[chat_id]

    return len(expired_chats)
