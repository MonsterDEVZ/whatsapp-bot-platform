"""
Отладочные команды для проверки AI Assistant.

Позволяет администраторам напрямую общаться с OpenAI Assistant,
минуя всю FSM-логику, чтобы диагностировать работу AI модуля.
"""

import logging
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command

from core.config import Config
from core.ai.assistant import AssistantManager

logger = logging.getLogger(__name__)

router = Router()


@router.message(Command("ask_ai"))
async def handle_ask_ai_telegram(message: Message, config: Config):
    """
    Секретная отладочная команда для прямого общения с AI Assistant.
    
    Доступна только администраторам. Игнорирует FSM и всю бизнес-логику.
    
    Формат: /ask_ai <вопрос>
    Пример: /ask_ai Привет, как тебя зовут?
    
    Args:
        message: Сообщение от пользователя
        config: Конфигурация бота
    """
    user_id = message.from_user.id
    
    # Проверка прав администратора
    if user_id not in config.bot.admin_ids:
        logger.warning(f"[AI_DEBUG] Unauthorized access attempt from user {user_id}")
        return  # Молча игнорируем, чтобы не раскрывать существование команды
    
    # Извлекаем текст вопроса (всё после "/ask_ai ")
    question = message.text.split(maxsplit=1)
    
    if len(question) < 2:
        await message.answer(
            "❓ <b>Формат команды:</b>\n"
            "<code>/ask_ai ваш вопрос</code>\n\n"
            "Пример:\n"
            "<code>/ask_ai Привет, как тебя зовут?</code>",
            parse_mode="HTML"
        )
        return
    
    question_text = question[1].strip()
    
    # Отправляем индикатор печати
    await message.bot.send_chat_action(message.chat.id, "typing")
    
    logger.info(f"[AI_DEBUG] Admin {user_id} asking: '{question_text[:50]}...'")
    
    try:
        # Создаем AssistantManager
        assistant = AssistantManager()
        
        # Получаем или создаем thread_id для админа
        # Используем user_id как chat_id для создания уникального thread
        thread_id = assistant.create_thread()
        
        logger.info(f"[AI_DEBUG] Created thread: {thread_id}")
        
        # НАПРЯМУЮ вызываем AI Assistant (без FSM, без state_manager)
        response, _ = await assistant.get_response(
            thread_id=thread_id,
            user_message=question_text,
            chat_id=str(user_id),
            timeout=30
        )
        
        logger.info(f"[AI_DEBUG] AI response received: {len(response)} chars")
        
        # Отправляем ответ админу
        await message.answer(
            f"🤖 <b>AI Assistant Response:</b>\n\n{response}",
            parse_mode="HTML"
        )
        
    except Exception as e:
        # Отправляем ПОЛНЫЙ текст ошибки админу для диагностики
        error_message = (
            f"❌ <b>AI Module Error:</b>\n\n"
            f"<code>{type(e).__name__}: {str(e)}</code>\n\n"
            f"<b>Details:</b>\n"
            f"<pre>{repr(e)}</pre>"
        )
        
        logger.error(f"[AI_DEBUG] Error: {e}", exc_info=True)
        
        await message.answer(
            error_message,
            parse_mode="HTML"
        )
