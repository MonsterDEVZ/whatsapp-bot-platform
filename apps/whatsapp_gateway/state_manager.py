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

# In-memory хранилище для OpenAI Thread IDs: {chat_id: thread_id}
thread_ids: Dict[str, str] = {}

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

    # AI-режим: подтверждение после распознавания намерения
    AI_CONFIRMING_ORDER = "ai_confirming_order"

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
    old_state = user_states.get(chat_id, {}).get("state", "NO_STATE")

    if chat_id not in user_states:
        user_states[chat_id] = {
            "state": state,
            "data": data or {},
            "updated_at": datetime.now()
        }
        logger.info(f"🔄 [STATE_MACHINE] {chat_id[:15]}... | NEW STATE: {state}")
    else:
        user_states[chat_id]["state"] = state
        user_states[chat_id]["updated_at"] = datetime.now()
        logger.info(f"🔄 [STATE_MACHINE] {chat_id[:15]}... | {old_state} → {state}")

        # Обновляем данные (merge)
        if data:
            user_states[chat_id]["data"].update(data)
            logger.debug(f"📝 [STATE_MACHINE] Обновлены данные: {list(data.keys())}")


def get_state(chat_id: str) -> str:
    """
    Получает текущее состояние пользователя.

    Args:
        chat_id: ID чата пользователя

    Returns:
        Текущее состояние или IDLE если не найдено
    """
    if chat_id not in user_states:
        logger.debug(f"🔍 [STATE_MACHINE] {chat_id[:15]}... | NO STATE FOUND → returning IDLE")
        return WhatsAppState.IDLE

    # Проверяем TTL
    user_data = user_states[chat_id]
    elapsed_time = datetime.now() - user_data["updated_at"]

    if elapsed_time > STATE_TTL:
        # Состояние устарело - очищаем
        logger.info(
            f"⏱️  [STATE_MACHINE] Сессия для {chat_id[:15]}... сброшена по таймауту "
            f"({int(elapsed_time.total_seconds())}s неактивности)"
        )
        clear_state(chat_id)
        return WhatsAppState.IDLE

    current_state = user_data["state"]
    logger.debug(f"🔍 [STATE_MACHINE] {chat_id[:15]}... | Current state: {current_state}")
    return current_state


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


# ==============================================================================
# THREAD MANAGEMENT для OpenAI Assistants API
# ==============================================================================

async def get_thread_id(chat_id: str) -> Optional[str]:
    """
    Получает thread_id для данного чата.

    Args:
        chat_id: ID чата пользователя

    Returns:
        thread_id или None если не найден
    """
    return thread_ids.get(chat_id)


async def set_thread_id(chat_id: str, thread_id: str):
    """
    Сохраняет thread_id для данного чата.

    Args:
        chat_id: ID чата пользователя
        thread_id: OpenAI Thread ID
    """
    thread_ids[chat_id] = thread_id
    logger.info(f"🧵 [THREAD_MANAGER] Сохранен thread_id={thread_id} для chat_id={chat_id[:15]}...")


def clear_thread_id(chat_id: str):
    """
    Удаляет thread_id для данного чата.

    Args:
        chat_id: ID чата пользователя
    """
    if chat_id in thread_ids:
        del thread_ids[chat_id]
        logger.info(f"🗑️ [THREAD_MANAGER] Удален thread_id для chat_id={chat_id[:15]}...")
