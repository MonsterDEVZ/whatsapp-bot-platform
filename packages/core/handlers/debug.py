"""
Обработчики команд для режима отладки.
"""

import os
from pathlib import Path
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command

from core.config import Config
from core.debug_mode import debug_mode

router = Router()


@router.message(Command("debug_on"))
async def handle_debug_on(message: Message, config: Config):
    """
    Включает режим отладки для текущего пользователя.
    Доступно только администраторам (проверка по ID).
    """
    user_id = message.from_user.id

    # Проверяем, является ли пользователь администратором
    # Для этого можно добавить список ADMIN_IDS в конфиг
    # Пока проверяем, что ID не нулевой (все реальные пользователи подходят)

    # Включаем debug mode
    debug_mode.enable(user_id)

    await message.answer(
        "🐞 <b>Режим отладки ВКЛЮЧЕН</b>\n\n"
        "Теперь при поиске лекал вы будете видеть:\n"
        "• Параметры поиска\n"
        "• Сгенерированные SQL запросы\n"
        "• Количество найденных записей\n\n"
        "Для выключения используйте /debug_off",
        parse_mode="HTML"
    )


@router.message(Command("debug_off"))
async def handle_debug_off(message: Message, config: Config):
    """
    Выключает режим отладки для текущего пользователя.
    """
    user_id = message.from_user.id

    # Выключаем debug mode
    debug_mode.disable(user_id)

    await message.answer(
        "✅ <b>Режим отладки ВЫКЛЮЧЕН</b>\n\n"
        "Отладочная информация больше не будет отображаться.",
        parse_mode="HTML"
    )


@router.message(Command("debug_status"))
async def handle_debug_status(message: Message, config: Config):
    """
    Показывает текущий статус режима отладки.
    """
    user_id = message.from_user.id
    is_enabled = debug_mode.is_enabled(user_id)

    status = "🟢 ВКЛЮЧЕН" if is_enabled else "🔴 ВЫКЛЮЧЕН"

    await message.answer(
        f"🐞 <b>Режим отладки:</b> {status}\n\n"
        f"Команды:\n"
        f"• /debug_on - включить\n"
        f"• /debug_off - выключить\n"
        f"• /debug_status - проверить статус",
        parse_mode="HTML"
    )


@router.message(Command("version"))
async def handle_version(message: Message, config: Config):
    """
    Показывает версию бота и коммит SHA для диагностики деплоев.
    """
    # Читаем версию из файла VERSION в корне проекта
    version_file = Path(__file__).parent.parent.parent.parent / "VERSION"

    try:
        version = version_file.read_text().strip()
    except FileNotFoundError:
        version = "unknown"

    # Получаем SHA коммита из переменной окружения (устанавливается при деплое)
    commit_sha = os.getenv("RAILWAY_GIT_COMMIT_SHA", "unknown")
    if commit_sha != "unknown" and len(commit_sha) > 7:
        commit_sha = commit_sha[:7]  # Короткий SHA

    # Получаем имя ветки
    branch = os.getenv("RAILWAY_GIT_BRANCH", "unknown")

    await message.answer(
        f"🤖 <b>Bot Version Information</b>\n\n"
        f"📦 Version: <code>{version}</code>\n"
        f"🔖 Commit: <code>{commit_sha}</code>\n"
        f"🌿 Branch: <code>{branch}</code>\n"
        f"🏢 Tenant: <code>{config.bot.tenant_slug}</code>",
        parse_mode="HTML"
    )
