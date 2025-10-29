"""
Модуль для управления режимом отладки бота.
"""

from typing import Set


class DebugMode:
    """Управление режимом отладки для пользователей."""

    def __init__(self):
        self._enabled_users: Set[int] = set()

    def enable(self, user_id: int):
        """Включает режим отладки для пользователя."""
        self._enabled_users.add(user_id)

    def disable(self, user_id: int):
        """Выключает режим отладки для пользователя."""
        self._enabled_users.discard(user_id)

    def is_enabled(self, user_id: int) -> bool:
        """Проверяет, включен ли режим отладки для пользователя."""
        return user_id in self._enabled_users

    def get_enabled_users(self) -> Set[int]:
        """Возвращает множество пользователей с включенным debug mode."""
        return self._enabled_users.copy()


# Глобальный экземпляр
debug_mode = DebugMode()


def format_debug_info(
    brand: str,
    model: str,
    category: str,
    sql_query: str,
    result_count: int,
    additional_info: str = ""
) -> str:
    """
    Форматирует отладочную информацию в красивый текст.

    Args:
        brand: Название бренда
        model: Название модели
        category: Код категории
        sql_query: SQL запрос
        result_count: Количество найденных записей
        additional_info: Дополнительная информация

    Returns:
        Отформатированная строка с debug info
    """
    text = (
        "🐞 <b>DEBUG INFO</b> 🐞\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"<b>Ищу в БД:</b>\n"
        f"• Марка: '<code>{brand}</code>'\n"
        f"• Модель: '<code>{model}</code>'\n"
        f"• Категория: '<code>{category}</code>'\n\n"
        f"<b>Сгенерированный SQL:</b>\n"
        f"<code>{sql_query[:500]}</code>\n"
    )

    if len(sql_query) > 500:
        text += "<i>(запрос обрезан)</i>\n"

    text += f"\n<b>Результат:</b> Найдено <b>{result_count}</b> записей."

    if additional_info:
        text += f"\n\n<b>Дополнительно:</b>\n{additional_info}"

    text += "\n\n━━━━━━━━━━━━━━━━━━━━"

    return text
