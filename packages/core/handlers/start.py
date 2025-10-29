"""
Обработчик команды /start.
"""

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from core.keyboards import get_language_keyboard
from core.config import Config

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, config: Config):
    """
    Обработчик команды /start.

    Отправляет приветственное сообщение и предлагает выбрать язык.
    После выбора языка появится навигационная панель.
    """
    # Сбрасываем состояние при старте
    await state.clear()

    # Получаем локализованное приветственное сообщение
    i18n = config.bot.i18n
    welcome_text = i18n.get("start.welcome")

    await message.answer(
        text=welcome_text,
        reply_markup=get_language_keyboard(i18n)
    )
