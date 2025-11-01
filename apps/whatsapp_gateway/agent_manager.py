"""
AI Agent Manager - Управление OpenAI Assistant с поддержкой Tool Calls.

Этот модуль реализует "умное ожидание" ответов от AI Assistant,
обработку вызовов инструментов (tools) и защиту от таймаутов.

Архитектура: AI-Agent + External State Management
- AI ведет диалог и вызывает инструменты
- Python код выполняет инструменты и сохраняет контекст
"""

import logging
import asyncio
import time
import json
from typing import Dict, Any, Optional
from openai import OpenAI
from sqlalchemy.ext.asyncio import AsyncSession

# Импорт функций-инструментов
from . import tools
from .state_manager import get_thread_id, set_thread_id

logger = logging.getLogger(__name__)


# ==============================================================================
# ASSISTANT MANAGER - Управление OpenAI Assistant
# ==============================================================================


class AssistantManager:
    """
    Менеджер для работы с OpenAI Assistant API.

    Управляет созданием threads, runs, обработкой tool calls
    и получением ответов от AI.
    """

    def __init__(self, api_key: str, assistant_id: str):
        """
        Args:
            api_key: OpenAI API ключ
            assistant_id: ID созданного Assistant в OpenAI Platform
        """
        self.client = OpenAI(api_key=api_key)
        self.assistant_id = assistant_id
        logger.info(f"✅ AssistantManager инициализирован (assistant_id={assistant_id[:20]}...)")

    async def get_or_create_thread(self, chat_id: str) -> str:
        """
        Получить существующий или создать новый Thread для пользователя.

        Thread - это контекст диалога с AI. Один пользователь = один Thread.

        Args:
            chat_id: ID чата WhatsApp

        Returns:
            str: Thread ID
        """
        # Проверяем существующий thread
        thread_id = await get_thread_id(chat_id)

        if thread_id:
            logger.info(f"📋 [Thread] Используем существующий thread: {thread_id[:20]}...")
            return thread_id

        # Создаем новый thread
        logger.info(f"📋 [Thread] Создаем новый thread для chat_id={chat_id[:20]}...")
        thread = self.client.beta.threads.create()
        thread_id = thread.id

        # Сохраняем в state manager
        await set_thread_id(chat_id, thread_id)

        logger.info(f"✅ [Thread] Создан новый thread: {thread_id[:20]}...")
        return thread_id


async def process_message_with_agent(
    chat_id: str,
    user_message: str,
    assistant_manager: AssistantManager,
    tenant_id: int,
    session: AsyncSession,
    max_wait_time: int = 60
) -> str:
    """
    ГЛАВНАЯ ФУНКЦИЯ! Полный цикл обработки сообщения пользователя через AI Assistant.

    Этот цикл реализует "умное ожидание":
    1. Создает/получает thread
    2. Добавляет сообщение пользователя
    3. Запускает AI Assistant (run)
    4. Ждет ответа с таймаутом
    5. Обрабатывает tool calls если AI запросил инструменты
    6. Возвращает финальный ответ AI

    Args:
        chat_id: ID чата WhatsApp (например: "996555123456@c.us")
        user_message: Сообщение от пользователя
        assistant_manager: Менеджер OpenAI Assistant
        tenant_id: ID арендатора (1=EVOPOLIKI, 2=5DELUXE)
        session: Сессия базы данных для выполнения tool calls
        max_wait_time: Максимальное время ожидания в секундах (по умолчанию 60)

    Returns:
        str: Текстовый ответ AI для отправки пользователю

    Raises:
        TimeoutError: Если AI не ответил за max_wait_time секунд
        Exception: Другие ошибки OpenAI API
    """
    client = assistant_manager.client
    assistant_id = assistant_manager.assistant_id

    logger.info(f"🤖 [AI Agent] Начинаю обработку сообщения от {chat_id[:20]}...")
    logger.info(f"💬 [AI Agent] Сообщение пользователя: {user_message[:100]}...")

    try:
        # ──────────────────────────────────────────────────────────────────
        # ШАГ 1: Получить или создать Thread
        # ──────────────────────────────────────────────────────────────────
        thread_id = await assistant_manager.get_or_create_thread(chat_id)

        # ──────────────────────────────────────────────────────────────────
        # ШАГ 2: Добавить сообщение пользователя в thread
        # ──────────────────────────────────────────────────────────────────
        logger.info(f"➕ [AI Agent] Добавляю сообщение в thread {thread_id[:20]}...")

        client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=user_message
        )

        # ──────────────────────────────────────────────────────────────────
        # ШАГ 3: Создать и запустить Run
        # ──────────────────────────────────────────────────────────────────
        logger.info(f"▶️ [AI Agent] Запускаю Assistant (assistant_id={assistant_id[:20]}...)...")

        run = client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=assistant_id
        )

        run_id = run.id
        logger.info(f"🔄 [AI Agent] Run создан: {run_id[:20]}... (статус: {run.status})")

        # ──────────────────────────────────────────────────────────────────
        # ШАГ 4: "Умное ожидание" - цикл проверки статуса с таймаутом
        # ──────────────────────────────────────────────────────────────────
        start_time = time.time()
        iteration = 0

        while True:
            iteration += 1
            elapsed_time = time.time() - start_time

            # Проверка таймаута
            if elapsed_time > max_wait_time:
                logger.error(f"⏱️ [AI Agent] ТАЙМАУТ! Превышено время ожидания ({max_wait_time}s)")
                return "Извините, я немного задумался... Попробуйте повторить ваш вопрос. 🤔"

            # Пауза между проверками (1 секунда)
            await asyncio.sleep(1)

            # Получаем актуальный статус run
            run = client.beta.threads.runs.retrieve(
                thread_id=thread_id,
                run_id=run_id
            )

            logger.info(f"🔄 [AI Agent] Итерация #{iteration} | Статус: {run.status} | Время: {elapsed_time:.1f}s")

            # ──────────────────────────────────────────────────────────────
            # ОБРАБОТКА СТАТУСОВ RUN
            # ──────────────────────────────────────────────────────────────

            # ═══ СТАТУС: requires_action ═══
            # AI запросил вызов инструментов
            if run.status == "requires_action":
                logger.info(f"🛠️ [AI Agent] AI запросил вызов инструментов!")

                # Получаем список tool calls
                tool_calls = run.required_action.submit_tool_outputs.tool_calls
                logger.info(f"🛠️ [AI Agent] Количество tool calls: {len(tool_calls)}")

                # Выполняем каждый tool call
                tool_outputs = []

                for tool_call in tool_calls:
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments)
                    tool_call_id = tool_call.id

                    logger.info(f"🔧 [Tool Call] {function_name}({function_args})")

                    # ─────────────────────────────────────────────────────
                    # Вызов соответствующей функции из tools.py
                    # ─────────────────────────────────────────────────────
                    try:
                        output = await execute_tool_call(
                            function_name=function_name,
                            function_args=function_args,
                            tenant_id=tenant_id,
                            chat_id=chat_id,
                            session=session
                        )

                        logger.info(f"✅ [Tool Call] {function_name} вернул: {str(output)[:200]}...")

                    except Exception as e:
                        logger.error(f"❌ [Tool Call] Ошибка при вызове {function_name}: {e}")
                        output = f"Ошибка при выполнении {function_name}: {str(e)}"

                    # Добавляем результат в список
                    tool_outputs.append({
                        "tool_call_id": tool_call_id,
                        "output": json.dumps(output) if isinstance(output, dict) else str(output)
                    })

                # ─────────────────────────────────────────────────────────
                # Отправляем результаты tool calls обратно в OpenAI
                # ─────────────────────────────────────────────────────────
                logger.info(f"📤 [AI Agent] Отправляю результаты {len(tool_outputs)} tool calls в OpenAI...")

                client.beta.threads.runs.submit_tool_outputs(
                    thread_id=thread_id,
                    run_id=run_id,
                    tool_outputs=tool_outputs
                )

                logger.info(f"✅ [AI Agent] Tool outputs отправлены, продолжаю ожидание...")
                continue  # Продолжаем цикл ожидания

            # ═══ СТАТУС: completed ═══
            # AI завершил обработку и готов ответ
            elif run.status == "completed":
                logger.info(f"✅ [AI Agent] Run completed! Получаю ответ...")

                # Получаем последнее сообщение от assistant
                messages = client.beta.threads.messages.list(
                    thread_id=thread_id,
                    limit=1,
                    order="desc"
                )

                if messages.data:
                    assistant_message = messages.data[0]

                    # Извлекаем текст ответа
                    if assistant_message.content and len(assistant_message.content) > 0:
                        response_text = assistant_message.content[0].text.value

                        logger.info(f"💬 [AI Agent] Ответ AI: {response_text[:200]}...")
                        logger.info(f"⏱️ [AI Agent] Общее время обработки: {elapsed_time:.2f}s")

                        return response_text
                    else:
                        logger.warning(f"⚠️ [AI Agent] Сообщение от AI пустое!")
                        return "Извините, произошла ошибка. Попробуйте еще раз."
                else:
                    logger.warning(f"⚠️ [AI Agent] Нет сообщений в thread!")
                    return "Извините, произошла ошибка. Попробуйте еще раз."

            # ═══ СТАТУС: failed ═══
            # AI сообщил об ошибке
            elif run.status == "failed":
                error_message = run.last_error.message if run.last_error else "Unknown error"
                logger.error(f"❌ [AI Agent] Run failed! Error: {error_message}")
                return "Извините, произошла техническая ошибка. Наш менеджер уже уведомлен. Пожалуйста, попробуйте позже."

            # ═══ СТАТУС: cancelled ═══
            elif run.status == "cancelled":
                logger.warning(f"⚠️ [AI Agent] Run был отменен")
                return "Запрос был отменен. Попробуйте еще раз."

            # ═══ СТАТУС: expired ═══
            elif run.status == "expired":
                logger.warning(f"⚠️ [AI Agent] Run истек (expired)")
                return "Время ожидания истекло. Попробуйте еще раз."

            # ═══ СТАТУСЫ: queued, in_progress ═══
            # Продолжаем ждать
            elif run.status in ["queued", "in_progress"]:
                # Продолжаем цикл
                continue

            # ═══ НЕИЗВЕСТНЫЙ СТАТУС ═══
            else:
                logger.error(f"❌ [AI Agent] Неизвестный статус run: {run.status}")
                return "Произошла неожиданная ошибка. Попробуйте еще раз."

    except Exception as e:
        logger.error(f"❌ [AI Agent] Критическая ошибка: {e}", exc_info=True)
        return "Извините, произошла техническая ошибка. Попробуйте позже."


async def execute_tool_call(
    function_name: str,
    function_args: Dict[str, Any],
    tenant_id: int,
    chat_id: str,
    session: AsyncSession
) -> Any:
    """
    Выполняет вызов функции-инструмента по имени.

    Это диспетчер (dispatcher), который маршрутизирует вызовы AI
    к соответствующим функциям из tools.py.

    Args:
        function_name: Имя функции для вызова
        function_args: Аргументы функции (dict)
        tenant_id: ID арендатора
        chat_id: ID чата WhatsApp
        session: Сессия базы данных

    Returns:
        Any: Результат выполнения функции

    Raises:
        ValueError: Если функция не найдена
    """
    logger.info(f"🔧 [Tool Dispatcher] Вызов {function_name} с аргументами: {function_args}")

    # ═══════════════════════════════════════════════════════════════════════
    # ДИСПЕТЧЕР ИНСТРУМЕНТОВ
    # ═══════════════════════════════════════════════════════════════════════

    # Добавляем обязательные параметры к аргументам
    function_args["tenant_id"] = tenant_id
    function_args["session"] = session

    # Для create_airtable_lead добавляем chat_id
    if function_name == "create_airtable_lead":
        function_args["chat_id"] = chat_id

    # Маршрутизация к функциям
    if function_name == "get_available_categories":
        return await tools.get_available_categories(**function_args)

    elif function_name == "get_available_brands":
        return await tools.get_available_brands(**function_args)

    elif function_name == "get_available_models":
        return await tools.get_available_models(**function_args)

    elif function_name == "search_patterns":
        return await tools.search_patterns(**function_args)

    elif function_name == "calculate_price":
        return await tools.calculate_price(**function_args)

    elif function_name == "create_airtable_lead":
        return await tools.create_airtable_lead(**function_args)

    else:
        raise ValueError(f"Неизвестная функция: {function_name}")
