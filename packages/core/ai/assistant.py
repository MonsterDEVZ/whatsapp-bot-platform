"""
OpenAI Assistants API интеграция.

Управляет взаимодействием с предварительно настроенным Ассистентом OpenAI,
который содержит базу знаний (FAQ) и умеет консультировать по автоаксессуарам.
"""

import os
import time
import logging
import json
import re
from typing import Optional, Dict, Any, Tuple
import openai

from ..memory import DialogMemory, get_memory

logger = logging.getLogger(__name__)


def parse_ai_command(response_text: str) -> Tuple[Optional[Dict[str, Any]], str]:
    """
    Парсит ответ AI на наличие JSON-команд.

    JSON-команды могут быть в формате:
    - {"intent": "SHOW_CATALOG"}
    - {"intent": "SHOW_MAIN_MENU"}

    Args:
        response_text: Ответ от AI ассистента

    Returns:
        Tuple[command_dict, clean_text]:
            - command_dict: Словарь с командой, если найдена, иначе None
            - clean_text: Текст ответа без JSON-команды
    """
    # Ищем JSON блок в ответе
    json_pattern = r'\{["\']intent["\']\s*:\s*["\'](\w+)["\']\}'
    match = re.search(json_pattern, response_text, re.IGNORECASE)

    if match:
        try:
            # Извлекаем JSON
            json_str = match.group(0)
            command_dict = json.loads(json_str)

            # Удаляем JSON из текста
            clean_text = response_text.replace(json_str, '').strip()

            logger.info(f"🎯 [AI_COMMAND] Обнаружена команда: {command_dict}")
            return command_dict, clean_text

        except json.JSONDecodeError:
            logger.warning(f"⚠️ [AI_COMMAND] Не удалось распарсить JSON: {match.group(0)}")

    return None, response_text


class AssistantManager:
    """
    Менеджер для работы с OpenAI Assistants API.

    Управляет созданием threads (сессий диалогов) и получением ответов
    от предварительно настроенного Ассистента.
    """

    def __init__(self, api_key: Optional[str] = None, assistant_id: Optional[str] = None,
                 memory: Optional[DialogMemory] = None):
        """
        Инициализирует менеджер ассистента.

        Args:
            api_key: OpenAI API ключ. Если None, берется из OPENAI_API_KEY
            assistant_id: ID ассистента в OpenAI. Если None, берется из OPENAI_ASSISTANT_ID
            memory: DialogMemory для хранения истории диалогов. Если None, использует get_memory()
        """
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        self.assistant_id = assistant_id or os.getenv('OPENAI_ASSISTANT_ID')

        if not self.api_key:
            raise ValueError("OPENAI_API_KEY не найден в переменных окружения")

        if not self.assistant_id:
            raise ValueError("OPENAI_ASSISTANT_ID не найден в переменных окружения")

        # Создаем клиент OpenAI
        self.client = openai.OpenAI(api_key=self.api_key)

        # Используем переданную memory или глобальную
        self.memory = memory

        logger.info(f"✅ AssistantManager инициализирован (Assistant ID: {self.assistant_id})")

    def create_thread(self) -> str:
        """
        Создает новую ветку диалога (thread) для пользователя.

        Returns:
            thread_id: ID созданного thread

        Raises:
            Exception: Если не удалось создать thread
        """
        try:
            thread = self.client.beta.threads.create()
            logger.info(f"🧵 Создан новый thread: {thread.id}")
            return thread.id
        except Exception as e:
            logger.error(f"❌ Ошибка при создании thread: {e}")
            raise

    async def get_response(self, thread_id: str, user_message: str, chat_id: Optional[str] = None,
                          timeout: int = 30) -> Tuple[str, Optional[Dict[str, Any]]]:
        """
        Отправляет сообщение пользователя в thread и получает ответ от Ассистента.

        Args:
            thread_id: ID thread (сессии диалога)
            user_message: Сообщение от пользователя
            chat_id: ID чата пользователя (для сохранения истории в DialogMemory)
            timeout: Максимальное время ожидания ответа в секундах (по умолчанию 30)

        Returns:
            Tuple[response_text, command_dict]:
                - response_text: Текстовый ответ от Ассистента (без JSON-команд)
                - command_dict: Словарь с командой, если AI вернул JSON-команду, иначе None

        Raises:
            TimeoutError: Если ответ не получен за timeout секунд
            Exception: Другие ошибки API
        """
        try:
            logger.info(f"💬 Попытка получить ответ от AI для thread: {thread_id}")
            logger.info(f"💬 Отправка сообщения в thread {thread_id}: '{user_message[:50]}...'")

            # 1. Получаем историю диалога из DialogMemory (если chat_id предоставлен)
            context_instructions = ""
            if chat_id and self.memory:
                context_instructions = self.memory.get_formatted_context(chat_id)
                if context_instructions:
                    logger.info(f"📖 Добавлен контекст диалога для {chat_id} ({len(context_instructions)} символов)")
                else:
                    logger.info(f"📭 Нет истории диалога для {chat_id} (новый пользователь)")

            # 2. Формируем сообщение с контекстом для thread
            # Встраиваем контекст непосредственно в сообщение, чтобы AI видел полную историю
            if context_instructions:
                message_with_context = f"{context_instructions}\n\n---\n\n{user_message}"
                logger.info(f"🔗 Контекст встроен в сообщение (итого: {len(message_with_context)} символов)")
            else:
                message_with_context = user_message

            # 3. Добавляем сообщение пользователя в thread (с контекстом если есть)
            self.client.beta.threads.messages.create(
                thread_id=thread_id,
                role="user",
                content=message_with_context
            )

            # 4. Запускаем "run" - выполнение Ассистента
            base_instructions = "Отвечай кратко, четко и по делу. Не более 3-4 предложений."
            run = self.client.beta.threads.runs.create(
                thread_id=thread_id,
                assistant_id=self.assistant_id,
                additional_instructions=base_instructions
            )

            logger.info(f"🏃 Запущен run {run.id}, ожидание завершения...")

            # 3. Ожидаем завершения run (polling)
            start_time = time.time()
            while True:
                # Проверяем таймаут
                if time.time() - start_time > timeout:
                    logger.error(f"⏱️ Таймаут ожидания ответа от Ассистента ({timeout}s)")
                    raise TimeoutError(f"Ассистент не ответил за {timeout} секунд")

                # Получаем статус run
                run_status = self.client.beta.threads.runs.retrieve(
                    thread_id=thread_id,
                    run_id=run.id
                )

                logger.debug(f"Run status: {run_status.status}")

                # Проверяем статус
                if run_status.status == 'completed':
                    logger.info("✅ Run завершен успешно")
                    break
                elif run_status.status == 'failed':
                    logger.error(f"❌ Run завершился с ошибкой: {run_status.last_error}")
                    raise Exception(f"Run failed: {run_status.last_error}")
                elif run_status.status == 'cancelled':
                    logger.error("❌ Run был отменен")
                    raise Exception("Run was cancelled")
                elif run_status.status == 'expired':
                    logger.error("❌ Run истек")
                    raise Exception("Run expired")

                # Ждем перед следующей проверкой
                time.sleep(1)

            # 4. Получаем последнее сообщение от Ассистента
            messages = self.client.beta.threads.messages.list(
                thread_id=thread_id,
                order='desc',
                limit=1
            )

            if not messages.data:
                logger.error("❌ Не получено сообщений от Ассистента")
                raise Exception("No messages received from Assistant")

            # Извлекаем текст ответа
            assistant_message = messages.data[0]

            # Проверяем, что это сообщение от ассистента
            if assistant_message.role != 'assistant':
                logger.error(f"❌ Последнее сообщение не от ассистента: {assistant_message.role}")
                raise Exception("Last message is not from assistant")

            # Извлекаем текст из content
            response_text = ""
            for content_block in assistant_message.content:
                if content_block.type == 'text':
                    response_text += content_block.text.value

            logger.info(f"💬 Получен ответ от Ассистента ({len(response_text)} символов)")

            # 5. Парсим JSON-команды из ответа
            command_dict, clean_text = parse_ai_command(response_text)

            if command_dict:
                logger.info(f"🎯 [AI_COMMAND] AI вернул команду: {command_dict['intent']}")
                # Если есть команда, сохраняем только clean_text (без JSON)
                response_to_save = clean_text if clean_text else "[Команда выполнена]"
            else:
                response_to_save = response_text

            # 6. Сохраняем диалог в память (если chat_id предоставлен)
            if chat_id and self.memory:
                self.memory.add_message(chat_id, "user", user_message)
                self.memory.add_message(chat_id, "assistant", response_to_save)
                logger.debug(f"💾 Сохранен диалог в память для {chat_id}")

            return clean_text if command_dict else response_text, command_dict

        except TimeoutError:
            raise
        except Exception as e:
            logger.exception("!!! CRITICAL ERROR IN ASSISTANT MANAGER !!!")
            logger.error(f"❌ The exact error was: {type(e).__name__}: {e}")
            logger.error(f"❌ Thread ID: {thread_id}")
            logger.error(f"❌ Assistant ID: {self.assistant_id}")
            raise


# Глобальное хранилище thread_id для пользователей
# Формат: {chat_id: thread_id}
# TODO: В будущем переместить в Redis или БД для персистентности
_user_threads = {}


def get_or_create_thread(chat_id: str, assistant_manager: AssistantManager) -> str:
    """
    Получает существующий thread_id для пользователя или создает новый.

    Args:
        chat_id: ID чата пользователя (Telegram user_id или WhatsApp chat_id)
        assistant_manager: Экземпляр AssistantManager

    Returns:
        thread_id: ID thread для этого пользователя
    """
    global _user_threads

    # Логируем текущее состояние кеша threads
    logger.info(f"🔍 [THREAD_CACHE] Всего threads в кеше: {len(_user_threads)}")
    logger.info(f"🔍 [THREAD_CACHE] Ищу thread для пользователя: {chat_id}")

    # Проверяем, есть ли уже thread для этого пользователя
    if chat_id in _user_threads:
        thread_id = _user_threads[chat_id]
        logger.info(f"✅ [THREAD_CACHE] Используется существующий thread {thread_id} для {chat_id}")
        return thread_id

    # Создаем новый thread
    logger.warning(f"⚠️ [THREAD_CACHE] Thread не найден в кеше! Создаю новый thread для {chat_id}")
    thread_id = assistant_manager.create_thread()
    _user_threads[chat_id] = thread_id

    logger.info(f"🆕 [THREAD_CACHE] Создан новый thread {thread_id} для {chat_id}")
    logger.info(f"📊 [THREAD_CACHE] Обновленный кеш: {len(_user_threads)} threads")

    return thread_id


def clear_thread(chat_id: str):
    """
    Удаляет thread для пользователя (например, при команде /start).
    Также очищает историю диалога в DialogMemory.

    Args:
        chat_id: ID чата пользователя
    """
    global _user_threads

    if chat_id in _user_threads:
        thread_id = _user_threads[chat_id]
        del _user_threads[chat_id]
        logger.info(f"🗑️ Удален thread {thread_id} для пользователя {chat_id}")

    # Очищаем историю диалога в DialogMemory
    try:
        memory = get_memory()
        memory.clear_history(chat_id)
    except RuntimeError:
        # DialogMemory не инициализирована - это нормально для некоторых случаев
        logger.debug("DialogMemory не инициализирована, пропуск очистки истории")


# Для быстрого тестирования
if __name__ == "__main__":
    import asyncio

    async def test():
        # Создаем менеджер
        manager = AssistantManager()

        # Создаем thread
        thread_id = manager.create_thread()

        # Тестовые вопросы
        test_messages = [
            "Какая у вас гарантия?",
            "Хочу ева коврики на тойоту камри",
            "Сколько стоит доставка?"
        ]

        for message in test_messages:
            print(f"\n{'='*60}")
            print(f"Пользователь: {message}")

            response = await manager.get_response(thread_id, message)

            print(f"Ассистент: {response}")
            print(f"{'='*60}\n")

    asyncio.run(test())
