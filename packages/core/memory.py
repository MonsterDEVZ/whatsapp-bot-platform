"""
Модуль для хранения истории диалогов пользователей.

Обеспечивает контекстную память для AI-ассистента, позволяя боту
"помнить" предыдущие сообщения пользователя и давать связные ответы
на последовательные вопросы.
"""

from typing import List, Dict, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class DialogMemory:
    """
    In-memory хранилище истории диалогов.

    Хранит последние N сообщений для каждого пользователя,
    чтобы AI-ассистент мог использовать контекст предыдущих
    сообщений при генерации ответов.

    Attributes:
        max_messages: Максимальное количество сообщений на пользователя
        _storage: Словарь с историями диалогов по chat_id
        _last_activity: Временные метки последней активности пользователей
    """

    def __init__(self, max_messages: int = 6):
        """
        Инициализирует хранилище диалогов.

        Args:
            max_messages: Максимальное количество сообщений в истории
                         (по умолчанию 6 = 3 пары вопрос-ответ)
        """
        self.max_messages = max_messages
        self._storage: Dict[str, List[Dict[str, str]]] = {}
        self._last_activity: Dict[str, datetime] = {}
        logger.info(f"✅ DialogMemory initialized (max_messages={max_messages})")

    def add_message(self, chat_id: str, role: str, content: str) -> None:
        """
        Добавляет новое сообщение в историю пользователя.

        Если история превышает max_messages, удаляет самые старые сообщения.

        Args:
            chat_id: Идентификатор чата/пользователя
            role: Роль отправителя ("user" или "assistant")
            content: Текст сообщения
        """
        if chat_id not in self._storage:
            self._storage[chat_id] = []

        # Добавляем сообщение
        self._storage[chat_id].append({
            "role": role,
            "content": content
        })

        # Ограничиваем размер истории
        if len(self._storage[chat_id]) > self.max_messages:
            # Удаляем самые старые сообщения
            self._storage[chat_id] = self._storage[chat_id][-self.max_messages:]

        # Обновляем временную метку активности
        self._last_activity[chat_id] = datetime.now()

        logger.debug(
            f"💬 Added message to history for {chat_id}: "
            f"role={role}, content_length={len(content)}, "
            f"history_size={len(self._storage[chat_id])}"
        )

    def get_history(self, chat_id: str) -> List[Dict[str, str]]:
        """
        Возвращает историю диалога для пользователя.

        Args:
            chat_id: Идентификатор чата/пользователя

        Returns:
            Список сообщений в формате [{"role": "...", "content": "..."}, ...]
            Возвращает пустой список, если истории нет
        """
        history = self._storage.get(chat_id, [])
        logger.debug(f"📖 Retrieved history for {chat_id}: {len(history)} messages")
        return history

    def clear_history(self, chat_id: str) -> None:
        """
        Очищает историю диалога для пользователя.

        Используется при команде /start или при сбросе контекста.

        Args:
            chat_id: Идентификатор чата/пользователя
        """
        if chat_id in self._storage:
            del self._storage[chat_id]
            logger.info(f"🗑️  Cleared history for {chat_id}")
        else:
            logger.debug(f"ℹ️  No history to clear for {chat_id}")

        # Также очищаем временную метку активности
        if chat_id in self._last_activity:
            del self._last_activity[chat_id]

    def get_last_activity(self, chat_id: str) -> Optional[datetime]:
        """
        Возвращает временную метку последней активности пользователя.

        Args:
            chat_id: Идентификатор чата/пользователя

        Returns:
            Временная метка последней активности или None, если пользователь не найден
        """
        return self._last_activity.get(chat_id)

    def check_timeout(self, chat_id: str, timeout_seconds: int = 900) -> bool:
        """
        Проверяет, истек ли таймаут сессии для пользователя.

        Args:
            chat_id: Идентификатор чата/пользователя
            timeout_seconds: Максимальное время неактивности в секундах
                           (по умолчанию 900 = 15 минут)

        Returns:
            True если сессия истекла, False если активна или пользователь новый
        """
        last_activity = self.get_last_activity(chat_id)

        # Если пользователь новый, таймаута нет
        if not last_activity:
            return False

        # Проверяем превышение таймаута
        elapsed_seconds = (datetime.now() - last_activity).total_seconds()
        timed_out = elapsed_seconds > timeout_seconds

        if timed_out:
            logger.info(
                f"⏱️  Session timeout for {chat_id}: "
                f"{int(elapsed_seconds)}s elapsed (limit: {timeout_seconds}s)"
            )

        return timed_out

    def get_formatted_context(self, chat_id: str) -> str:
        """
        Возвращает историю диалога в виде отформатированной строки
        для передачи в системный промпт AI.

        Args:
            chat_id: Идентификатор чата/пользователя

        Returns:
            Форматированная строка с историей диалога
        """
        history = self.get_history(chat_id)

        if not history:
            return ""

        context_lines = ["КОНТЕКСТ ПРЕДЫДУЩЕГО ДИАЛОГА:"]
        for msg in history:
            role_label = "Пользователь" if msg["role"] == "user" else "Ассистент"
            context_lines.append(f"{role_label}: {msg['content']}")

        context_lines.append("\nУчитывай этот контекст при ответе на новый вопрос.")

        return "\n".join(context_lines)

    def get_stats(self) -> Dict[str, int]:
        """
        Возвращает статистику использования памяти.

        Returns:
            Словарь со статистикой (количество активных пользователей и т.д.)
        """
        return {
            "active_users": len(self._storage),
            "total_messages": sum(len(history) for history in self._storage.values()),
            "tracked_sessions": len(self._last_activity)
        }


# Глобальный экземпляр DialogMemory
_global_memory: Optional[DialogMemory] = None


def init_memory(max_messages: int = 6) -> DialogMemory:
    """
    Инициализирует глобальный экземпляр DialogMemory.

    Args:
        max_messages: Максимальное количество сообщений в истории

    Returns:
        Глобальный экземпляр DialogMemory
    """
    global _global_memory
    _global_memory = DialogMemory(max_messages=max_messages)
    return _global_memory


def get_memory() -> DialogMemory:
    """
    Возвращает глобальный экземпляр DialogMemory.

    Returns:
        Глобальный экземпляр DialogMemory

    Raises:
        RuntimeError: Если память не была инициализирована
    """
    if _global_memory is None:
        raise RuntimeError(
            "DialogMemory не инициализирована. "
            "Вызовите init_memory() перед использованием get_memory()."
        )
    return _global_memory
