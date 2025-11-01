"""
AI Agent Manager - Упрощенная версия для распознавания намерений.

Этот модуль содержит единственную функцию для взаимодействия с OpenAI,
которая используется ТОЛЬКО для первоначального распознавания намерения пользователя.

AI НЕ ведет весь диалог. Он выступает только как "умный маршрутизатор"
на входе, возвращая JSON с намерением или текстовый ответ.

Вся дальнейшая логика выполняется IVR-воронкой без обращений к AI.
"""

import asyncio
import logging
from typing import Optional
from openai import AsyncOpenAI

from .state_manager import get_thread_id, set_thread_id

logger = logging.getLogger(__name__)


async def get_ai_response(
    client: AsyncOpenAI,
    assistant_id: str,
    chat_id: str,
    text: str
) -> str:
    """
    Получить ответ от AI-ассистента (используется ТОЛЬКО для распознавания намерения).

    Эта функция вызывается ТОЛЬКО ОДИН РАЗ, когда пользователь находится в состоянии IDLE.
    AI анализирует сообщение и возвращает:
    - JSON с намерением (например, {"intent": "ORDER", "category": "eva_mats"})
    - Или текстовый ответ на вопрос/приветствие

    После получения ответа управление передается в IVR-воронку,
    и AI больше не вызывается до следующего сброса в IDLE.

    Args:
        client: OpenAI AsyncClient
        assistant_id: ID ассистента в OpenAI
        chat_id: ID чата пользователя (WhatsApp chatId)
        text: Текст сообщения от пользователя

    Returns:
        str: Ответ AI (JSON или текст)

    Raises:
        Exception: При критических ошибках взаимодействия с OpenAI API
    """
    logger.info(f"🤖 [AI] Запрос к AI для распознавания намерения")
    logger.info(f"🤖 [AI] Chat ID: {chat_id[:20]}...")
    logger.info(f"🤖 [AI] Message: '{text}'")

    # ─────────────────────────────────────────────────────────────────────
    # ШАГ 1: Получаем или создаем Thread для этого пользователя
    # ─────────────────────────────────────────────────────────────────────
    thread_id = await get_thread_id(chat_id)

    if not thread_id:
        logger.info(f"🧵 [AI] Thread не найден, создаю новый...")
        thread = client.beta.threads.create()
        thread_id = thread.id
        await set_thread_id(chat_id, thread_id)
        logger.info(f"🧵 [AI] ✅ Создан новый Thread: {thread_id}")
    else:
        logger.info(f"🧵 [AI] Используем существующий Thread: {thread_id}")

    # ─────────────────────────────────────────────────────────────────────
    # ШАГ 2: Добавляем сообщение пользователя в Thread
    # ─────────────────────────────────────────────────────────────────────
    logger.info(f"💬 [AI] Добавляю сообщение в Thread...")
    client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=text
    )
    logger.info(f"💬 [AI] ✅ Сообщение добавлено")

    # ─────────────────────────────────────────────────────────────────────
    # ШАГ 3: Запускаем Assistant
    # ─────────────────────────────────────────────────────────────────────
    logger.info(f"🏃 [AI] Запускаю Assistant...")
    run = client.beta.threads.runs.create(
        thread_id=thread_id,
        assistant_id=assistant_id
    )
    logger.info(f"🏃 [AI] ✅ Run создан: {run.id}")

    # ─────────────────────────────────────────────────────────────────────
    # ШАГ 4: Ждем завершения обработки (простое ожидание)
    # ─────────────────────────────────────────────────────────────────────
    max_wait_time = 30  # Максимум 30 секунд ожидания
    elapsed_time = 0

    while run.status in ["queued", "in_progress"]:
        if elapsed_time >= max_wait_time:
            logger.error(f"❌ [AI] Превышено время ожидания ({max_wait_time}с)")
            return "Извините, обработка заняла слишком много времени. Попробуйте переформулировать запрос."

        logger.debug(f"⏳ [AI] Статус: {run.status}, ожидание...")
        await asyncio.sleep(1)
        elapsed_time += 1

        # Обновляем статус Run
        run = client.beta.threads.runs.retrieve(
            thread_id=thread_id,
            run_id=run.id
        )

    # ─────────────────────────────────────────────────────────────────────
    # ШАГ 5: Обработка финального статуса
    # ─────────────────────────────────────────────────────────────────────
    logger.info(f"🏁 [AI] Run завершен со статусом: {run.status}")

    if run.status == "completed":
        # Получаем ответ AI
        messages = client.beta.threads.messages.list(
            thread_id=thread_id,
            limit=1,
            order="desc"
        )

        if messages.data and len(messages.data) > 0:
            latest_message = messages.data[0]

            if latest_message.content and len(latest_message.content) > 0:
                response = latest_message.content[0].text.value

                logger.info(f"✅ [AI] Ответ получен: '{response[:100]}...'")
                return response
            else:
                logger.error(f"❌ [AI] Сообщение пустое")
                return "Извините, получен пустой ответ. Попробуйте еще раз."
        else:
            logger.error(f"❌ [AI] Нет сообщений в Thread")
            return "Извините, не удалось получить ответ. Попробуйте еще раз."

    elif run.status == "failed":
        error_message = run.last_error.message if run.last_error else "Unknown error"
        logger.error(f"❌ [AI] Run failed: {error_message}")
        return "Извините, произошла техническая ошибка. Наш менеджер уже уведомлен."

    elif run.status == "cancelled":
        logger.warning(f"⚠️ [AI] Run был отменен")
        return "Обработка была отменена. Попробуйте начать заново."

    elif run.status == "expired":
        logger.warning(f"⚠️ [AI] Run истек")
        return "Время обработки истекло. Попробуйте еще раз."

    else:
        logger.error(f"❌ [AI] Неожиданный статус: {run.status}")
        return "Произошла непредвиденная ошибка. Попробуйте позже."
