"""
Обработчик команды /reset для отладки.

Позволяет администраторам полностью сбросить состояние диалога
и начать тестирование с чистого листа.
"""

import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from core.keyboards import get_main_menu_keyboard
from core.config import Config

logger = logging.getLogger(__name__)

router = Router()


@router.message(Command("reset"))
async def cmd_reset(message: Message, state: FSMContext, config: Config):
    """
    Обработчик команды /reset (только для администраторов).

    Полностью очищает FSM-состояние и память диалога,
    позволяя начать тестирование заново.

    Args:
        message: Сообщение от пользователя
        state: FSM контекст
        config: Конфигурация tenant
    """
    user_id = message.from_user.id
    
    # Проверка прав администратора
    if user_id not in config.bot.admin_ids:
        logger.warning(f"[RESET] Unauthorized access attempt from user {user_id}")
        await message.answer("⛔️ У вас нет прав для использования этой команды.")
        return
    
    logger.info(f"[RESET] Admin {user_id} requested dialog reset")
    
    # Полная очистка FSM-состояния
    await state.clear()
    
    # Попытка очистить историю AI (если используется)
    try:
        from core.ai.memory import get_memory
        memory = get_memory()
        memory.clear_history(str(user_id))
        logger.info(f"[RESET] AI memory cleared for user {user_id}")
    except Exception as e:
        logger.debug(f"[RESET] AI memory not available or already clear: {e}")
    
    # Получаем локализацию
    i18n = config.bot.i18n
    
    # Отправляем подтверждение и главное меню
    reset_message = (
        "🔄 **Диалог сброшен!**\n\n"
        "Все данные удалены. Начинаем с чистого листа.\n\n"
        "Выберите категорию товаров:"
    )
    
    await message.answer(
        text=reset_message,
        reply_markup=get_main_menu_keyboard(i18n),
        parse_mode="Markdown"
    )
    
    logger.info(f"[RESET] Dialog successfully reset for user {user_id}")
