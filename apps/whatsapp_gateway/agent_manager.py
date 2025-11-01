"""
AI Agent Manager - Управление жизненным циклом AI-агента.

Этот модуль содержит логику взаимодействия с OpenAI Assistants API,
включая:
- Создание и управление threads
- Запуск runs
- Обработку вызовов инструментов (tool calls)
- Получение финального ответа от AI

Это "сердце" новой агентной архитектуры бота.
"""

import asyncio
import json
import logging
from typing import Optional
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from . import tools  # Наши инструменты
from .state_manager import get_thread_id, set_thread_id  # Thread manager

logger = logging.getLogger(__name__)

# ==============================================================================
# TOOL DISPATCHER - Маппинг имен функций на Python-функции
# ==============================================================================

TOOL_MAP = {
    "get_available_categories": tools.get_available_categories,
    "get_available_brands": tools.get_available_brands,
    "get_available_models": tools.get_available_models,
    "search_patterns": tools.search_patterns,
    "calculate_price": tools.calculate_price,
    "create_airtable_lead": tools.create_airtable_lead,
}


# ==============================================================================
# MAIN AGENT PROCESSING LOOP
# ==============================================================================

async def process_message_with_agent(
    client: AsyncOpenAI,
    assistant_id: str,
    chat_id: str,
    text: str,
    tenant_id: int,
    session: AsyncSession
) -> str:
    """
    Основной цикл обработки сообщения через AI-агента с инструментами.

    Этот метод:
    1. Получает или создает Thread для пользователя
    2. Добавляет сообщение пользователя в Thread
    3. Запускает Run (Assistant начинает обработку)
    4. Циклически проверяет статус Run
    5. Обрабатывает вызовы инструментов (tool calls)
    6. Возвращает финальный ответ AI

    Args:
        client: OpenAI AsyncClient
        assistant_id: ID ассистента в OpenAI
        chat_id: ID чата пользователя (WhatsApp chatId)
        text: Текст сообщения от пользователя
        tenant_id: ID tenant (1 для EVOPOLIKI, 2 для 5DELUXE)
        session: AsyncSession для работы с БД

    Returns:
        str: Финальный ответ AI для отправки пользователю

    Raises:
        Exception: При критических ошибках взаимодействия с OpenAI API
    """
    logger.info(f"🤖 [AGENT] ===== НАЧАЛО ОБРАБОТКИ СООБЩЕНИЯ =====")
    logger.info(f"🤖 [AGENT] Chat ID: {chat_id[:20]}...")
    logger.info(f"🤖 [AGENT] Message: '{text}'")
    logger.info(f"🤖 [AGENT] Tenant ID: {tenant_id}")

    # ─────────────────────────────────────────────────────────────────────
    # ШАГ 1: Получаем или создаем Thread для этого пользователя
    # ─────────────────────────────────────────────────────────────────────
    thread_id = await get_thread_id(chat_id)

    if not thread_id:
        # Thread не существует - создаем новый
        logger.info(f"🧵 [AGENT] Thread не найден, создаю новый...")
        thread = client.beta.threads.create()
        thread_id = thread.id
        await set_thread_id(chat_id, thread_id)
        logger.info(f"🧵 [AGENT] ✅ Создан новый Thread: {thread_id}")
    else:
        logger.info(f"🧵 [AGENT] Используем существующий Thread: {thread_id}")

    # ─────────────────────────────────────────────────────────────────────
    # ШАГ 2: Добавляем сообщение пользователя в Thread
    # ─────────────────────────────────────────────────────────────────────
    logger.info(f"💬 [AGENT] Добавляю сообщение в Thread...")
    client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=text
    )
    logger.info(f"💬 [AGENT] ✅ Сообщение добавлено")

    # ─────────────────────────────────────────────────────────────────────
    # ШАГ 3: Запускаем Assistant (создаем Run)
    # ─────────────────────────────────────────────────────────────────────
    logger.info(f"🏃 [AGENT] Запускаю Assistant...")
    run = await client.beta.threads.runs.create(
        thread_id=thread_id,
        assistant_id=assistant_id
    )
    logger.info(f"🏃 [AGENT] ✅ Run создан: {run.id}, статус: {run.status}")

    # ─────────────────────────────────────────────────────────────────────
    # ШАГ 4: Цикл ожидания и обработки инструментов
    # ─────────────────────────────────────────────────────────────────────
    max_iterations = 50  # Защита от бесконечного цикла
    iteration = 0

    while run.status in ["queued", "in_progress", "requires_action"]:
        iteration += 1

        if iteration > max_iterations:
            logger.error(f"❌ [AGENT] Превышен лимит итераций ({max_iterations})")
            return "Извините, обработка заняла слишком много времени. Попробуйте переформулировать запрос."

        # ═════════════════════════════════════════════════════════════════
        # ОБРАБОТКА ВЫЗОВОВ ИНСТРУМЕНТОВ (requires_action)
        # ═════════════════════════════════════════════════════════════════
        if run.status == "requires_action":
            logger.info(f"🛠️ [AGENT] AI запросил вызов инструментов")

            tool_outputs = []

            # Обрабатываем каждый вызов инструмента
            for tool_call in run.required_action.submit_tool_outputs.tool_calls:
                func_name = tool_call.function.name
                arguments_json = tool_call.function.arguments

                try:
                    arguments = json.loads(arguments_json)
                except json.JSONDecodeError as e:
                    logger.error(f"❌ [TOOL_CALL] Ошибка парсинга аргументов: {e}")
                    tool_outputs.append({
                        "tool_call_id": tool_call.id,
                        "output": json.dumps({"error": "Invalid arguments format"})
                    })
                    continue

                logger.info(f"🛠️ [TOOL_CALL] Функция: {func_name}")
                logger.info(f"🛠️ [TOOL_CALL] Аргументы: {arguments}")

                # Проверяем, есть ли такая функция
                if func_name not in TOOL_MAP:
                    logger.error(f"❌ [TOOL_CALL] Неизвестная функция: {func_name}")
                    tool_outputs.append({
                        "tool_call_id": tool_call.id,
                        "output": json.dumps({"error": f"Unknown function: {func_name}"})
                    })
                    continue

                # ─────────────────────────────────────────────────────────
                # ВЫЗОВ PYTHON-ФУНКЦИИ
                # ─────────────────────────────────────────────────────────
                try:
                    # Добавляем session в аргументы (все наши инструменты требуют session)
                    arguments["session"] = session

                    # Добавляем chat_id для инструмента create_airtable_lead
                    # (chat_id нужен для извлечения номера телефона клиента)
                    if func_name == "create_airtable_lead":
                        arguments["chat_id"] = chat_id
                        logger.info(f"💾 [TOOL_CALL] Инжектируем chat_id={chat_id[:20]}... для create_airtable_lead")

                    # Вызываем функцию
                    python_func = TOOL_MAP[func_name]
                    output = await python_func(**arguments)

                    logger.info(f"✅ [TOOL_CALL] Результат: {output}")

                    # Формируем ответ для OpenAI
                    # Если результат - список или словарь, сериализуем в JSON
                    if isinstance(output, (list, dict)):
                        output_str = json.dumps(output, ensure_ascii=False)
                    else:
                        output_str = str(output)

                    tool_outputs.append({
                        "tool_call_id": tool_call.id,
                        "output": output_str
                    })

                except Exception as e:
                    logger.error(f"❌ [TOOL_CALL] Ошибка выполнения {func_name}: {e}", exc_info=True)
                    tool_outputs.append({
                        "tool_call_id": tool_call.id,
                        "output": json.dumps({"error": str(e)}, ensure_ascii=False)
                    })

            # ─────────────────────────────────────────────────────────────
            # Отправляем результаты вызовов обратно в OpenAI
            # ─────────────────────────────────────────────────────────────
            logger.info(f"📤 [AGENT] Отправляю {len(tool_outputs)} результатов в OpenAI...")
            run = await client.beta.threads.runs.submit_tool_outputs(
                thread_id=thread_id,
                run_id=run.id,
                tool_outputs=tool_outputs
            )
            logger.info(f"📤 [AGENT] ✅ Результаты отправлены, новый статус: {run.status}")

        # ═════════════════════════════════════════════════════════════════
        # ОЖИДАНИЕ ОБРАБОТКИ
        # ═════════════════════════════════════════════════════════════════
        else:
            # Run в процессе или в очереди - ждем
            logger.debug(f"⏳ [AGENT] Статус Run: {run.status}, ожидание...")
            await asyncio.sleep(1)  # Ждем 1 секунду перед следующей проверкой

            # Обновляем статус Run
            run = await client.beta.threads.runs.retrieve(
                thread_id=thread_id,
                run_id=run.id
            )

    # ─────────────────────────────────────────────────────────────────────
    # ШАГ 5: Обработка финального статуса Run
    # ─────────────────────────────────────────────────────────────────────
    logger.info(f"🏁 [AGENT] Run завершен со статусом: {run.status}")

    if run.status == "completed":
        # Run успешно завершен - получаем ответ AI
        logger.info(f"✅ [AGENT] Получаю финальный ответ AI...")

        messages = await client.beta.threads.messages.list(
            thread_id=thread_id,
            limit=1,
            order="desc"
        )

        if messages.data and len(messages.data) > 0:
            # Получаем последнее сообщение (ответ AI)
            latest_message = messages.data[0]

            if latest_message.content and len(latest_message.content) > 0:
                response = latest_message.content[0].text.value

                logger.info(f"✅ [AGENT] Финальный ответ: '{response[:100]}...'")
                logger.info(f"🤖 [AGENT] ===== КОНЕЦ ОБРАБОТКИ (SUCCESS) =====")

                return response
            else:
                logger.error(f"❌ [AGENT] Сообщение пустое")
                return "Извините, получен пустой ответ. Попробуйте еще раз."
        else:
            logger.error(f"❌ [AGENT] Нет сообщений в Thread")
            return "Извините, не удалось получить ответ. Попробуйте еще раз."

    elif run.status == "failed":
        # Run завершился с ошибкой
        error_message = run.last_error.message if run.last_error else "Unknown error"
        logger.error(f"❌ [AGENT] Run failed: {error_message}")
        logger.error(f"🤖 [AGENT] ===== КОНЕЦ ОБРАБОТКИ (FAILED) =====")

        return "Извините, произошла техническая ошибка. Наш менеджер уже уведомлен."

    elif run.status == "cancelled":
        logger.warning(f"⚠️ [AGENT] Run был отменен")
        logger.warning(f"🤖 [AGENT] ===== КОНЕЦ ОБРАБОТКИ (CANCELLED) =====")

        return "Обработка была отменена. Попробуйте начать заново."

    elif run.status == "expired":
        logger.warning(f"⚠️ [AGENT] Run истек (expired)")
        logger.warning(f"🤖 [AGENT] ===== КОНЕЦ ОБРАБОТКИ (EXPIRED) =====")

        return "Время обработки истекло. Попробуйте еще раз."

    else:
        # Неожиданный статус
        logger.error(f"❌ [AGENT] Неожиданный статус Run: {run.status}")
        logger.error(f"🤖 [AGENT] ===== КОНЕЦ ОБРАБОТКИ (UNEXPECTED) =====")

        return "Произошла непредвиденная ошибка. Попробуйте позже."
