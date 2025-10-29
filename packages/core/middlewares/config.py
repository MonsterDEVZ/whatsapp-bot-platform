"""
Middleware для внедрения конфигурации в обработчики.
"""

from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from ..config import Config


class ConfigMiddleware(BaseMiddleware):
    """
    Middleware для внедрения изолированной конфигурации бота в обработчики.

    Каждый обработчик получит config в качестве параметра через data["config"].
    """

    def __init__(self, config: Config):
        """
        Args:
            config: Изолированный экземпляр конфигурации для этого бота
        """
        super().__init__()
        self.config = config

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """
        Внедряет config в data перед вызовом обработчика.

        Args:
            handler: Обработчик события
            event: Telegram событие
            data: Данные для обработчика

        Returns:
            Результат выполнения обработчика
        """
        # Внедряем конфигурацию в data
        data["config"] = self.config

        # Вызываем обработчик с внедренной конфигурацией
        return await handler(event, data)
